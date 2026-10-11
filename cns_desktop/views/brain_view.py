from __future__ import annotations

import time

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet
from vtkmodules.vtkRenderingCore import (vtkActor, vtkCompositeDataDisplayAttributes,
                                         vtkCompositePolyDataMapper, vtkHardwarePicker)

from ..lod import choose_lod, face_totals
from ..slices import AXIS_INDEX
from ..state import AppState

BACKGROUND = "#0a0a10"
CLICK_TOLERANCE_PX = 3
HIGHLIGHT = 0.45
PLANE_OPACITY = 0.18


def _rgb(color) -> tuple[float, float, float]:
    return tuple(c / 255 for c in color)


def _lighten(color, amount: float) -> tuple[float, float, float]:
    return tuple((c + (255 - c) * amount) / 255 for c in color)


def _polydata(mesh) -> pv.PolyData:
    poly = pv.PolyData.from_regular_faces(np.asarray(mesh.vertices, dtype=np.float32),
                                          np.asarray(mesh.faces, dtype=np.int64))
    normals = numpy_to_vtk(np.asarray(mesh.normals, dtype=np.float32), deep=True)
    poly.GetPointData().SetNormals(normals)
    return poly


def _composite(blocks: list[pv.PolyData]):
    data = vtkMultiBlockDataSet()
    data.SetNumberOfBlocks(len(blocks))
    for index, block in enumerate(blocks):
        data.SetBlock(index, block)
    mapper = vtkCompositePolyDataMapper()
    mapper.SetInputDataObject(data)
    mapper.ScalarVisibilityOff()
    attributes = vtkCompositeDataDisplayAttributes()
    mapper.SetCompositeDataDisplayAttributes(attributes)
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetInterpolationToGouraud()
    prop.SetSpecular(0.15)
    return actor, mapper, attributes


class BrainView(QtInteractor):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent, auto_update=False)
        self.state = state
        self.set_background(BACKGROUND)
        self.ids = list(state.geometry_ids)
        self.lod = choose_lod(face_totals(state.atlas, self.ids))
        self.blocks = {i: _polydata(state.atlas.mesh(i, self.lod)) for i in self.ids}
        blocks = [self.blocks[i] for i in self.ids]
        self.actor, self.composite_mapper, self.attributes = _composite(blocks)
        for structure_id in self.ids:
            block = self.blocks[structure_id]
            self.attributes.SetBlockColor(block, _rgb(state.atlas.get(structure_id).rgb_triplet))
            self.attributes.SetBlockVisibility(block, True)
        self.renderer.AddActor(self.actor)
        self.scene_bounds = self._scene_bounds()
        self.highlighted: list[int] = []
        self.overlay: vtkActor | None = None
        self.overlay_ids: list[int] = []
        self.plane = self.add_mesh(pv.Plane(), color="white", opacity=PLANE_OPACITY,
                                   pickable=False, reset_camera=False, lighting=False)

        self._picker = vtkHardwarePicker()
        self._press_pos: tuple[int, int] | None = None
        self.iren.add_observer("LeftButtonPressEvent", self._on_press)
        self.iren.add_observer("LeftButtonReleaseEvent", self._on_release)

        self.last_render_ms = 0.0
        self.render_count = 0
        self._render_started = 0.0
        self.ren_win.AddObserver("StartEvent", self._on_render_start)
        self.ren_win.AddObserver("EndEvent", self._on_render_end)

        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(self._on_visibility_changed)
        state.slice_changed.connect(self._on_slice_changed)
        self.reset_view()
        self._on_slice_changed(state.slice_axis, state.slice_mm)

    def reset_view(self) -> None:
        """World frame is MNI millimetres: x right, y anterior, z superior."""
        self.camera_position = [(-400.0, 250.0, 150.0), (0.0, -18.0, 10.0), (0.0, 0.0, 1.0)]
        self.reset_camera()
        self.render()

    def is_drawn(self, structure_id: int) -> bool:
        block = self.blocks.get(structure_id)
        return block is not None and bool(self.attributes.GetBlockVisibility(block))

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
        self._picker.Pick(x, y, 0, self.renderer)
        if self._picker.GetActor() is not self.actor:
            return None
        index = self._picker.GetFlatBlockIndex() - 1
        return self.ids[index] if 0 <= index < len(self.ids) else None

    def pick_at(self, x: int, y: int) -> None:
        structure_id = self.structure_at(x, y)
        if structure_id is not None:
            self.state.select(structure_id)

    def _refresh_overlay(self) -> None:
        if self.overlay is not None:
            self.renderer.RemoveActor(self.overlay)
            self.overlay = None
        self.overlay_ids = [i for i in self.highlighted if not self.state.is_hidden(i)]
        if not self.overlay_ids:
            return
        actor, mapper, attributes = _composite([self.blocks[i] for i in self.overlay_ids])
        mapper.SetResolveCoincidentTopologyToPolygonOffset()
        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(-1.0, -1.0)
        for structure_id in self.overlay_ids:
            color = _lighten(self.state.atlas.get(structure_id).rgb_triplet, HIGHLIGHT)
            attributes.SetBlockColor(self.blocks[structure_id], color)
        actor.GetProperty().SetAmbient(0.3)
        actor.SetPickable(False)
        self.overlay = actor
        self.renderer.AddActor(actor)

    def _on_selection_changed(self, structure_id: int | None) -> None:
        self.highlighted = [] if structure_id is None else self.state.geometry_in(structure_id)
        self._refresh_overlay()
        self.render()

    def _on_visibility_changed(self, ids: frozenset[int]) -> None:
        for structure_id in ids:
            block = self.blocks.get(structure_id)
            if block is not None:
                self.attributes.SetBlockVisibility(block, not self.state.is_hidden(structure_id))
        if any(i in ids for i in self.highlighted):
            self._refresh_overlay()
        self.render()

    def _scene_bounds(self) -> tuple[float, ...]:
        volumes = self.state.atlas.volumes
        if not volumes:
            return tuple(self.actor.GetBounds())
        shape, affine = volumes[0].shape, volumes[0].affine
        corners = np.array([[i, j, k, 1.0] for i in (0, shape[0] - 1) for j in (0, shape[1] - 1)
                            for k in (0, shape[2] - 1)])
        world = (np.asarray(affine) @ corners.T)[:3]
        low, high = world.min(axis=1), world.max(axis=1)
        return (low[0], high[0], low[1], high[1], low[2], high[2])

    def _on_slice_changed(self, axis: str, mm: float) -> None:
        bounds = self.scene_bounds
        if not self.state.atlas.volumes or bounds[0] > bounds[1]:
            self.plane.SetVisibility(False)
            return
        center = [(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2,
                  (bounds[4] + bounds[5]) / 2]
        normal = [0.0, 0.0, 0.0]
        a = AXIS_INDEX[axis]
        center[a], normal[a] = mm, 1.0
        size = 1.1 * max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
        plane = pv.Plane(center=center, direction=normal, i_size=size, j_size=size)
        self.plane.GetMapper().SetInputData(plane)
        self.plane.SetVisibility(True)
        self.render()

    def _on_render_start(self, *_):
        self._render_started = time.perf_counter()

    def _on_render_end(self, *_):
        self.render_count += 1
        self.last_render_ms = (time.perf_counter() - self._render_started) * 1000
