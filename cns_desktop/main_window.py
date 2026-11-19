from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import QEvent, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QFileDialog,
                               QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QWidget)

from shiboken6 import delete

from cns_atlas import Atlas
from cns_atlas.lesions import prepare as prepare_lesions
from cns_study.answers import AnswerIndex
from cns_study.progress import ProgressStore

from . import preferences
from .design import dialogs, widgets
from .design.panels import PanelGroup
from .design.theme import set_role
from .design.tokens import GAP, SIZE
from .design.topbar import TopBar
from .lab.viewport import Viewport
from .lab.workspace import LabWorkspace
from .lesion.workspace import LesionWorkspace
from .state import AppState
from .views.activity_chart import ActivityChart
from .views.brain_view import BrainView
from .views.info_panel import InfoPanel
from .views.pathway_panel import PathwayPanel
from .views.quiz_panel import QuizPanel
from .views.slice_panel import SlicePanel
from .views.structure_tree import StructureTree
from .warm_up import WarmUp
from .window_menus import WindowMenus
from .window_lessons import LessonMode
from .window_quiz import QuizMode
from .window_routes import RouteMode
from .workspaces import Workspaces

APP_NAME = "Mnemosyn"
APP_FOLDER = "mnemosyn"
OLD_FOLDER = "cns-atlas"
HOVER_MS = 1500
GREY_DIMMED = 0.15
MOUSE_HINT = "drag rotates · right drag pans · wheel zooms · click selects"
KEYS = {
    "explore": (("F", "frame"), ("H", "hide"), ("I", "isolate"), ("Q", "quiz")),
    "pathway": (("Space", "play"), ("←", "back"), ("→", "next"), ("Esc", "close")),
    "quiz": (("Esc", "end the quiz"),),
    "lab": (("Space", "play"), ("V", "brain or circuit"), ("Del", "remove change")),
}
ARROW_WIDGETS = (QAbstractSlider, QAbstractItemView, QAbstractSpinBox)
FIRST_DRAW_WAIT_MS = 250


def data_folder() -> Path:
    location = QStandardPaths.StandardLocation.GenericDataLocation
    return Path(QStandardPaths.writableLocation(location))


def default_progress_path(base: Path | None = None) -> Path:
    return (base or data_folder()) / APP_FOLDER / "progress.sqlite"


def migrate_progress(base: Path | None = None) -> None:
    base = base or data_folder()
    path = default_progress_path(base)
    old = base / OLD_FOLDER / "progress.sqlite"
    if not old.exists() or path.exists():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("-wal", "-shm", ""):
            source = old.with_name(old.name + suffix)
            if source.exists():
                source.replace(path.with_name(path.name + suffix))
    except OSError:
        return


def gpu_name(view: BrainView) -> str:
    for line in view.ren_win.ReportCapabilities().splitlines():
        if "OpenGL renderer string" in line:
            return line.split(":", 1)[1].strip().split(" (")[0]
    return "unknown GPU"


class MainWindow(WindowMenus, QuizMode, RouteMode, LessonMode, QMainWindow):
    def __init__(self, atlas: Atlas, progress_path: Path | None = None, settings=None) -> None:
        super().__init__()
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks
                            | QMainWindow.DockOption.AllowNestedDocks)
        title = f"{APP_NAME}: {atlas.metadata.get('name', 'atlas')}"
        if atlas.local_only:
            title += " (local build, not for sharing)"
        self.base_title = title
        self.setWindowTitle(title)
        self.resize(*SIZE["window"])
        self.state = AppState(atlas)
        self.progress_path = progress_path or default_progress_path()
        self._store: ProgressStore | None = None
        self._answers: AnswerIndex | None = None
        self._saved: tuple | None = None
        self.recovery_box: QMessageBox | None = None
        self.quiz_active = False
        self.pathway_active = False
        self._pathway_saved: tuple | None = None
        self._route_camera: tuple | None = None
        self._route_painted: dict[int, tuple] = {}
        self.shortcuts: dict[str, QAction] = {}

        self.settings = settings
        self.topbar = TopBar(self)
        self.setMenuWidget(self.topbar)
        self.view = BrainView(self.state, self)
        self.viewport = Viewport(self.view)
        self.setCentralWidget(self.viewport)
        self.tree = StructureTree(self.state)
        self.slices = SlicePanel(self.state)
        self.info = InfoPanel(self.state)
        self.info.structure_linked.connect(self.follow_link)
        self.chart = ActivityChart(self.state)
        self.quiz = QuizPanel(self.state)
        self.pathways = PathwayPanel(self.state, hold=self._held)
        left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        self.structures_group = self._group("Structures", self.tree, left)
        self.routes_group = PanelGroup("Pathways", [
            ("routes", "Routes", self.pathways.routes_page),
            ("steps", "Steps", self.pathways.steps_page)], self)
        self.addDockWidget(left, self.routes_group)
        self.pathways.setParent(self)
        self.pathways.hide()
        self.slices_group = self._group("Slices", self.slices, right)
        self.info_group = self._group("Info", self.info, right)
        self.step_panel = self.pathways.step_panel
        self.step_panel.details.structure_linked.connect(self.follow_link)
        self.pathways.steps_page.narrow_details.structure_linked.connect(self.follow_link)
        self.step_group = self._group("Step", self.step_panel, right)
        self.step_group.hide()
        self.step_group.visibilityChanged.connect(
            lambda shown: self.pathways.set_narrow(not shown))
        self.activity_group = self._group("Activity", self.chart,
                                          Qt.DockWidgetArea.BottomDockWidgetArea)
        self.quiz_group = self._group("Quiz", self.quiz, left)
        self.quiz_group.setFeatures(PanelGroup.DockWidgetFeature.DockWidgetMovable)
        self.quiz_group.hide()
        self.tree_dock, self.pathway_dock = self.structures_group, self.routes_group
        self.slice_dock, self.info_dock = self.slices_group, self.info_group
        self.chart_dock, self.quiz_dock = self.activity_group, self.quiz_group
        self.routes_group.hide()
        self.splitDockWidget(self.slices_group, self.info_group, Qt.Orientation.Horizontal)
        self._sync_chart()

        self._add_actions()
        self.workspaces = Workspaces(self, settings)
        self._add_window_menu()
        self._add_help_menu()
        self._add_lesson_menu()
        self._add_settings_action()
        narrow = {"Explore": [("Structures", "Info"), ("Structures", "Slices")],
                  "Slices": [("Structures", "Info")],
                  "Pathways": [("Pathways", "Info"), ("Pathways", "Slices")]}
        self.workspaces.capture_defaults({"Explore": self._arrange_explore,
                                          "Slices": self._arrange_slices,
                                          "Pathways": self._arrange_pathways}, narrow)
        self.ask = lambda title, text, buttons: dialogs.ask(self, title, text, buttons)
        self.inform = lambda title, text: dialogs.inform(self, title, text)
        self.pick_open = lambda: QFileDialog.getOpenFileName(
            self, "Open experiment", "", "Lab experiments (*.mnemolab)")[0]
        self.pick_save = lambda: QFileDialog.getSaveFileName(
            self, "Save experiment", "", "Lab experiments (*.mnemolab)")[0]
        self.lab = LabWorkspace(self, next(iter(atlas.models))) if atlas.models else None
        if self.lab is not None:
            preferences.load_timeline(settings, self.lab.timeline)
        lesions = any(p.texts == "lesion" for p in atlas.pathways)
        self.lesion = LesionWorkspace(self) if lesions else None
        if self.lesion is not None:
            self.lesion.deficits.structure_linked.connect(self.follow_link)
            self.lesion.deficits.route_requested.connect(self.open_route_step)
        for kind in ARROW_WIDGETS:
            for widget in self.findChildren(kind):
                widget.installEventFilter(self)
        self.status = widgets.ElidedLabel()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().setFixedHeight(SIZE["status"])
        self.status_keys = QWidget()
        QHBoxLayout(self.status_keys).setContentsMargins(0, 0, GAP["small"], 0)
        self.status_keys.layout().setSpacing(GAP["tight"])
        self._shown_keys: tuple = ()
        self.statusBar().addPermanentWidget(self.status_keys)
        self.topbar.tidy_menus()
        self.slices.hovered.connect(self._show_hover)
        self.quiz.finished.connect(self.leave_quiz)
        self.quiz.centre_requested.connect(self.slices.centre_on_selection)
        self.quiz.find_target.connect(self._prefer_in_slices)
        self.quiz.frame_target.connect(self._frame_quiz_target)
        self.quiz.lab_requested.connect(self.open_quiz_in_lab)
        self.quiz.laid_out.connect(lambda: QTimer.singleShot(0, self.fit_quiz_column))
        self.quiz.dim_grey.connect(
            lambda dim: self.view.set_grey_opacity(GREY_DIMMED if dim else 1.0))
        self.pathways.entered.connect(self.enter_pathway)
        self.pathways.lab_requested.connect(self.open_lab)
        self.pathways.left.connect(self.leave_pathway)
        self.pathways.centre_requested.connect(self.slices.centre_on_selection)
        self.pathways.timeline_changed.connect(self._on_timeline)
        self.pathways.step_drawn.connect(self._paint_route)
        self.pathways.show_tab.connect(self.routes_group.show_page)
        self.pathways.route_opened.connect(self._show_step_tab)
        self.pathways.route_opened.connect(self._frame_route)
        self.pathways.time_changed.connect(self.chart.set_time)
        self.chart.seek_requested.connect(self.pathways.seek)
        self.pathway_dock.visibilityChanged.connect(self._prepare_pathways)
        self.state.selection_changed.connect(lambda _: self._update_status())
        self.state.visibility_changed.connect(lambda _: self._update_status())
        self._status_timer = QTimer(self, interval=250, timeout=self._update_status)
        self._status_timer.start()

        default = next((s.id for s in atlas.structures
                        if s.name.startswith("Hippocampus") and atlas.has_mesh(s.id)), None)
        self.state.select(default)
        self.view.setFocus()
        self._warm_up = WarmUp(self._warm_up_jobs(), self)
        self._first_draw = None

    def _warm_up_jobs(self) -> list:
        atlas = self.state.atlas
        volumes = [*atlas.volumes, *atlas.templates.values(), *atlas.fills.values()]
        jobs = [lambda v=v: v.data for v in volumes]
        jobs += [lambda v=v: self.slices.warm(v) for v in atlas.volumes]
        jobs += [lambda i=i: self.info.warm(i) for i in (1, 2, 3) if i in atlas]
        ids = self.view.ids + self.view.shell_ids
        jobs += [lambda c=ids[k:k + 40]: self.view.warm_outline(c) for k in range(0, len(ids), 40)]
        jobs.append(lambda: self.view.warm_outline(ids))
        if self.lesion is not None:
            jobs += [lambda v=v: prepare_lesions(v) for v in atlas.volumes]
        if self.lab is not None:
            experiment = self.lab.document.experiment
            jobs.append(lambda: self.lab.document.simulator.normal(experiment.length,
                                                                   experiment.start_clock))
        return jobs

    @property
    def warm_up_done(self) -> bool:
        return self._warm_up.done

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.viewport.fit(self.workspaces.current if hasattr(self, "workspaces") else "Explore",
                          event.size().width())
        if hasattr(self, "workspaces"):
            self.workspaces.width_changed(event.oldSize().width(), event.size().width())
        old, new = event.oldSize().width(), event.size().width()
        if (getattr(self, "quiz_active", False) and old > 0
                and (old < SIZE["narrow"]) != (new < SIZE["narrow"])):
            self._arrange_quiz(new)

    def showEvent(self, event) -> None:
        if not getattr(self, "_fitted", False):
            self._fitted = True
            self.workspaces.fit_to_width()
        super().showEvent(event)
        if self._warm_up.started_after_render is None and self._first_draw is None:
            self._first_draw = self.view.ren_win.AddObserver("EndEvent", self._after_first_draw)
            QTimer.singleShot(FIRST_DRAW_WAIT_MS, self, self._after_first_draw)

    def _after_first_draw(self, *_) -> None:
        if self._warm_up.started_after_render is None and self.view.ren_win is not None:
            self.view.ren_win.RemoveObserver(self._first_draw)
            self._warm_up.start(self.view.render_count)

    def _group(self, title: str, widget, area: Qt.DockWidgetArea) -> PanelGroup:
        group = PanelGroup(title, [(title.lower(), title, widget)], self)
        self.addDockWidget(area, group)
        return group

    def open_lab(self, route: str) -> None:
        if self.lab is None:
            return
        self.pathways.leave()
        key = self.lab.model_for_route(route)
        if key is not None:
            self.lab.choose_system(key)
        self.workspaces.switch("Lab")

    def _sides(self, left: PanelGroup, right: list[PanelGroup]) -> None:
        self.resizeDocks([left, *right], [SIZE["panel_left"], *[SIZE["panel_right"]] * len(right)],
                         Qt.Orientation.Horizontal)

    def _arrange_explore(self) -> list[tuple[str, str]]:
        self.structures_group.show()
        self.routes_group.hide()
        self.step_group.hide()
        self._sides(self.structures_group, [self.info_group])
        return [("Info", "Slices")]

    def _arrange_slices(self) -> list[tuple[str, str]]:
        self.structures_group.show()
        self.routes_group.hide()
        self.step_group.hide()
        self.slices_group.show()
        self.info_group.show()
        width, side = self.width(), SIZE["panel_left"]
        wide = width >= SIZE["narrow"]
        central = SIZE["central_min_slices"] if wide else 0
        info = side if wide else 0
        slices = max(SIZE["central_min"], width - side - central - info)
        self.resizeDocks([self.structures_group, self.slices_group, self.info_group],
                         [side, slices, side], Qt.Orientation.Horizontal)
        return []

    def _arrange_pathways(self) -> list[tuple[str, str]]:
        self.structures_group.hide()
        self.routes_group.show()
        if self.width() < SIZE["narrow"]:
            self.step_group.hide()
            self._sides(self.routes_group, [])
            return []
        self.step_group.show()
        self._sides(self.routes_group, [self.step_group])
        return [("Step", "Info"), ("Step", "Slices")]

    def workspace_docks(self) -> list[PanelGroup]:
        return [self.structures_group, self.routes_group, self.slices_group, self.info_group,
                self.step_group]

    def _out_of_lab(self) -> None:
        if self.workspaces.current in self.workspaces.extra:
            self.workspaces.switch("Explore")

    def before_layout(self, name: str) -> None:
        self.viewport.fit(name, self.width())

    def _order_tabs(self) -> None:
        bar = [w for w in self.topbar.findChildren(QWidget)
               if w.isVisible() and w.isEnabled() and w.focusPolicy() & Qt.FocusPolicy.TabFocus]
        for first, second in pairwise(bar):
            QWidget.setTabOrder(first, second)
        if bar:
            QWidget.setTabOrder(bar[-1], self.view)

    def sync_after_layout(self, name: str) -> None:
        self._order_tabs()
        self.viewport.fit(name, self.width())
        if self.viewport.isHidden():
            if self.slices.view.isVisible():
                self.slices.view.setFocus()
        elif self.isActiveWindow():
            self.view.setFocus()
        self._sync_chart()

    def _show_hover(self, name: str) -> None:
        if self.quiz_active:
            return
        if name:
            self.statusBar().showMessage(name, HOVER_MS)
        else:
            self.statusBar().clearMessage()

    def _prefer_in_slices(self, ids) -> None:
        self.slices.preferred = frozenset(ids)
        self.view.set_preferred(ids)

    def open_route_step(self, key: str, side: str, index: int) -> bool:
        pathway = next((p for p in self.state.atlas.pathways if p.key == key), None)
        if pathway is None:
            return False
        self.workspaces.switch("Pathways")
        self.pathways.open(pathway.key, side)
        self.pathways.go(min(index, len(pathway.steps) - 1))
        return True

    def follow_link(self, structure_id: int) -> None:
        if structure_id not in self.state.atlas:
            return
        self.state.set_hidden([i for i in self.state.geometry_in(structure_id)
                               if not self.state.is_tract(i)], False)
        if self.lesion is not None and self.lesion.place.active:
            self.lesion.place.select_quietly(structure_id)
        else:
            self.state.select(structure_id)
        self.view.frame_selection()

    def frame(self) -> None:
        if self.slices.layer is not None and self.slices.view.underMouse():
            self.slices.fit_volume()
        else:
            self.view.frame_selection()

    def _hide_selected(self) -> None:
        if self.state.selected:
            self.state.set_hidden(self.state.geometry_in(self.state.selected), True)

    def _isolate_selected(self) -> None:
        if self.state.selected:
            self.state.isolate(self.state.selected)

    def _show_keys(self, context: str) -> None:
        keys = KEYS[context]
        if keys == self._shown_keys:
            return
        self._shown_keys = keys
        row = self.status_keys.layout()
        while row.count():
            item = row.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        for key, meaning in keys:
            cap = widgets.key_cap(key)
            label = QLabel(meaning)
            set_role(label, "secondary")
            for widget in (cap, label):
                row.addWidget(widget)
                widget.show()
            row.addSpacing(GAP["small"])

    def _update_status(self) -> None:
        if self.quiz_active:
            self.status.setText("quiz in progress")
            self._show_keys("quiz")
            return
        if self.lab is not None and self.workspaces.current == "Lab":
            self.status.setText(self.lab.status_text())
            self._show_keys("lab")
            return
        panel = self.pathways
        if self.pathway_active and panel.pathway is not None:
            self.status.setText(
                f"pathway: {panel.pathway.name}"
                f"{f' ({panel.side})' if panel.pathway.sides == 'one' else ''}   │   "
                f"step {panel.index + 1} of {len(panel.pathway.steps)}")
            self._show_keys("pathway")
            return
        selected = self.state.selected
        name = self.state.atlas.get(selected).name if selected else "none"
        self.status.setText(f"selected: {name}   │   {MOUSE_HINT}")
        self._show_keys("explore")

    def eventFilter(self, watched, event) -> bool:
        if (event.type() == QEvent.Type.ShortcutOverride
                and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)):
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:
        if self.lesson_window is not None and not self.lesson_window.close():
            event.ignore()
            return
        if self.lab is not None and not self.lab.confirm_discard():
            event.ignore()
            return
        self._warm_up.stop()
        if self.quiz_active:
            self.quiz.stop()
            self.leave_quiz()
        self.workspaces.save()
        if self.lab is not None:
            preferences.save_timeline(self.settings, self.lab.timeline)
        if self.settings is not None:
            self.settings.sync()
        self._status_timer.stop()
        self.pathways.pause()
        if self.lab is not None:
            self.lab.pause()
        if self._store is not None:
            self._store.close()
        self.view.close()
        # A closed window can outlive its close, so its GL context is freed now. pyvistaqt keeps
        # Python handles to Qt's context and surface; they are dropped first so none goes stale.
        forget = getattr(self.view, "_forget_context", None)
        if forget is not None:
            forget()
        delete(self.view)
        super().closeEvent(event)
