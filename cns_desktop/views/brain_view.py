from __future__ import annotations

import time

from pyvistaqt import QtInteractor
from vtkmodules.vtkRenderingCore import vtkActor, vtkPropPicker

from ..state import AppState

BACKGROUND = "#0a0a10"
CLICK_TOLERANCE_PX = 3


def _lighten(rgb: tuple[int, int, int], amount: float) -> tuple[float, float, float]:
    return tuple((c + (255 - c) * amount) / 255 for c in rgb)


class BrainView(QtInteractor):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent, auto_update=False)
        self.state = state
        self.set_background(BACKGROUND)
        self._actors: dict[str, vtkActor] = {}
        self._id_by_actor: dict[str, str] = {}
        self._highlighted: str | None = None
        for s in state.atlas.structures.values():
            actor = self.add_mesh(s.mesh, color=s.color, smooth_shading=True,
                                  specular=0.15, name=s.id, reset_camera=False)
            self._actors[s.id] = actor
            self._id_by_actor[actor.GetAddressAsString("vtkActor")] = s.id
        self.reset_view()

        self._picker = vtkPropPicker()
        self._press_pos: tuple[int, int] | None = None
        self.iren.add_observer("LeftButtonPressEvent", self._on_press)
        self.iren.add_observer("LeftButtonReleaseEvent", self._on_release)

        self.last_render_ms = 0.0
        self._render_started = 0.0
        self.ren_win.AddObserver("StartEvent", self._on_render_start)
        self.ren_win.AddObserver("EndEvent", self._on_render_end)

        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(self._on_visibility_changed)

    def reset_view(self) -> None:
        """World frame: x right, y up, z front."""
        self.camera_position = [(-3.0, 1.0, 1.8), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        self.reset_camera()
        self.render()

    def _event_pos(self) -> tuple[int, int]:
        return self.iren.interactor.GetEventPosition()

    def _on_press(self, *_):
        self._press_pos = self._event_pos()

    def _on_release(self, *_):
        if self._press_pos is None:
            return
        (x0, y0), (x1, y1) = self._press_pos, self._event_pos()
        self._press_pos = None
        if abs(x1 - x0) <= CLICK_TOLERANCE_PX and abs(y1 - y0) <= CLICK_TOLERANCE_PX:
            self.pick_at(x1, y1)

    def structure_at(self, x: int, y: int) -> str | None:
        """VTK display coords: origin is bottom-left."""
        if not self._picker.PickProp(x, y, self.renderer):
            return None
        actor = self._picker.GetActor()
        return self._id_by_actor.get(actor.GetAddressAsString("vtkActor")) if actor else None

    def pick_at(self, x: int, y: int) -> None:
        sid = self.structure_at(x, y)
        if sid is not None:
            self.state.select(sid)

    def _paint(self, sid: str, selected: bool) -> None:
        prop = self._actors[sid].GetProperty()
        color = self.state.atlas.structures[sid].color
        prop.SetColor(_lighten(color, 0.45) if selected else tuple(c / 255 for c in color))
        prop.SetAmbient(0.35 if selected else 0.0)

    def _on_selection_changed(self, sid: str | None) -> None:
        if self._highlighted is not None:
            self._paint(self._highlighted, False)
        if sid is not None:
            self._paint(sid, True)
        self._highlighted = sid
        self.render()

    def _on_visibility_changed(self, ids: frozenset[str]) -> None:
        for sid in ids:
            self._actors[sid].SetVisibility(not self.state.is_hidden(sid))
        self.render()

    def _on_render_start(self, *_):
        self._render_started = time.perf_counter()

    def _on_render_end(self, *_):
        self.last_render_ms = (time.perf_counter() - self._render_started) * 1000
