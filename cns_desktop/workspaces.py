from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QByteArray, QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QToolButton, QWidget

NAMES = ("Explore", "Slices", "Pathways", "Lab")
VERSION = 1


class Workspaces(QObject):
    changed = Signal(str)

    def __init__(self, window, settings=None) -> None:
        super().__init__(window)
        self.window = window
        self.settings = settings
        if settings is not None and settings.value("workspaces/version", 0, type=int) != VERSION:
            settings.remove("workspaces")
        self.memory: dict[str, QByteArray] = {}
        self.current = "Explore"
        self.locked = False
        self.lab_docks: list = []
        self._enter: Callable[[], None] | None = None
        self._leave: Callable[[], None] | None = None
        self.defaults: dict[str, QByteArray] = {}
        self.corner = QWidget()
        row = QHBoxLayout(self.corner)
        row.setContentsMargins(0, 0, 4, 0)
        row.setSpacing(2)
        self.group = QButtonGroup(self)
        self._buttons: dict[str, QToolButton] = {}
        self.actions: dict[str, QAction] = {}
        for number, name in enumerate(NAMES, 1):
            button = QToolButton(text=name, checkable=True, autoRaise=True)
            button.setToolTip(f"{name} workspace (Ctrl+{number})")
            button.clicked.connect(lambda _=False, n=name: self.switch(n))
            self.group.addButton(button)
            row.addWidget(button)
            self._buttons[name] = button
            action = QAction(f"{name} workspace", window,
                             shortcut=QKeySequence(f"Ctrl+{number}"),
                             triggered=lambda _=False, n=name: self.switch(n))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            window.addAction(action)
            self.actions[name] = action
        self._buttons["Explore"].setChecked(True)
        self._buttons["Lab"].hide()
        self.actions["Lab"].setEnabled(False)
        window.menuBar().setCornerWidget(self.corner, Qt.Corner.TopRightCorner)

    def button(self, name: str) -> QToolButton:
        return self._buttons[name]

    def _key(self, name: str) -> str:
        return f"workspaces/{name}"

    def _stored(self, name: str) -> QByteArray | None:
        if self.settings is None:
            return self.memory.get(name)
        value = self.settings.value(self._key(name))
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def _store(self, name: str) -> None:
        state = self.window.saveState()
        if self.settings is None:
            self.memory[name] = state
            return
        self.settings.setValue("workspaces/version", VERSION)
        self.settings.setValue(self._key(name), state)

    def capture_defaults(self, arrange: dict[str, Callable[[], None]]) -> None:
        explore = self.window.saveState()
        self.defaults["Explore"] = explore
        for name, build in arrange.items():
            self.window.restoreState(explore)
            build()
            self.defaults[name] = self.window.saveState()
        self.window.restoreState(explore)
        stored = self._stored("Explore")
        if stored is not None:
            self.window.restoreState(stored)
            self._after_restore("Explore")

    def register_lab(self, docks: list, enter: Callable[[], None],
                     leave: Callable[[], None]) -> None:
        self.lab_docks = list(docks)
        self._enter, self._leave = enter, leave
        others = [d for d in self.window.findChildren(type(docks[0])) if d not in self.lab_docks]
        state = self.window.saveState()
        for dock in others:
            dock.hide()
        for dock in self.lab_docks:
            dock.show()
        self.defaults["Lab"] = self.window.saveState()
        self.window.restoreState(state)
        self._buttons["Lab"].show()
        self.actions["Lab"].setEnabled(not self.locked)
        self._after_restore(self.current)

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        for name, button in self._buttons.items():
            button.setEnabled(not locked)
            self.actions[name].setEnabled(not locked and (name != "Lab" or bool(self.lab_docks)))

    def _after_restore(self, name: str) -> None:
        in_lab = name == "Lab"
        for dock in self.lab_docks:
            if not in_lab:
                dock.hide()
            dock.toggleViewAction().setEnabled(in_lab)
        if not in_lab:
            self.window.quiz_dock.setVisible(self.window.quiz_active)
        self.window.sync_after_layout(name)

    def switch(self, name: str) -> None:
        if name not in NAMES or name == self.current or self.locked:
            return
        if name == "Lab" and not self.lab_docks:
            return
        if name == "Lab" and self.window.pathway_active:
            self.window.pathways.leave()
        self._store(self.current)
        if self.current == "Lab" and self._leave is not None:
            self._leave()
        self.window.restoreState(self._stored(name) or self.defaults[name])
        self.current = name
        self._after_restore(name)
        if name == "Lab" and self._enter is not None:
            self._enter()
        self._buttons[name].setChecked(True)
        self.changed.emit(name)

    def reset(self, name: str | None = None) -> None:
        name = name or self.current
        if name != self.current:
            return
        self.window.restoreState(self.defaults[name])
        self._after_restore(name)

    def save(self) -> None:
        self._store(self.current)
