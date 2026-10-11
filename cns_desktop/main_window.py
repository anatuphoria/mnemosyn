from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow

from brain_tui.knowledge import KnowledgeBase

from .atlas_data import REPO_ROOT, Atlas
from .state import AppState
from .views.activity_chart import ActivityChart
from .views.brain_view import BrainView
from .views.info_panel import InfoPanel
from .views.structure_tree import StructureTree


def gpu_name(view: BrainView) -> str:
    for line in view.ren_win.ReportCapabilities().splitlines():
        if "OpenGL renderer string" in line:
            return line.split(":", 1)[1].strip().split(" (")[0]
    return "unknown GPU"


class MainWindow(QMainWindow):
    def __init__(self, atlas: Atlas, knowledge: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"CNS Atlas - prototype ({atlas.name})")
        self.resize(1500, 900)
        self.state = AppState(atlas)
        kb = KnowledgeBase(knowledge or os.path.join(REPO_ROOT, "data", "knowledge.json"))

        self.view = BrainView(self.state, self)
        self.setCentralWidget(self.view)
        self.tree = StructureTree(self.state)
        self.info = InfoPanel(self.state, kb)
        self.chart = ActivityChart(self.state)
        tree_dock = self._dock("Structures", self.tree, Qt.DockWidgetArea.LeftDockWidgetArea)
        info_dock = self._dock("Info", self.info, Qt.DockWidgetArea.RightDockWidgetArea)
        chart_dock = self._dock("Activity", self.chart, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.resizeDocks([tree_dock, info_dock], [250, 300], Qt.Orientation.Horizontal)
        self.resizeDocks([chart_dock], [200], Qt.Orientation.Vertical)

        self._add_actions()
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(QLabel(f"GPU: {gpu_name(self.view)}"))
        self.state.selection_changed.connect(lambda _: self._update_status())
        self.state.visibility_changed.connect(lambda _: self._update_status())
        self._status_timer = QTimer(self, interval=250, timeout=self._update_status)
        self._status_timer.start()

        default = next((s.id for s in atlas.structures.values() if s.name == "Hippocampus_L"), None)
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

        action("Hide", "H", self._hide_selected)
        action("Isolate", "I", self._isolate_selected)
        action("Show all", "U", self.state.show_all)
        action("Reset view", "R", self.view.reset_view)
        focus_filter = QAction(self, shortcut=QKeySequence.StandardKey.Find,
                               triggered=lambda: self.tree.filter_box.setFocus())
        self.addAction(focus_filter)

    def _hide_selected(self) -> None:
        if self.state.selected:
            self.state.set_hidden([self.state.selected], True)

    def _isolate_selected(self) -> None:
        if self.state.selected:
            self.state.isolate(self.state.selected)

    def _update_status(self) -> None:
        sel = self.state.selected
        name = self.state.atlas.structures[sel].name if sel else "-"
        shown = sum(not self.state.is_hidden(s) for s in self.state.atlas.structures)
        self.status.setText(
            f"selected: {name}   │   visible: {shown}/{len(self.state.atlas.structures)}   │   "
            f"last frame: {self.view.last_render_ms:.1f} ms   │   "
            "drag rotate · right-drag/wheel zoom · middle/shift-drag pan · click select")

    def closeEvent(self, event) -> None:
        self._status_timer.stop()
        self.view.close()
        super().closeEvent(event)
