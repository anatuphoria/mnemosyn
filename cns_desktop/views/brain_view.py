from __future__ import annotations

import time

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkPropPicker

from ..state import AppState

BACKGROUND = "#0a0a10"
CLICK_TOLERANCE_PX = 3


def _lighten(rgb, amount: float) -> tuple[float, float, float]:
    return tuple((c + (255 - c) * amount) / 255 for c in rgb)


class BrainView(QtInteractor):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent, auto_update=False)
        self.state = state
        self.set_background(BACKGROUND)
        self._actors: dict[int, vtkActor] = {}
        self._id_by_actor: dict[str, int] = {}
        self._highlighted: int | None = None
        for structure_id in state.geometry_ids:
            actor = self._make_actor(structure_id)
            self.renderer.AddActor(actor)
            self._actors[structure_id] = actor
            self._id_by_actor[actor.GetAddressAsString("vtkActor")] = structure_id
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

    def _make_actor(self, structure_id: int) -> vtkActor:
        data = self.state.atlas.mesh(structure_id, lod=0)
        mesh = pv.PolyData.from_regular_faces(np.asarray(data.vertices, dtype=np.float32),
                                              np.asarray(data.faces, dtype=np.int64))
        normals = numpy_to_vtk(np.asarray(data.normals, dtype=np.float32), deep=True)
        mesh.GetPointData().SetNormals(normals)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(mesh)
        mapper.ScalarVisibilityOff()
        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetInterpolationToGouraud()
        prop.SetSpecular(0.15)
        prop.SetColor(tuple(c / 255 for c in self.state.atlas.get(structure_id).rgb_triplet))
        return actor

    def reset_view(self) -> None:
        """World frame is MNI millimetres: x right, y anterior, z superior."""
        self.camera_position = [(-400.0, 250.0, 150.0), (0.0, -18.0, 10.0), (0.0, 0.0, 1.0)]
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

    def structure_at(self, x: int, y: int) -> int | None:
        """VTK display coords: origin is bottom-left."""
        if not self._picker.PickProp(x, y, self.renderer):
            return None
        actor = self._picker.GetActor()
        return self._id_by_actor.get(actor.GetAddressAsString("vtkActor")) if actor else None

    def pick_at(self, x: int, y: int) -> None:
        structure_id = self.structure_at(x, y)
        if structure_id is not None:
            self.state.select(structure_id)

    def _paint(self, structure_id: int, selected: bool) -> None:
        actor = self._actors.get(structure_id)
        if actor is None:
            return
        color = self.state.atlas.get(structure_id).rgb_triplet
        prop = actor.GetProperty()
        prop.SetColor(_lighten(color, 0.45) if selected else tuple(c / 255 for c in color))
        prop.SetAmbient(0.35 if selected else 0.0)

    def _on_selection_changed(self, structure_id: int | None) -> None:
        if self._highlighted is not None:
            self._paint(self._highlighted, False)
        if structure_id is not None:
            self._paint(structure_id, True)
        self._highlighted = structure_id
        self.render()

    def _on_visibility_changed(self, ids: frozenset[int]) -> None:
        for structure_id in ids:
            actor = self._actors.get(structure_id)
            if actor is not None:
                actor.SetVisibility(not self.state.is_hidden(structure_id))
        self.render()

    def _on_render_start(self, *_):
        self._render_started = time.perf_counter()

    def _on_render_end(self, *_):
        self.last_render_ms = (time.perf_counter() - self._render_started) * 1000
