from __future__ import annotations

import time
from contextlib import contextmanager

import numpy as np
import pyvista as pv
from PySide6.QtCore import QTimer
from pyvistaqt import QtInteractor
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance
from vtkmodules.vtkFiltersSources import vtkPlaneSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkHardwarePicker, vtkPolyDataMapper

from ..lod import choose_lod, face_totals
from ..slices import AXIS_INDEX
from ..state import AppState
from .cell_plane import mid_body_plane, side_structure
from .chunks import Chunks
from .navigation import install_navigation
from .outline import OutlineLayer

BACKGROUND = "#0a0a10"
CLICK_TOLERANCE_PX = 3
FAINT = 0.08
PLANE_OPACITY = 0.18
CELL_PLANE_COLOR = (1.0, 0.85, 0.45)
CELL_PLANE_OPACITY = 0.35
SHELL_OPACITY = 0.25


def _rgb(color) -> tuple[float, float, float]:
    return tuple(c / 255 for c in color)


def _polydata(mesh) -> pv.PolyData:
    poly = pv.PolyData.from_regular_faces(np.asarray(mesh.vertices, dtype=np.float32),
                                          np.asarray(mesh.faces, dtype=np.int64))
    normals = numpy_to_vtk(np.asarray(mesh.normals, dtype=np.float32), deep=True)
    poly.GetPointData().SetNormals(normals)
    return poly


def _surface_actor(block: pv.PolyData, color) -> vtkActor:
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(block)
    mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*_rgb(color))
    prop.SetInterpolationToGouraud()
    prop.SetSpecular(0.15)
    return actor


class BrainView(QtInteractor):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent, auto_update=False)
        self.state = state
        self.set_background(BACKGROUND)
        self.shell_ids = [i for i in state.geometry_ids
                          if state.atlas.get(i).kind in ("shell", "cover")]
        self.cover_ids = frozenset(i for i in self.shell_ids
                                   if state.atlas.get(i).kind == "cover")
        self.inside_ids = self._inside_of_covers()
        self.preferred: frozenset[int] = frozenset()
        self._looking = False
        shells = frozenset(self.shell_ids)
        self.ids = [i for i in state.geometry_ids if not state.is_tract(i) and i not in shells]
        self.tract_ids = list(state.tract_ids)
        self._tract_set = frozenset(self.tract_ids)
        self.lod = choose_lod(face_totals(state.atlas, self.ids + self.shell_ids))
        self.blocks = {i: _polydata(state.atlas.mesh(i, self.lod)) for i in self.ids}
        self.chunks = Chunks(self.ids, self.blocks,
                             {i: _rgb(state.atlas.get(i).rgb_triplet) for i in self.ids},
                             {i for i in self.ids if state.is_hidden(i)})
        for actor in self.chunks.actors:
            self.renderer.AddActor(actor)
        self.chunks.apply_focus(state.focus, FAINT)
        self.outline = OutlineLayer(self.ren_win, self.renderer)
        self.outline.add_blocks(self.ids, [self.blocks[i] for i in self.ids])
        self.shell_actors: dict[int, vtkActor] = {}
        self._shell_of: dict[vtkActor, int] = {}
        self._insides: dict[int, vtkImplicitPolyDataDistance] = {}
        for structure_id in self.shell_ids:
            block = self.blocks[structure_id] = _polydata(state.atlas.mesh(structure_id, self.lod))
            actor = _surface_actor(block, state.atlas.get(structure_id).rgb_triplet)
            self.renderer.AddActor(actor)
            self.shell_actors[structure_id] = actor
            self._shell_of[actor] = structure_id
            self._style_shell(structure_id)
        self.outline.add_blocks(self.shell_ids, [self.blocks[i] for i in self.shell_ids])
        self.tract_actors: dict[int, vtkActor] = {}
        self._tract_of: dict[vtkActor, int] = {}
        self.tract_lod: int | None = None
        self.tract_builds = 0
        self._extents: dict[int, tuple] = {}
        self.scene_bounds = self._scene_bounds()
        self.highlighted: list[int] = []
        self.overlay_ids: list[int] = []
        self._plane_key = None
        self.plane = self.add_mesh(pv.Plane(), color="white", opacity=PLANE_OPACITY,
                                   pickable=False, reset_camera=False, lighting=False)
        self.cell_plane_actor: vtkActor | None = None

        self._picker = vtkHardwarePicker()
        self.pick_position = np.zeros(3)
        self._press_pos: tuple[int, int] | None = None
        self.iren.add_observer("LeftButtonPressEvent", self._on_press)
        self.iren.add_observer("LeftButtonReleaseEvent", self._on_release)

        self._holds = 0
        self._render_wanted = False
        self._render_soon = QTimer(self, singleShot=True, interval=0)
        self._render_soon.timeout.connect(self.render)
        self.last_render_ms = 0.0
        self.render_count = 0
        self._render_started = 0.0
        self.ren_win.AddObserver("StartEvent", self._on_render_start)
        self.ren_win.AddObserver("EndEvent", self._on_render_end)

        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(self._on_visibility_changed)
        state.slice_changed.connect(self._on_slice_changed)
        state.slice_volume_changed.connect(
            lambda _name: self._on_slice_changed(state.slice_axis, state.slice_mm))
        state.focus_changed.connect(self._on_focus_changed)
        state.cell_view_changed.connect(self._on_cell_view)
        state.cell_side_changed.connect(lambda _side: self._on_cell_view(state.cell_view))
        self.reset_view()
        self._on_slice_changed(state.slice_axis, state.slice_mm)
        install_navigation(self)

    def _on_cell_view(self, key: str | None) -> None:
        if key is None:
            self.show_cell_plane(None)
            return
        view = next(v for v in self.state.atlas.cell_views() if v.key == key)
        self.show_cell_plane(side_structure(self.state.atlas, view, self.state.cell_side))

    def show_cell_plane(self, structure_id: int | None) -> None:
        mesh = None if structure_id is None else self.state.atlas.mesh(structure_id, 0)
        if mesh is None:
            if self.cell_plane_actor is not None:
                self.cell_plane_actor.SetVisibility(False)
                self._request_render()
            return
        plane = mid_body_plane(mesh.vertices)
        origin = plane.centre - (plane.u + plane.v) * plane.size / 2
        source = vtkPlaneSource()
        source.SetOrigin(*origin)
        source.SetPoint1(*(origin + plane.u * plane.size))
        source.SetPoint2(*(origin + plane.v * plane.size))
        source.Update()
        if self.cell_plane_actor is None:
            mapper = vtkPolyDataMapper()
            self.cell_plane_actor = vtkActor()
            self.cell_plane_actor.SetMapper(mapper)
            self.cell_plane_actor.SetPickable(False)
            prop = self.cell_plane_actor.GetProperty()
            prop.SetColor(*CELL_PLANE_COLOR)
            prop.SetOpacity(CELL_PLANE_OPACITY)
            prop.LightingOff()
            self.renderer.AddActor(self.cell_plane_actor)
        self.cell_plane_actor.GetMapper().SetInputData(source.GetOutput())
        self.cell_plane_actor.SetVisibility(True)
        self._request_render()

    def reset_view(self) -> None:
        """World frame is MNI millimetres: x right, y anterior, z superior."""
        self.camera_position = [(-400.0, 250.0, 150.0), (0.0, -18.0, 10.0), (0.0, 0.0, 1.0)]
        if len(self.state.atlas.volumes) > 1:
            self.reset_camera(render=False, bounds=self.scene_bounds)
        else:
            self.reset_camera()
        self.render()

    @contextmanager
    def held(self):
        self._holds += 1
        try:
            yield
        finally:
            self._holds -= 1
            if not self._holds and self._render_wanted:
                self._render_wanted = False
                self.render()

    def _request_render(self) -> None:
        if self._holds:
            self._render_wanted = True
        else:
            self._render_soon.start()

    def is_drawn(self, structure_id: int) -> bool:
        actor = self.tract_actors.get(structure_id) or self.shell_actors.get(structure_id)
        if actor is not None:
            return bool(actor.GetVisibility())
        return (structure_id in self.blocks and structure_id not in self._tract_set
                and self.chunks.is_visible(structure_id))

    def set_grey_opacity(self, opacity: float) -> None:
        self.chunks.set_opacity(opacity)
        self._request_render()

    def _style_tract(self, structure_id: int) -> None:
        actor = self.tract_actors[structure_id]
        shown = not self.state.is_hidden(structure_id)
        in_focus = self.state.in_focus(structure_id)
        actor.SetVisibility(shown)
        actor.GetProperty().SetOpacity(1.0 if in_focus else FAINT)
        actor.SetPickable(shown and in_focus)

    def _inside_of_covers(self) -> frozenset[int]:
        if not self.cover_ids:
            return frozenset()
        paths = [self.state.atlas.get(i).structure_id_path for i in self.cover_ids]
        common = [ids[0] for ids in zip(*paths) if len(set(ids)) == 1]
        while common:
            inside = frozenset(self.state.geometry_in(common[-1])) - self.cover_ids
            if inside:
                return inside
            common.pop()
        return frozenset()

    def looking_inside(self) -> bool:
        seen = set(self.state.highlighted_ids()) | self.preferred
        return bool(self.inside_ids & seen) or any(
            self.state.is_tract(i) and not self.state.is_hidden(i) for i in self.inside_ids)

    def _update_covers(self) -> None:
        looking = self.looking_inside()
        if looking != self._looking:
            self._looking = looking
            for structure_id in self.cover_ids:
                self._style_shell(structure_id)

    def set_preferred(self, ids) -> None:
        self.preferred = frozenset(ids)
        self._update_covers()
        self._request_render()

    def _style_shell(self, structure_id: int) -> None:
        actor = self.shell_actors[structure_id]
        shown = not self.state.is_hidden(structure_id)
        in_focus = self.state.in_focus(structure_id)
        actor.SetVisibility(shown)
        see_through = structure_id not in self.cover_ids or self._looking
        actor.GetProperty().SetOpacity(
            FAINT if not in_focus else SHELL_OPACITY if see_through else 1.0)
        actor.SetPickable(shown and in_focus)

    def _on_focus_changed(self, _focus) -> None:
        self.chunks.apply_focus(self.state.focus, FAINT)
        for structure_id in self.tract_actors:
            self._style_tract(structure_id)
        for structure_id in self.shell_actors:
            self._style_shell(structure_id)
        self._request_render()

    def warm_outline(self, ids) -> None:
        self.outline.warm(ids)
        try:
            self.ren_win.Render()
        finally:
            self.outline.end_warm()
        self._request_render()

    def prepare_tracts(self) -> None:
        self._ensure_tracts()

    def _ensure_tracts(self) -> None:
        if self.tract_actors or not self.tract_ids:
            return
        atlas = self.state.atlas
        self.tract_lod = choose_lod(face_totals(atlas, self.tract_ids))
        for structure_id in self.tract_ids:
            block = self.blocks[structure_id] = _polydata(atlas.mesh(structure_id, self.tract_lod))
            actor = _surface_actor(block, atlas.get(structure_id).rgb_triplet)
            self.renderer.AddActor(actor)
            self.tract_actors[structure_id] = actor
            self._tract_of[actor] = structure_id
            self._style_tract(structure_id)
        self.tract_builds += 1
        self.outline.add_blocks(self.tract_ids, [self.blocks[i] for i in self.tract_ids])

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

    def _pick(self, x: int, y: int) -> int | None:
        self._picker.Pick(x, y, 0, self.renderer)
        actor = self._picker.GetActor()
        if actor is None:
            return None
        if actor in self.chunks.actors:
            return self.chunks.pick(actor, self._picker.GetFlatBlockIndex())
        return self._tract_of.get(actor, self._shell_of.get(actor))

    def _inside(self, shell_id: int, point: np.ndarray) -> bool:
        if shell_id not in self._insides:
            self._insides[shell_id] = vtkImplicitPolyDataDistance()
            self._insides[shell_id].SetInput(self.blocks[shell_id])
        return self._insides[shell_id].EvaluateFunction(*point) < 0

    def structure_at(self, x: int, y: int) -> int | None:
        """VTK display coords: origin is bottom-left; a shell yields to shapes inside it."""
        found = self._pick(x, y)
        self.pick_position = np.array(self._picker.GetPickPosition())
        if found not in self.shell_actors or found in self.preferred:
            return found
        if found in self.cover_ids and not self._looking:
            return found
        for actor in self.shell_actors.values():
            actor.SetPickable(False)
        behind = self._pick(x, y)
        point = np.array(self._picker.GetPickPosition())
        for structure_id in self.shell_actors:
            self._style_shell(structure_id)
        if found in self.cover_ids:
            if behind not in self.inside_ids:
                return found
        elif behind is None or not self._inside(found, point):
            return found
        self.pick_position = point
        return behind

    def zoom_at(self, x: int, y: int, factor: float) -> None:
        camera = self.renderer.GetActiveCamera()
        position, focal = np.array(camera.GetPosition()), np.array(camera.GetFocalPoint())
        found = self._pick(x, y) is not None
        anchor = np.array(self._picker.GetPickPosition()) if found else focal
        camera.SetPosition(*(anchor + (position - anchor) / factor))
        camera.SetFocalPoint(*(anchor + (focal - anchor) / factor))
        self.renderer.ResetCameraClippingRange()

    def pick_at(self, x: int, y: int) -> None:
        structure_id = self.structure_at(x, y)
        if structure_id is not None:
            self.state.select(structure_id)

    def _refresh_overlay(self) -> None:
        self.overlay_ids = [i for i in self.highlighted
                            if i in self.blocks and not self.state.is_hidden(i)]
        self.outline.show(self.overlay_ids)

    def _on_selection_changed(self, structure_id: int | None) -> None:
        self.highlighted = self.state.highlighted_ids()
        self._update_covers()
        self._refresh_overlay()
        self._request_render()

    def _extent(self, structure_id: int) -> tuple[np.ndarray, np.ndarray]:
        if structure_id not in self._extents:
            block = self.blocks.get(structure_id)
            if block is not None:
                b = block.GetBounds()
                low, high = np.array(b[0::2]), np.array(b[1::2])
            else:
                vertices = np.asarray(self.state.atlas.mesh(structure_id, self.lod).vertices)
                low, high = vertices.min(axis=0), vertices.max(axis=0)
            self._extents[structure_id] = (low, high)
        return self._extents[structure_id]

    def frame_selection(self) -> None:
        shown = [i for i in self.highlighted if i in self.blocks and not self.state.is_hidden(i)]
        if shown:
            extents = [self._extent(i) for i in shown]
            low = np.min([e[0] for e in extents], axis=0)
            high = np.max([e[1] for e in extents], axis=0)
            bounds = (low[0], high[0], low[1], high[1], low[2], high[2])
        else:
            bounds = self.scene_bounds
        self.reset_camera(render=False, bounds=bounds)
        self.render()

    def _on_visibility_changed(self, ids: frozenset[int]) -> None:
        if any(i in self._tract_set and not self.state.is_hidden(i) for i in ids):
            self._ensure_tracts()
        grey = {}
        for structure_id in ids:
            if structure_id in self.tract_actors:
                self._style_tract(structure_id)
            elif structure_id in self.shell_actors:
                self._style_shell(structure_id)
            elif structure_id in self.blocks and structure_id not in self._tract_set:
                grey[structure_id] = self.state.is_hidden(structure_id)
        self.chunks.set_hidden(grey)
        if any(i in ids for i in self.highlighted):
            self._refresh_overlay()
        if self.cover_ids:
            self._update_covers()
        self._request_render()

    def _volume_bounds(self, volume) -> tuple[float, ...]:
        shape, affine = volume.shape, volume.affine
        corners = np.array([[i, j, k, 1.0] for i in (0, shape[0] - 1) for j in (0, shape[1] - 1)
                            for k in (0, shape[2] - 1)])
        world = (np.asarray(affine) @ corners.T)[:3]
        low, high = world.min(axis=1), world.max(axis=1)
        return (low[0], high[0], low[1], high[1], low[2], high[2])

    def _scene_bounds(self) -> tuple[float, ...]:
        volumes = self.state.atlas.volumes
        return self.chunks.bounds() if not volumes else self._volume_bounds(volumes[0])

    def _slice_bounds(self) -> tuple[float, ...]:
        volume = next((v for v in self.state.atlas.volumes if v.name == self.state.slice_volume),
                      None)
        return self.scene_bounds if volume is None else self._volume_bounds(volume)

    def _on_slice_changed(self, axis: str, mm: float) -> None:
        bounds = self._slice_bounds()
        if not self.state.atlas.volumes or bounds[0] > bounds[1]:
            self.plane.SetVisibility(False)
            return
        a = AXIS_INDEX[axis]
        if self._plane_key != (axis, bounds):
            self._plane_key = (axis, bounds)
            center = [(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2,
                      (bounds[4] + bounds[5]) / 2]
            normal = [0.0, 0.0, 0.0]
            center[a], normal[a] = 0.0, 1.0
            size = 1.1 * max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
            plane = pv.Plane(center=center, direction=normal, i_size=size, j_size=size)
            self.plane.GetMapper().SetInputData(plane)
        offset = [0.0, 0.0, 0.0]
        offset[a] = mm
        self.plane.SetPosition(*offset)
        self.plane.SetVisibility(True)
        self._request_render()

    def _on_render_start(self, *_):
        self._render_soon.stop()
        self._render_started = time.perf_counter()

    def _on_render_end(self, *_):
        self.render_count += 1
        self.last_render_ms = (time.perf_counter() - self._render_started) * 1000
