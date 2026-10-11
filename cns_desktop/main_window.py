from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QMessageBox

from cns_atlas import DISCLAIMER, Atlas

from .state import AppState
from .views.activity_chart import ActivityChart
from .views.brain_view import BrainView
from .views.info_panel import InfoPanel
from .views.slice_panel import SlicePanel
from .views.structure_tree import StructureTree

HOVER_MS = 1500


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
    return (f"<h3>CNS Atlas</h3><p>{escape(DISCLAIMER)}</p>"
            f"<p>Atlas package: {name} {version}</p>"
            f"<h4>Data sources</h4><ul>{rows}</ul>")


class MainWindow(QMainWindow):
    def __init__(self, atlas: Atlas) -> None:
        super().__init__()
        self.setWindowTitle(f"CNS Atlas - {atlas.metadata.get('name', 'atlas')}")
        self.resize(1500, 900)
        self.state = AppState(atlas)

        self.view = BrainView(self.state, self)
        self.setCentralWidget(self.view)
        self.tree = StructureTree(self.state)
        self.slices = SlicePanel(self.state)
        self.info = InfoPanel(self.state)
        self.chart = ActivityChart(self.state)
        tree_dock = self._dock("Structures", self.tree, Qt.DockWidgetArea.LeftDockWidgetArea)
        slice_dock = self._dock("Slices", self.slices, Qt.DockWidgetArea.RightDockWidgetArea)
        info_dock = self._dock("Info", self.info, Qt.DockWidgetArea.RightDockWidgetArea)
        chart_dock = self._dock("Activity", self.chart, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.splitDockWidget(slice_dock, info_dock, Qt.Orientation.Horizontal)
        self.resizeDocks([tree_dock, slice_dock, info_dock], [250, 420, 300],
                         Qt.Orientation.Horizontal)
        self.resizeDocks([chart_dock], [180], Qt.Orientation.Vertical)

        self._add_actions()
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(QLabel(f"GPU: {gpu_name(self.view)}"))
        self.slices.hovered.connect(self._show_hover)
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

        action("Hide", "H", self._hide_selected)
        action("Isolate", "I", self._isolate_selected)
        action("Show all", "U", self.state.show_all)
        action("Reset view", "R", self.view.reset_view)
        action("Centre slice", "C", self.slices.centre_on_selection)
        action("About", "F1", self.show_about)
        focus_filter = QAction(self, shortcut=QKeySequence.StandardKey.Find,
                               triggered=lambda: self.tree.filter_box.setFocus())
        self.addAction(focus_filter)

    def _show_hover(self, name: str) -> None:
        if name:
            self.statusBar().showMessage(name, HOVER_MS)
        else:
            self.statusBar().clearMessage()

    def show_about(self) -> None:
        QMessageBox.about(self, "About CNS Atlas", about_text(self.state.atlas))

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
        selected = self.state.selected
        name = self.state.atlas.get(selected).name if selected else "-"
        total = len(self.state.geometry_ids)
        shown = sum(not self.state.is_hidden(i) for i in self.state.geometry_ids)
        self.status.setText(
            f"selected: {name}   │   visible: {shown}/{total}   │   "
            f"last frame: {self.view.last_render_ms:.1f} ms   │   "
            "drag rotate · right-drag/wheel zoom · middle/shift-drag pan · click select")

    def closeEvent(self, event) -> None:
        self._status_timer.stop()
        self.view.close()
        super().closeEvent(event)
