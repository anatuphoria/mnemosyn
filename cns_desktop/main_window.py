from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QMessageBox

from cns_atlas import DISCLAIMER, Atlas
from cns_study.answers import AnswerIndex
from cns_study.items import group_items, items, structure_items, with_reviewed_entries
from cns_study.progress import ProgressStore
from cns_study.session import QuizChoice, Session, utc_now

from .state import AppState
from .views.activity_chart import ActivityChart
from .views.brain_view import BrainView
from .views.info_panel import InfoPanel
from .views.progress_dialog import ProgressDialog
from .views.quiz_panel import QuizPanel
from .views.quiz_setup import QuizSetup
from .views.slice_panel import SlicePanel
from .views.structure_tree import StructureTree

APP_NAME = "Mnemosyn"
APP_FOLDER = "mnemosyn"
OLD_FOLDER = "cns-atlas"
HOVER_MS = 1500
QUIZ_LOCKED = ("Hide", "Isolate", "Show all", "Start quiz")
RECOVERED = {
    "damaged": ("Progress file damaged", "Your progress file could not be read. It was kept as "
                "{path} and a new one was started."),
    "newer": ("Progress file from a newer version", "Your progress file was written by a newer "
              "version of Mnemosyn. It was kept as {path} and a new one was started."),
}


def default_progress_path(base: Path | None = None) -> Path:
    if base is None:
        location = QStandardPaths.StandardLocation.GenericDataLocation
        base = Path(QStandardPaths.writableLocation(location))
    path = base / APP_FOLDER / "progress.sqlite"
    old = base / OLD_FOLDER / "progress.sqlite"
    if old.exists() and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            source = old.with_name(old.name + suffix)
            if source.exists():
                source.replace(path.with_name(path.name + suffix))
    return path


def gpu_name(view: BrainView) -> str:
    for line in view.ren_win.ReportCapabilities().splitlines():
        if "OpenGL renderer string" in line:
            return line.split(":", 1)[1].strip().split(" (")[0]
    return "unknown GPU"


def about_text(atlas: Atlas) -> str:
    sources = [*atlas.sources.values()]
    rows = "".join(f"<li>{escape(s.citation())} Licence: {escape(s.licence)}.</li>"
                   for s in sources)
    name = escape(str(atlas.metadata.get("name", "")))
    version = escape(str(atlas.metadata.get("version", "")))
    return (f"<h3>{APP_NAME}</h3><p>{escape(DISCLAIMER)}</p>"
            f"<p>Atlas package: {name} {version}</p>"
            f"<h4>Data sources</h4><ul>{rows}</ul>")


class MainWindow(QMainWindow):
    def __init__(self, atlas: Atlas, progress_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {atlas.metadata.get('name', 'atlas')}")
        self.resize(1500, 900)
        self.state = AppState(atlas)
        self.progress_path = progress_path or default_progress_path()
        self._store: ProgressStore | None = None
        self._answers: AnswerIndex | None = None
        self._saved: tuple | None = None
        self.recovery_box: QMessageBox | None = None
        self.quiz_active = False
        self.shortcuts: dict[str, QAction] = {}

        self.view = BrainView(self.state, self)
        self.setCentralWidget(self.view)
        self.tree = StructureTree(self.state)
        self.slices = SlicePanel(self.state)
        self.info = InfoPanel(self.state)
        self.chart = ActivityChart(self.state)
        self.quiz = QuizPanel(self.state)
        left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        self.tree_dock = self._dock("Structures", self.tree, left)
        self.slice_dock = self._dock("Slices", self.slices, right)
        self.info_dock = self._dock("Info", self.info, right)
        self.chart_dock = self._dock("Activity", self.chart, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.quiz_dock = self._dock("Quiz", self.quiz, left)
        self.quiz_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.quiz_dock.hide()
        self.splitDockWidget(self.slice_dock, self.info_dock, Qt.Orientation.Horizontal)
        self.resizeDocks([self.tree_dock, self.slice_dock, self.info_dock], [250, 420, 300],
                         Qt.Orientation.Horizontal)
        self.resizeDocks([self.chart_dock], [180], Qt.Orientation.Vertical)

        self._add_actions()
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(QLabel(f"GPU: {gpu_name(self.view)}"))
        self.slices.hovered.connect(self._show_hover)
        self.quiz.finished.connect(self.leave_quiz)
        self.quiz.centre_requested.connect(self.slices.centre_on_selection)
        self.state.selection_changed.connect(lambda _: self._update_status())
        self.state.visibility_changed.connect(lambda _: self._update_status())
        self._status_timer = QTimer(self, interval=250, timeout=self._update_status)
        self._status_timer.start()

        default = next((s.id for s in atlas.structures
                        if s.name.startswith("Hippocampus") and atlas.has_mesh(s.id)), None)
        self.state.select(default)

    def _dock(self, title: str, widget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _add_actions(self) -> None:
        toolbar = self.addToolBar("View")
        toolbar.setObjectName("View")

        def action(text: str, key: str, slot) -> None:
            act = QAction(f"{text}  ({key})", self, shortcut=QKeySequence(key), triggered=slot)
            act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            toolbar.addAction(act)
            self.shortcuts[text] = act

        action("Hide", "H", self._hide_selected)
        action("Isolate", "I", self._isolate_selected)
        action("Show all", "U", self.state.show_all)
        action("Reset view", "R", self.view.reset_view)
        action("Centre slice", "C", self.slices.centre_on_selection)
        action("About", "F1", self.show_about)
        focus_filter = QAction(self, shortcut=QKeySequence.StandardKey.Find,
                               triggered=lambda: self.tree.filter_box.setFocus())
        self.addAction(focus_filter)
        study = self.menuBar().addMenu("Study")
        start = QAction("Start quiz  (Q)", self, shortcut=QKeySequence("Q"),
                        triggered=self.open_quiz_setup)
        start.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        study.addAction(start)
        study.addAction(QAction("Progress", self, triggered=self.show_progress))
        self.shortcuts["Start quiz"] = start

    def _show_hover(self, name: str) -> None:
        if self.quiz_active:
            return
        if name:
            self.statusBar().showMessage(name, HOVER_MS)
        else:
            self.statusBar().clearMessage()

    def progress_store(self) -> ProgressStore:
        if self._store is None:
            name = str(self.state.atlas.metadata.get("name", "atlas"))
            self._store = ProgressStore(self.progress_path, name)
            if self._store.recovered_from is not None:
                title, text = RECOVERED[self._store.recovery_reason]
                self.recovery_box = QMessageBox(
                    QMessageBox.Icon.Warning, title, text.format(path=self._store.recovered_from),
                    QMessageBox.StandardButton.Ok, self)
                self.recovery_box.open()
        return self._store

    def answer_index(self) -> AnswerIndex:
        if self._answers is None:
            atlas = self.state.atlas
            self._answers = AnswerIndex(structure_items(atlas) + group_items(atlas))
        return self._answers

    def open_quiz_setup(self) -> QuizSetup:
        self.slices.label_centres()
        dialog = QuizSetup(self.state.atlas, self.progress_store(), self)
        dialog.accepted.connect(lambda: self.start_quiz(dialog.choice()))
        dialog.open()
        return dialog

    def show_progress(self) -> ProgressDialog:
        dialog = ProgressDialog(self.state.atlas, self.progress_store(), self)
        dialog.open()
        return dialog

    def start_quiz(self, choice: QuizChoice, rng: random.Random | None = None,
                   now: Callable[[], datetime] = utc_now) -> None:
        atlas = self.state.atlas
        pool = items(atlas, choice.level)
        chosen = items(atlas, choice.level, choice.scope)
        if choice.mode == "flashcard":
            chosen = with_reviewed_entries(atlas, chosen)
        rng = rng or random.Random()
        session = Session(chosen, choice.mode, self.progress_store(), choice.practice, now=now,
                          rng=rng)
        self.enter_quiz()
        self.quiz.start(session, choice.mode, self.answer_index(), pool, rng)

    def _quiz_locked(self) -> list[QAction]:
        docks = (self.tree_dock, self.info_dock, self.chart_dock)
        return [*(self.shortcuts[name] for name in QUIZ_LOCKED),
                *(dock.toggleViewAction() for dock in docks)]

    def enter_quiz(self) -> None:
        if self.quiz_active:
            return
        state = self.state
        hidden = [i for i in state.geometry_ids if state.is_hidden(i)]
        self._saved = (self.saveState(), hidden, state.selected, state.slice_axis, state.slice_mm,
                       [(w, w.focusPolicy()) for w in (self.view, self.slices.view)])
        self.quiz_active = True
        for action in self._quiz_locked():
            action.setEnabled(False)
        state.show_all()
        for widget, _ in self._saved[5]:
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree_dock.hide()
        self.info_dock.hide()
        self.chart_dock.hide()
        self.quiz_dock.show()
        self.statusBar().clearMessage()
        self._update_status()

    def leave_quiz(self) -> None:
        if not self.quiz_active:
            return
        layout, hidden, selected, axis, mm, focus = self._saved
        self.quiz_active = False
        for action in self._quiz_locked():
            action.setEnabled(True)
        for widget, policy in focus:
            widget.setFocusPolicy(policy)
        self.restoreState(layout)
        self.state.show_all()
        self.state.set_hidden(hidden, True)
        self.state.select(selected)
        self.state.set_slice(axis, mm)
        self._update_status()

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {APP_NAME}", about_text(self.state.atlas))

    def show_disclaimer(self) -> QMessageBox:
        box = QMessageBox(QMessageBox.Icon.Information, "Before you start", DISCLAIMER,
                          QMessageBox.StandardButton.Ok, self)
        box.open()
        return box

    def _hide_selected(self) -> None:
        if self.state.selected:
            self.state.set_hidden(self.state.geometry_in(self.state.selected), True)

    def _isolate_selected(self) -> None:
        if self.state.selected:
            self.state.isolate(self.state.selected)

    def _update_status(self) -> None:
        if self.quiz_active:
            self.status.setText(f"quiz in progress   │   last frame: "
                                f"{self.view.last_render_ms:.1f} ms   │   Esc ends the quiz")
            return
        selected = self.state.selected
        name = self.state.atlas.get(selected).name if selected else "-"
        total = len(self.state.geometry_ids)
        shown = sum(not self.state.is_hidden(i) for i in self.state.geometry_ids)
        self.status.setText(
            f"selected: {name}   │   visible: {shown}/{total}   │   "
            f"last frame: {self.view.last_render_ms:.1f} ms   │   "
            "drag rotate · right-drag/wheel zoom · middle/shift-drag pan · click select")

    def closeEvent(self, event) -> None:
        if self.quiz_active:
            self.quiz.stop()
        self._status_timer.stop()
        if self._store is not None:
            self._store.close()
        self.view.close()
        super().closeEvent(event)
