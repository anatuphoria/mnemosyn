from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QByteArray, QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QToolButton

from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.tokens import SIZE
from cns_desktop.design.widgets import SegmentedControl

NAMES = ("Explore", "Slices", "Pathways", "Lab")
ICONS = {"Explore": "brain", "Slices": "layers-2", "Pathways": "route", "Lab": "flask-conical"}
VERSION = 2

Join = tuple[str, str]


class Workspaces(QObject):
    changed = Signal(str)

    def __init__(self, window, settings=None) -> None:
        super().__init__(window)
        self.window = window
        self.settings = settings
        if settings is not None and settings.value("workspaces/version", 0, type=int) != VERSION:
            settings.remove("workspaces")
        self.memory: dict[str, tuple[QByteArray, list[Join]]] = {}
        self.current = "Explore"
        self.locked = False
        self.lab_docks: list = []
        self._enter: Callable[[], None] | None = None
        self._leave: Callable[[], None] | None = None
        self.defaults: dict[str, tuple[QByteArray, list[Join]]] = {}
        self.arrange: dict[str, Callable[[], object]] = {}
        self.narrow: dict[str, list[Join]] = {}
        self.touched: set[str] = set()
        self._applying = 0
        self._watched: set[int] = set()
        self.switcher = SegmentedControl([(name, name) for name in NAMES], icons=ICONS)
        self.switcher.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.switcher.changed.connect(self.switch)
        self.actions: dict[str, QAction] = {}
        for number, name in enumerate(NAMES, 1):
            self.switcher.button(name).setToolTip(f"{name} workspace  Ctrl+{number}")
            action = QAction(f"{name} workspace", window,
                             shortcut=QKeySequence(f"Ctrl+{number}"),
                             triggered=lambda _=False, n=name: self.switch(n))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            window.addAction(action)
            self.actions[name] = action
        self.switcher.button("Lab").hide()
        self.actions["Lab"].setEnabled(False)
        window.topbar.set_switch(self.switcher)

    def button(self, name: str) -> QToolButton:
        return self.switcher.button(name)

    def groups(self) -> list[PanelGroup]:
        return self.window.findChildren(PanelGroup)

    def _group(self, name: str) -> PanelGroup | None:
        return next((g for g in self.groups() if g.objectName() == name), None)

    def joins(self) -> list[Join]:
        return [(host.objectName(), guest.objectName()) for host in self.groups()
                for guest in host.joined()]

    def _watch(self) -> None:
        for group in self.groups():
            if id(group) not in self._watched:
                self._watched.add(id(group))
                group.dockLocationChanged.connect(lambda _area: self._moved())
                group.topLevelChanged.connect(lambda _floating: self._moved())
                group.close_button.clicked.connect(lambda _checked=False: self._moved())
                group.toggleViewAction().triggered.connect(lambda _checked=False: self._moved())

    def _moved(self) -> None:
        if not self._applying:
            self.touched.add(self.current)

    def release_joins(self, show: bool = True) -> None:
        self._applying += 1
        try:
            for group in self.groups():
                group.release_all(show)
        finally:
            self._applying -= 1

    def apply_joins(self, joins: list[Join]) -> None:
        self._applying += 1
        try:
            for host_name, guest_name in joins:
                host, guest = self._group(host_name), self._group(guest_name)
                if host is not None and guest is not None:
                    host.join(guest)
        finally:
            self._applying -= 1

    def _key(self, name: str) -> str:
        return f"workspaces/{name}"

    def _stored(self, name: str) -> tuple[QByteArray, list[Join]] | None:
        if self.settings is None:
            return self.memory.get(name)
        value = self.settings.value(self._key(name))
        if not isinstance(value, QByteArray) or value.isEmpty():
            return None
        joins = self.settings.value(f"workspaces/joins/{name}", [])
        if isinstance(joins, str):
            joins = [joins]
        pairs = [tuple(text.split(":", 1)) for text in joins or [] if ":" in str(text)]
        return value, pairs

    def _store(self, name: str) -> None:
        state, joins = self.window.saveState(), self.joins()
        if self.settings is None:
            self.memory[name] = (state, joins)
            return
        self.settings.setValue("workspaces/version", VERSION)
        self.settings.setValue(self._key(name), state)
        self.settings.setValue(f"workspaces/joins/{name}", [f"{h}:{g}" for h, g in joins])

    def _restore_state(self, state: QByteArray) -> None:
        size = self.window.size()
        self.window.restoreState(state)
        if self.window.isVisible() and self.window.size() != size:
            self.window.resize(size)

    def _restore(self, state: QByteArray, joins: list[Join]) -> None:
        self._applying += 1
        try:
            self.release_joins(show=False)
            self._restore_state(state)
            self.apply_joins(joins)
        finally:
            self._applying -= 1

    def _apply_default(self, name: str) -> None:
        self.window.before_layout(name)
        state, joins = self.defaults[name]
        if self.window.width() < SIZE["narrow"]:
            joins = [*joins, *self.narrow.get(name, [])]
        size = self.window.size()
        self._applying += 1
        try:
            self.release_joins(show=False)
            self._restore_state(state)
            self.apply_joins(joins)
            if name in self.arrange:
                self.arrange[name]()
            self.apply_joins(joins)
            if self.window.isVisible() and self.window.size() != size:
                self.window.layout().activate()
                self.window.resize(size)
        finally:
            self._applying -= 1
        self.touched.discard(name)

    def _apply(self, name: str) -> None:
        self.window.before_layout(name)
        stored = self._stored(name)
        if stored is None:
            self._apply_default(name)
        else:
            self._restore(*stored)

    def capture_defaults(self, arrange: dict[str, Callable[[], list[Join]]],
                         narrow: dict[str, list[Join]] | None = None) -> None:
        self.narrow.update(narrow or {})
        self.arrange.update(arrange)
        base = self.window.saveState()
        for name, build in arrange.items():
            self.release_joins()
            self._restore_state(base)
            joins = build()
            self.apply_joins(joins)
            self.defaults[name] = (self.window.saveState(), list(joins))
        self._apply("Explore")
        self._after_restore("Explore")
        self._watch()

    def register_lab(self, docks: list, enter: Callable[[], None],
                     leave: Callable[[], None], arrange: Callable[[], None] | None = None,
                     narrow: list[Join] | None = None) -> None:
        self.lab_docks = list(docks)
        self._enter, self._leave = enter, leave
        if narrow:
            self.narrow["Lab"] = list(narrow)
        joins = self.joins()
        state = self.window.saveState()
        self.release_joins()
        for dock in self.groups():
            if dock not in self.lab_docks:
                dock.hide()
        for dock in self.lab_docks:
            dock.show()
        if arrange is not None:
            arrange()
            self.arrange["Lab"] = arrange
        self.defaults["Lab"] = (self.window.saveState(), [])
        self._restore(state, joins)
        self.switcher.button("Lab").show()
        self.actions["Lab"].setEnabled(not self.locked)
        self._watch()
        self._after_restore(self.current)

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        for name in NAMES:
            self.switcher.button(name).setEnabled(not locked)
            self.actions[name].setEnabled(not locked and (name != "Lab" or bool(self.lab_docks)))

    def _after_restore(self, name: str) -> None:
        in_lab = name == "Lab"
        for dock in self.lab_docks:
            if not in_lab:
                dock.hide()
            dock.toggleViewAction().setEnabled(in_lab)
        if self.lab_docks:
            for dock in self.window.workspace_docks():
                dock.toggleViewAction().setEnabled(not in_lab)
        if not in_lab:
            self.window.quiz_dock.setVisible(self.window.quiz_active)
        self.window.topbar.show_group(name)
        self.window.sync_after_layout(name)

    def width_changed(self, old: int, new: int) -> None:
        narrow = SIZE["narrow"]
        if (old < narrow) == (new < narrow) or old <= 0 or self._applying:
            return
        if self._stored(self.current) is None and self.current not in self.touched:
            self._apply_default(self.current)
            self.window.sync_after_layout(self.current)

    def fit_to_width(self) -> None:
        if self._stored(self.current) is None:
            self._apply_default(self.current)
            self.window.sync_after_layout(self.current)

    def switch(self, name: str) -> None:
        if name not in NAMES or name == self.current or self.locked:
            self.switcher.set_current(self.current)
            return
        if name == "Lab" and not self.lab_docks:
            self.switcher.set_current(self.current)
            return
        if name == "Lab" and self.window.pathway_active:
            self.window.pathways.leave()
        self._store(self.current)
        if self.current == "Lab" and self._leave is not None:
            self._leave()
        size = self.window.size()
        self._apply(name)
        self.current = name
        self._after_restore(name)
        self._keep_size(size)
        if name == "Lab" and self._enter is not None:
            self._enter()
        self.switcher.set_current(name)
        self.changed.emit(name)

    def reset(self, name: str | None = None) -> None:
        name = name or self.current
        if name != self.current:
            return
        size = self.window.size()
        self._apply_default(name)
        self._after_restore(name)
        self._keep_size(size)

    def _keep_size(self, size) -> None:
        if self.window.isVisible() and self.window.size() != size:
            self.window.layout().activate()
            self.window.resize(size)

    def save(self) -> None:
        self._store(self.current)
