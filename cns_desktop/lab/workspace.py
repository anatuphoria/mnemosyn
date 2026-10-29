from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QComboBox, QMenu, QMessageBox, QToolBar, QToolButton
from shiboken6 import isValid

from cns_lab.files import EXTENSION, FileError, read, write

from .brain_overlay import LabBrain
from .charts import LabCharts
from .circuit import CircuitView
from .document import DAY, LabDocument
from .experiments_panel import ExperimentsPanel
from .inspector import Inspector
from .model_panel import ModelPanel
from .timeline import Timeline
from .why_panel import WhyPanel

TICK_MS = 30
SPEEDS = (0.5, 1.0, 2.0, 4.0)
LENGTHS = (("6 h", 360.0), ("1 d", DAY), ("3 d", 3 * DAY), ("1 w", 7 * DAY), ("4 w", 28 * DAY),
           ("8 w", 56 * DAY))
STATUS_HINT = "Space plays, drag a change to move it"
RECENT_KEY = "lab/recent"
RECENT_COUNT = 8
FILE_ACTIONS = ("New experiment", "Open", "Save", "Save as")


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


class LabWorkspace:
    def __init__(self, window, model_key: str) -> None:
        self.window = window
        self.document = LabDocument(window.state.atlas, model_key, compute=False)
        doc = self.document
        self.speed = 1.0
        self.playing = False
        self._last_tick = 0.0
        self.timer = QTimer(window, interval=TICK_MS, timeout=self._tick)
        self.experiments = ExperimentsPanel(doc)
        self.model_panel = ModelPanel(doc)
        self.why = WhyPanel(doc)
        self.inspector = Inspector(doc)
        self.timeline = Timeline(doc)
        self.charts = LabCharts(doc)
        self.circuit = CircuitView(doc)
        window.viewport.add_circuit(self.circuit)
        self.brain = LabBrain(doc, window.view, window.viewport, window.state)
        left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        bottom = Qt.DockWidgetArea.BottomDockWidgetArea
        self._docks = {}
        for title, widget, area in (("Experiments", self.experiments, left),
                                    ("Model", self.model_panel, left),
                                    ("Why", self.why, right), ("Inspector", self.inspector, right),
                                    ("Timeline", self.timeline, bottom),
                                    ("Charts", self.charts, bottom)):
            dock = window._dock(title, widget, area)
            dock.setObjectName(f"Lab {title}")
            dock.hide()
            self._docks[title] = dock
        window.tabifyDockWidget(self._docks["Experiments"], self._docks["Model"])
        window.tabifyDockWidget(self._docks["Why"], self._docks["Inspector"])
        window.tabifyDockWidget(self._docks["Timeline"], self._docks["Charts"])
        self.docks = list(self._docks.values())
        self._actions: dict[str, QAction] = {}
        self._build_switch()
        self._build_toolbar()
        self._build_menu()
        self._recent: list[str] = []
        self._build_file_menu()
        for dock in self.docks:
            window.window_menu.insertAction(window.window_separator, dock.toggleViewAction())
        doc.changed.connect(window._update_status)
        doc.undo.cleanChanged.connect(lambda _clean: self.update_title())
        doc.changed.connect(self.update_title)
        doc.wants_longer.connect(self._offer_longer)
        self.inspector.show_in_atlas.connect(self.show_part_in_atlas)
        self.circuit.show_in_atlas.connect(self.show_part_in_atlas)
        self.circuit.show_chart.connect(self.show_chart)
        self.brain.on_show_chart = self.show_chart
        self.brain.on_show_in_atlas = self.show_part_in_atlas
        self.timeline.edit_requested.connect(self._edit_block)
        self._saved = None
        self._set_enabled(False)
        window.workspaces.register_lab(self.docks, self.enter, self.leave)
        for title in ("Experiments", "Why", "Timeline"):
            self._docks[title].raise_()

    def dock(self, title: str):
        return self._docks[title]

    def action(self, name: str) -> QAction:
        return self._actions[name]

    def length_action(self, label: str) -> QAction:
        return self._actions[f"Length {label}"]

    def _add(self, name: str, slot, key: str | None = None, checkable: bool = False) -> QAction:
        action = QAction(name, self.window, triggered=slot, checkable=checkable)
        if key:
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.window.addAction(action)
        self._actions[name] = action
        return action

    def _build_switch(self) -> None:
        bar = self.window.viewport.top_bar.layout()
        self.brain_button = QToolButton(text="Brain", checkable=True, checked=True,
                                        autoRaise=True)
        self.circuit_button = QToolButton(text="Circuit", checkable=True, autoRaise=True)
        self.brain_button.clicked.connect(lambda: self.show_circuit(False))
        self.circuit_button.clicked.connect(lambda: self.show_circuit(True))
        bar.addStretch(1)
        bar.addWidget(self.brain_button)
        bar.addWidget(self.circuit_button)
        bar.addStretch(1)
        self._add("Switch Brain and Circuit", lambda: self.show_circuit(
            not self.window.viewport.showing_circuit), "V")

    def show_circuit(self, shown: bool) -> None:
        self.window.viewport.show_circuit(shown)
        self.brain_button.setChecked(not self.window.viewport.showing_circuit)
        self.circuit_button.setChecked(self.window.viewport.showing_circuit)

    def _build_toolbar(self) -> None:
        doc = self.document
        toolbar = QToolBar("Lab", self.window)
        toolbar.setObjectName("Lab toolbar")
        self.window.addToolBar(toolbar)
        self.toolbar = toolbar
        toolbar.addAction(self._add("Play or pause", self.toggle_play, "Space"))
        toolbar.addAction(self._add("Back to start", lambda: doc.set_playhead(0.0), "Home"))
        self.speed_box = QComboBox()
        for speed in SPEEDS:
            self.speed_box.addItem(f"{speed:g}×", speed)
        self.speed_box.setCurrentIndex(SPEEDS.index(1.0))
        self.speed_box.currentIndexChanged.connect(
            lambda i: self.set_speed(self.speed_box.itemData(i)))
        self.speed_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        toolbar.addWidget(self.speed_box)
        toolbar.addSeparator()
        undo = doc.undo.createUndoAction(self.window, "Undo")
        redo = doc.undo.createRedoAction(self.window, "Redo")
        for action, key, name in ((undo, "Ctrl+Z", "Undo"), (redo, "Ctrl+Shift+Z", "Redo")):
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.window.addAction(action)
            toolbar.addAction(action)
            self._actions[name] = action
        self._add("Delete selected", self._delete_selected, "Delete")
        toolbar.addSeparator()
        compare = self._add("Compare with normal", self._compare, checkable=True)
        compare.setChecked(True)
        toolbar.addAction(compare)
        toolbar.addAction(self._add("Take snapshot", doc.take_snapshot))
        self._add("Clear snapshot", doc.clear_snapshot)
        toolbar.addSeparator()
        self.system_box = QComboBox()
        for model in self.window.state.atlas.models.values():
            self.system_box.addItem(model.name, model.key)
        self.system_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.system_box.activated.connect(
            lambda i: self.choose_system(self.system_box.itemData(i)))
        toolbar.addWidget(self.system_box)
        toolbar.addAction(self._add("What this model includes", self.show_scope))
        self.length_box = QComboBox()
        for label, minutes in LENGTHS:
            self.length_box.addItem(label, minutes)
            self._add(f"Length {label}", lambda _=False, m=minutes: doc.set_length(m))
        self.length_box.setCurrentIndex(1)
        self.length_box.activated.connect(lambda i: doc.set_length(self.length_box.itemData(i)))
        self.length_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        doc.changed.connect(self._sync_length)
        toolbar.addWidget(self.length_box)
        toolbar.hide()

    def _sync_length(self) -> None:
        index = self.length_box.findData(self.document.experiment.length)
        self.length_box.blockSignals(True)
        self.length_box.setCurrentIndex(index)
        self.length_box.blockSignals(False)

    def _build_menu(self) -> None:
        menu = QMenu("Experiment", self.window)
        self.add_menu = menu.addMenu("Add at the playhead")
        self._fill_add_menu()
        menu.addAction(self._actions["Delete selected"])
        lengths = menu.addMenu("Run length")
        for label, _minutes in LENGTHS:
            lengths.addAction(self._actions[f"Length {label}"])
        menu.addSeparator()
        for name in ("Compare with normal", "Take snapshot", "Clear snapshot",
                     "What this model includes"):
            menu.addAction(self._actions[name])
        self.experiment_menu = menu
        self.window.menuBar().insertMenu(self.window.window_menu.menuAction(), menu)
        menu.menuAction().setVisible(False)

    def _fill_add_menu(self) -> None:
        self.add_menu.clear()
        model = self.document.model
        for key, name in [(e.key, e.name) for e in model.experiments] + [
                (t.key, t.name) for t in model.tests]:
            self.add_menu.addAction(QAction(name, self.add_menu, triggered=lambda _=False, k=key:
                                            self.document.add_block(k, self.document.playhead)))

    def model_for_route(self, route: str) -> str | None:
        return next((m.key for m in self.window.state.atlas.models.values() if m.route == route),
                    None)

    def choose_system(self, key: str) -> None:
        doc = self.document
        if key != doc.model.key and self.confirm_discard():
            active = self.brain.active
            if active:
                self.brain.deactivate()
            doc.set_model(key)
            self._fill_add_menu()
            if active:
                self.brain.activate()
            self.update_title()
            self.window._update_status()
        self.system_box.setCurrentIndex(self.system_box.findData(doc.model.key))

    def _set_enabled(self, on: bool) -> None:
        for name, action in self._actions.items():
            if name not in FILE_ACTIONS:
                action.setEnabled(on)
        if on:
            self._actions["Undo"].setEnabled(self.document.undo.canUndo())
            self._actions["Redo"].setEnabled(self.document.undo.canRedo())

    def enter(self) -> None:
        self._saved = self.window._snapshot()
        self.document.ensure_run()
        self.window.viewport.show_lab_parts(True)
        self.toolbar.show()
        self.experiment_menu.menuAction().setVisible(True)
        self._set_enabled(True)
        self.brain.activate()
        self.window._update_status()

    def leave(self) -> None:
        self.pause()
        self.brain.deactivate()
        self.window.viewport.show_lab_parts(False)
        self.brain_button.setChecked(True)
        self.circuit_button.setChecked(False)
        self.toolbar.hide()
        self.experiment_menu.menuAction().setVisible(False)
        self._set_enabled(False)
        if self._saved is not None:
            self.window._restore(*self._saved)
            self._saved = None

    def rate(self) -> float:
        start, end = self.timeline.span
        return (end - start) / 20.0 * self.speed

    def set_speed(self, speed: float) -> None:
        self.speed = float(speed)

    def play(self) -> None:
        if self.document.playhead >= self.document.experiment.length:
            self.document.set_playhead(0.0)
        self.playing = True
        self._last_tick = time.perf_counter()
        self.timer.start()

    def pause(self) -> None:
        self.playing = False
        self.timer.stop()

    def toggle_play(self) -> None:
        self.pause() if self.playing else self.play()

    def advance(self, seconds: float) -> None:
        doc = self.document
        target = doc.playhead + self.rate() * seconds
        doc.set_playhead(target)
        if target >= doc.experiment.length:
            self.pause()

    def _tick(self) -> None:
        now = time.perf_counter()
        self.advance(now - self._last_tick)
        self._last_tick = now

    def _compare(self, on: bool) -> None:
        self.timeline.compare = on
        self.charts.set_compare(on)

    def _delete_selected(self) -> None:
        selection = self.document.selection
        if selection and selection[0] == "block":
            self.document.delete_block(selection[1])

    def _edit_block(self, index: int) -> None:
        self.document.select(("block", index))
        self._docks["Inspector"].raise_()

    def _offer_longer(self, minutes: float) -> None:
        answer = self.window.ask("Longer run", "This change takes weeks to show its effect. "
                                 "Make the run four weeks long?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.document.set_length(minutes)

    def scope_text(self) -> str:
        found = self.window.state.atlas.lab_text(self.document.model.key, "scope")
        if not found:
            return ""
        text, references = found
        lines = [text]
        if references:
            lines += ["", "References"]
            lines += [f"{n}. {ref.citation()}" for n, ref in enumerate(references, 1)]
        return "\n".join(lines)

    def show_scope(self) -> None:
        self.window.inform("What this model includes", self.scope_text())

    def show_chart(self, _key: str = "") -> None:
        self._docks["Charts"].show()
        self._docks["Charts"].raise_()

    def show_part_in_atlas(self, key: str) -> None:
        part = self.document.model.part(key)
        self.show_circuit(False)
        if part.structure is not None and part.structure in self.window.state.atlas:
            self.window.state.select(part.structure)
            self.window.view.frame_selection()
        self.document.select(("part", key))

    def status_text(self) -> str:
        doc = self.document
        changes = _count(len(doc.experiment.blocks), "change", "changes")
        values = _count(len(doc.experiment.values), "value edited", "values edited")
        return f"{doc.model.name} · healthy adult   │   {changes} · {values}   │   {STATUS_HINT}"

    def _build_file_menu(self) -> None:
        window = self.window
        menu = QMenu("File", window)
        window.menuBar().insertMenu(window.menuBar().actions()[0], menu)
        for name, key, slot in (("New experiment", "Ctrl+N", self.new),
                                ("Open", "Ctrl+O", self.open),
                                ("Save", "Ctrl+S", self.save),
                                ("Save as", "Ctrl+Shift+S", self.save_as)):
            menu.addAction(self._add(name, slot, key))
        self.recent_menu = menu.addMenu("Open recent")
        self.file_menu = menu
        settings = window.settings
        if settings is not None:
            stored = settings.value(RECENT_KEY, [])
            self._recent = [str(p) for p in (stored if isinstance(stored, list) else [stored])
                            if p]
        self._fill_recent()

    def set_files_enabled(self, on: bool) -> None:
        for name in FILE_ACTIONS:
            self._actions[name].setEnabled(on)
        self.recent_menu.setEnabled(on and bool(self._recent))

    def recent_files(self) -> list[Path]:
        return [Path(p) for p in self._recent]

    def _remember(self, path: Path) -> None:
        text = str(path)
        self._recent = [text, *[p for p in self._recent if p != text]][:RECENT_COUNT]
        if self.window.settings is not None:
            self.window.settings.setValue(RECENT_KEY, self._recent)
        self._fill_recent()

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        for text in self._recent:
            path = Path(text)
            self.recent_menu.addAction(QAction(path.name, self.recent_menu,
                                               triggered=lambda _=False, p=path: self.open(p)))
        self.recent_menu.setEnabled(bool(self._recent))

    def update_title(self) -> None:
        window, doc = self.window, self.document
        if not (isValid(window) and isValid(doc.undo)):
            return
        title = window.base_title
        if doc.path is not None or doc.is_modified():
            title += f" · {doc.path.name if doc.path else 'Untitled experiment'}[*]"
        window.setWindowTitle(title)
        window.setWindowModified(doc.is_modified())

    def confirm_discard(self) -> bool:
        if not self.document.is_modified():
            return True
        buttons = (QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                   | QMessageBox.StandardButton.Cancel)
        answer = self.window.ask("Unsaved experiment",
                                 "Save the changes to this experiment first?", buttons)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new(self) -> None:
        if self.confirm_discard():
            self.document.new()
            self.window.workspaces.switch("Lab")
            self.update_title()

    def open(self, path: Path | None = None) -> None:
        if not self.confirm_discard():
            return
        path = path or self.window.pick_open()
        if not path:
            return
        path = Path(path)
        try:
            experiment, report = read(path, self.window.state.atlas.models)
        except FileError as exc:
            self.window.inform("Cannot open the experiment", str(exc))
            return
        self.document.load(experiment, path)
        self._remember(path)
        self.window.workspaces.switch("Lab")
        if report:
            self.window.inform("Opened with changes", "\n".join(report))
        self.update_title()

    def _write(self, path: Path) -> bool:
        path = Path(path)
        if path.suffix != EXTENSION:
            path = path.with_suffix(EXTENSION)
        try:
            write(path, self.document.experiment)
        except OSError as exc:
            self.window.inform("Cannot save the experiment", str(exc))
            return False
        self.document.path = path
        self.document.undo.setClean()
        self._remember(path)
        self.update_title()
        return True

    def save(self) -> bool:
        if self.document.path is None:
            return self.save_as()
        return self._write(self.document.path)

    def save_as(self) -> bool:
        path = self.window.pick_save()
        return bool(path) and self._write(path)
