from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from PySide6.QtCore import Qt



from .design.tokens import rgb

ROUTE_DIM = 0.55
ROUTE_KEYS = ("Play or pause", "Back", "Next")
PATHWAY_LOCKED = ("Hide", "Isolate", "Show all", "Tracts")


class RouteMode:
    def _prepare_pathways(self, shown: bool) -> None:
        if shown and self.state.atlas.pathways:
            self.slices.label_centres()
            self.view.prepare_tracts()

    @contextmanager
    def _held(self):
        with self.view.held(), self.slices.held():
            yield

    def route_bounds(self) -> tuple[float, ...]:
        ids = [i for ids in self.pathways.lights for i in ids if i in self.view.blocks]
        if not ids:
            return tuple(self.view.scene_bounds)
        extents = [self.view.extent_of(i) for i in ids]
        low = np.min([e[0] for e in extents], axis=0)
        high = np.max([e[1] for e in extents], axis=0)
        return (low[0], high[0], low[1], high[1], low[2], high[2])

    def _paint_route(self, *_args) -> None:
        panel = self.pathways
        if panel.pathway is None:
            return
        accent = tuple(c / 255 for c in rgb("accent"))
        back = rgb("s0")
        wanted: dict[int, tuple] = {}
        for n, ids in enumerate(panel.lights):
            if n == panel.index:
                continue
            for i in ids:
                if n < panel.index:
                    wanted[i] = accent
                else:
                    own = self.state.atlas.get(i).rgb_triplet
                    wanted[i] = tuple((o + (b - o) * ROUTE_DIM) / 255 for o, b in zip(own, back))
        for i in panel.lights[panel.index] if panel.lights else ():
            wanted.pop(i, None)
        changes = {i: c for i, c in wanted.items() if self._route_painted.get(i) != c}
        changes.update({i: None for i in self._route_painted if i not in wanted})
        self._route_painted = wanted
        if changes:
            self.view.set_lab_colors(changes)

    def _show_step_tab(self) -> None:
        if self.step_group.isVisible():
            self.step_group.show_page("step")

    def _frame_route(self) -> None:
        self.view.set_plane_shown(False)
        self.view.set_home(self.route_bounds(), 0)
        self.view.reset_view(render=False)

    def enter_pathway(self) -> None:
        self._pathway_saved = self._snapshot()
        camera = self.view.renderer.GetActiveCamera()
        self._route_camera = (self.view.camera_position.to_list(), camera.GetViewAngle(),
                              self.view.plane_shown())
        self.pathway_active = True
        for name in PATHWAY_LOCKED:
            self.shortcuts[name].setEnabled(False)
        self.shortcuts["Close route"].setEnabled(True)
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
        self.shortcuts["Close route"].setEnabled(False)
        with self._held():
            self.view.set_lab_colors({i: None for i in self._route_painted})
            self._route_painted = {}
            self.view.set_home(None)
            if self._route_camera is not None:
                position, angle, plane = self._route_camera
                self.view.camera_position = position
                self.view.renderer.GetActiveCamera().SetViewAngle(angle)
                self.view.set_plane_shown(plane)
                self._route_camera = None
            self.state.set_focus(None)
            self._restore(*self._pathway_saved)
        for name in ROUTE_KEYS:
            self.shortcuts[name].setEnabled(False)
        self._sync_chart()
        self._update_status()

    def _on_timeline(self, timeline) -> None:
        self.chart.show_timeline(timeline, self.pathways.pathway.name if self.pathways.pathway
                                 else "")
        self.step_panel.set_timeline_note(self.chart.note_html())
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
