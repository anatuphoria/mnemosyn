from __future__ import annotations

import random
from contextlib import contextmanager
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QCheckBox,
                               QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QWidget)

from shiboken6 import delete

from cns_atlas import DISCLAIMER, Atlas
from cns_study.answers import AnswerIndex
from cns_study.items import (group_items, items, structure_items, tract_items,
                             with_reviewed_entries)
from cns_study.progress import ProgressStore
from cns_study.session import QuizChoice, Session, utc_now

from .design import widgets
from .design.panels import PanelGroup
from .design.theme import set_role
from .design.tokens import SIZE
from .design.topbar import TopBar
from .lab.viewport import Viewport
from .lab.workspace import LabWorkspace
from .state import AppState
from .views.about_dialog import AboutDialog
from .views.activity_chart import ActivityChart
from .views.brain_view import BrainView
from .views.info_panel import InfoPanel
from .views.pathway_panel import PathwayPanel
from .views.progress_dialog import ProgressDialog
from .views.quiz_panel import QuizPanel
from .views.quiz_setup import QuizSetup
from .views.slice_panel import SlicePanel
from .views.structure_tree import StructureTree
from .warm_up import WarmUp
from .workspaces import Workspaces

APP_NAME = "Mnemosyn"
APP_FOLDER = "mnemosyn"
OLD_FOLDER = "cns-atlas"
HOVER_MS = 1500
GREY_DIMMED = 0.15
MOUSE_HINT = "drag rotates · right drag pans · wheel zooms · click selects"
GUIDE_URL = "https://mnemo.saeed.cool/guide/"
KEYS = {
    "explore": (("F", "frame"), ("H", "hide"), ("I", "isolate"), ("Q", "quiz")),
    "pathway": (("Space", "play"), ("←", "back"), ("→", "next"), ("Esc", "leave")),
    "quiz": (("Esc", "end the quiz"),),
    "lab": (("Space", "play"), ("V", "brain or circuit"), ("Del", "remove change")),
}
QUIZ_LOCKED = ("Hide", "Isolate", "Show all", "Start quiz", "Tracts")
ARROW_WIDGETS = (QAbstractSlider, QAbstractItemView, QAbstractSpinBox)
ROUTE_KEYS = ("Play or pause", "Back", "Next")
PATHWAY_LOCKED = ("Hide", "Isolate", "Show all", "Tracts")
RECOVERED = {
    "damaged": ("Progress file damaged", "Your progress file could not be read. It was kept as "
                "{path} and a new one was started."),
    "newer": ("Progress file from a newer version", "Your progress file was written by a newer "
              "version of Mnemosyn. It was kept as {path} and a new one was started."),
}
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


class MainWindow(QMainWindow):
    def __init__(self, atlas: Atlas, progress_path: Path | None = None, settings=None) -> None:
        super().__init__()
        title = f"{APP_NAME}: {atlas.metadata.get('name', 'atlas')}"
        if atlas.local_only:
            title += " (local build, not for sharing)"
        self.base_title = title
        self.setWindowTitle(title)
        self.resize(1500, 900)
        self.state = AppState(atlas)
        self.progress_path = progress_path or default_progress_path()
        self._store: ProgressStore | None = None
        self._answers: AnswerIndex | None = None
        self._saved: tuple | None = None
        self.recovery_box: QMessageBox | None = None
        self.quiz_active = False
        self.pathway_active = False
        self._pathway_saved: tuple | None = None
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
        self.chart = ActivityChart(self.state)
        self.quiz = QuizPanel(self.state)
        self.pathways = PathwayPanel(self.state, hold=self._held)
        left, right = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        self.structures_group = self._group("Structures", self.tree, left)
        self.routes_group = self._group("Pathways", self.pathways, left)
        self.slices_group = self._group("Slices", self.slices, right)
        self.info_group = self._group("Info", self.info, right)
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
        narrow = {"Explore": [("Structures", "Info"), ("Structures", "Slices")],
                  "Slices": [("Structures", "Info")],
                  "Pathways": [("Pathways", "Info"), ("Pathways", "Slices")]}
        self.workspaces.capture_defaults({"Explore": self._arrange_explore,
                                          "Slices": self._arrange_slices,
                                          "Pathways": self._arrange_pathways}, narrow)
        self.ask = lambda title, text, buttons: QMessageBox.question(self, title, text, buttons)
        self.inform = lambda title, text: QMessageBox.information(self, title, text)
        self.pick_open = lambda: QFileDialog.getOpenFileName(
            self, "Open experiment", "", "Lab experiments (*.mnemolab)")[0]
        self.pick_save = lambda: QFileDialog.getSaveFileName(
            self, "Save experiment", "", "Lab experiments (*.mnemolab)")[0]
        self.lab = LabWorkspace(self, next(iter(atlas.models))) if atlas.models else None
        for kind in ARROW_WIDGETS:
            for widget in self.findChildren(kind):
                widget.installEventFilter(self)
        self.status = widgets.ElidedLabel()
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().setFixedHeight(SIZE["status"])
        self.status_keys = QWidget()
        QHBoxLayout(self.status_keys).setContentsMargins(0, 0, 8, 0)
        self.status_keys.layout().setSpacing(4)
        self._shown_keys: tuple = ()
        self.statusBar().addPermanentWidget(self.status_keys)
        self.topbar.tidy_menus()
        self.slices.hovered.connect(self._show_hover)
        self.quiz.finished.connect(self.leave_quiz)
        self.quiz.centre_requested.connect(self.slices.centre_on_selection)
        self.quiz.find_target.connect(self._prefer_in_slices)
        self.quiz.dim_grey.connect(
            lambda dim: self.view.set_grey_opacity(GREY_DIMMED if dim else 1.0))
        self.pathways.entered.connect(self.enter_pathway)
        self.pathways.lab_requested.connect(self.open_lab)
        self.pathways.left.connect(self.leave_pathway)
        self.pathways.centre_requested.connect(self.slices.centre_on_selection)
        self.pathways.timeline_changed.connect(self._on_timeline)
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
        self.topbar.set_compact(event.size().width() < SIZE["narrow"])
        self.viewport.fit(self.workspaces.current if hasattr(self, "workspaces") else "Explore",
                          event.size().width())
        if hasattr(self, "workspaces"):
            self.workspaces.width_changed(event.oldSize().width(), event.size().width())

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

    def _add_actions(self) -> None:
        view = self.topbar.menu("View")

        def action(text: str, key: str, slot, menu=view) -> QAction:
            act = QAction(text, self, shortcut=QKeySequence(key), triggered=slot)
            act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.addAction(act)
            menu.addAction(act)
            self.shortcuts[text] = act
            return act

        action("Hide", "H", self._hide_selected)
        action("Isolate", "I", self._isolate_selected)
        action("Show all", "U", self.state.show_all)
        view.addSeparator()
        action("Tracts", "T", self.state.toggle_tracts)
        view.addSeparator()
        action("Reset view", "R", self.view.reset_view)
        action("Frame selection", "F", self.frame)
        action("Centre slice", "C", self.slices.centre_on_selection)
        focus_filter = QAction(self, shortcut=QKeySequence.StandardKey.Find,
                               triggered=lambda: self.tree.filter_box.setFocus())
        self.addAction(focus_filter)
        study = self.topbar.menu("Study")
        action("Start quiz", "Q", self.open_quiz_setup, study)
        study.addAction(QAction("Progress", self, triggered=self.show_progress))
        icons = {"Hide": "eye-off", "Isolate": "scan", "Show all": "eye", "Tracts": "waypoints",
                 "Start quiz": "graduation-cap"}

        def buttons(names):
            return [None if name is None else widgets.icon_button(self.shortcuts[name],
                                                                  icons[name])
                    for name in names]

        full = ("Hide", "Isolate", "Show all", None, "Tracts", None, "Start quiz")
        self.topbar.add_group("Explore", buttons(full))
        self.topbar.add_group("Slices", buttons(full))
        self.topbar.add_group("Pathways", buttons(("Tracts", None, "Start quiz")))
        for name, icon in (("Frame selection", "maximize"), ("Reset view", "rotate-ccw")):
            self.viewport.add_tool(widgets.icon_button(self.shortcuts[name], icon))
        self.viewport.add_tool(buttons(("Tracts",))[0])
        leave = QAction("Leave pathway", self, shortcut=QKeySequence("Esc"),
                        triggered=self.pathways.leave)
        leave.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        leave.setEnabled(False)
        self.addAction(leave)
        self.shortcuts["Leave pathway"] = leave
        for name, key, slot in (("Play or pause", "Space", self.pathways.toggle_play),
                                ("Back", "Left", self.pathways.back),
                                ("Next", "Right", self.pathways.next)):
            route_key = QAction(name, self, shortcut=QKeySequence(key), triggered=slot)
            route_key.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            route_key.setEnabled(False)
            self.addAction(route_key)
            self.shortcuts[name] = route_key

    def _add_window_menu(self) -> None:
        self.window_menu = self.topbar.menu("Window")
        for dock in (self.structures_group, self.routes_group, self.slices_group,
                     self.info_group, self.activity_group):
            self.window_menu.addAction(dock.toggleViewAction())
        self.window_separator = self.window_menu.addSeparator()
        self.window_menu.addAction(QAction("Reset layout", self,
                                           triggered=lambda: self.workspaces.reset()))

    def _add_help_menu(self) -> None:
        help_menu = self.topbar.menu("Help")
        about = QAction("About Mnemosyn", self, shortcut=QKeySequence("F1"),
                        triggered=self.show_about)
        about.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.addAction(about)
        help_menu.addAction(about)
        self.shortcuts["About"] = about
        help_menu.addAction(QAction("Guide on the website", self, triggered=lambda:
                                    QDesktopServices.openUrl(QUrl(GUIDE_URL))))

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
        self._sides(self.structures_group, [self.info_group])
        return [("Info", "Slices")]

    def _arrange_slices(self) -> list[tuple[str, str]]:
        self.structures_group.show()
        self.routes_group.hide()
        self.slices_group.show()
        self.info_group.show()
        width = max(self.width(), 1500)
        side = SIZE["panel_left"]
        self.resizeDocks([self.structures_group, self.slices_group, self.info_group],
                         [side, width - 2 * side - SIZE["central_min_slices"], side],
                         Qt.Orientation.Horizontal)
        return []

    def _arrange_pathways(self) -> list[tuple[str, str]]:
        self.structures_group.hide()
        self.routes_group.show()
        self._sides(self.routes_group, [self.info_group])
        return [("Info", "Slices")]

    def workspace_docks(self) -> list[PanelGroup]:
        return [self.structures_group, self.routes_group, self.slices_group, self.info_group]

    def _out_of_lab(self) -> None:
        if self.workspaces.current == "Lab":
            self.workspaces.switch("Explore")

    def before_layout(self, name: str) -> None:
        self.viewport.fit(name, self.width())

    def sync_after_layout(self, name: str) -> None:
        self.viewport.fit(name, self.width())
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
            pool = structure_items(atlas) + group_items(atlas) + tract_items(atlas)
            self._answers = AnswerIndex(pool)
        return self._answers

    def open_quiz_setup(self) -> QuizSetup:
        self._out_of_lab()
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
        if self.pathway_active:
            self.pathways.leave()
        self._out_of_lab()
        self.enter_quiz()
        shown = choice.level == "tracts" and choice.mode == "find"
        self.state.set_hidden(self.state.tract_ids, not shown)
        self.quiz.start(session, choice.mode, self.answer_index(), pool, rng)

    def _quiz_locked(self) -> list[QAction]:
        docks = (self.tree_dock, self.pathway_dock, self.info_dock, self.chart_dock)
        return [*(self.shortcuts[name] for name in QUIZ_LOCKED),
                *(dock.toggleViewAction() for dock in docks)]

    def enter_quiz(self) -> None:
        if self.quiz_active:
            return
        state = self.state
        self._saved = (self.saveState(), *self._snapshot(),
                       [(w, w.focusPolicy()) for w in (self.view, self.slices.view)],
                       self.workspaces.joins())
        self.workspaces.release_joins()
        self.quiz_active = True
        self.workspaces.set_locked(True)
        if self.lab is not None:
            self.lab.set_files_enabled(False)
        for action in self._quiz_locked():
            action.setEnabled(False)
        state.set_hidden([i for i in state.geometry_ids if not state.is_tract(i)], False)
        for widget, _ in self._saved[6]:
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree_dock.hide()
        self.pathway_dock.hide()
        self.info_dock.hide()
        self.chart_dock.hide()
        self.quiz_dock.show()
        self.statusBar().clearMessage()
        self._update_status()

    def leave_quiz(self) -> None:
        if not self.quiz_active:
            return
        layout, hidden, selected, axis, mm, volume, focus, joins = self._saved
        self.quiz_active = False
        self.workspaces.set_locked(False)
        if self.lab is not None:
            self.lab.set_files_enabled(True)
        for action in self._quiz_locked():
            action.setEnabled(True)
        for widget, policy in focus:
            widget.setFocusPolicy(policy)
        self.workspaces.release_joins()
        self.restoreState(layout)
        self.workspaces.apply_joins(joins)
        self._restore(hidden, selected, axis, mm, volume)
        self._sync_chart()
        self._update_status()

    def _snapshot(self) -> tuple:
        state = self.state
        hidden = [i for i in state.geometry_ids if state.is_hidden(i)]
        return hidden, state.selected, state.slice_axis, state.slice_mm, state.slice_volume

    def _restore(self, hidden, selected, axis, mm, volume="") -> None:
        self.state.select(selected)
        kept = set(hidden)
        self.state.set_hidden([i for i in self.state.geometry_ids if i not in kept], False)
        self.state.set_hidden(hidden, True)
        if volume:
            self.state.set_slice_volume(volume)
        self.state.set_slice(axis, mm)

    def _prepare_pathways(self, shown: bool) -> None:
        if shown and self.state.atlas.pathways:
            self.slices.label_centres()
            self.view.prepare_tracts()

    @contextmanager
    def _held(self):
        with self.view.held(), self.slices.held():
            yield

    def enter_pathway(self) -> None:
        self._pathway_saved = self._snapshot()
        self.pathway_active = True
        for name in PATHWAY_LOCKED:
            self.shortcuts[name].setEnabled(False)
        self.shortcuts["Leave pathway"].setEnabled(True)
        self._sync_chart()
        for name in ROUTE_KEYS:
            self.shortcuts[name].setEnabled(True)
        self._update_status()

    def leave_pathway(self) -> None:
        if not self.pathway_active:
            return
        self.pathway_active = False
        for name in PATHWAY_LOCKED:
            self.shortcuts[name].setEnabled(True)
        self.shortcuts["Leave pathway"].setEnabled(False)
        with self._held():
            self.state.set_focus(None)
            self._restore(*self._pathway_saved)
        for name in ROUTE_KEYS:
            self.shortcuts[name].setEnabled(False)
        self._sync_chart()
        self._update_status()

    def _on_timeline(self, timeline) -> None:
        self.chart.show_timeline(timeline, self.pathways.pathway.name if self.pathways.pathway
                                 else "")
        self._sync_chart()

    def chart_wanted(self) -> bool:
        return (self.pathway_active and not self.quiz_active
                and self.pathways.timeline is not None)

    def _sync_chart(self) -> None:
        wanted = self.chart_wanted()
        self.chart_dock.toggleViewAction().setEnabled(wanted)
        if wanted and self.chart_dock.isHidden():
            self.chart_dock.show()
            self.resizeDocks([self.chart_dock], [self.height() // 3], Qt.Orientation.Vertical)
        elif not wanted:
            self.chart_dock.hide()

    def frame(self) -> None:
        if self.slices.layer is not None and self.slices.view.underMouse():
            self.slices.fit_volume()
        else:
            self.view.frame_selection()

    def show_about(self) -> None:
        AboutDialog(self.state.atlas, self).exec()

    def show_disclaimer(self) -> QMessageBox:
        box = QMessageBox(QMessageBox.Icon.Information, "Before you start", DISCLAIMER,
                          QMessageBox.StandardButton.Ok, self)
        box.setCheckBox(QCheckBox("Don't show this again", box))
        box.open()
        return box

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
            row.addSpacing(8)

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
        if self.lab is not None and not self.lab.confirm_discard():
            event.ignore()
            return
        self.workspaces.save()
        if self.settings is not None:
            self.settings.sync()
        self._warm_up.stop()
        if self.quiz_active:
            self.quiz.stop()
        self._status_timer.stop()
        self.pathways.pause()
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
