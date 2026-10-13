from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from cns_atlas import Atlas

from .slices import AXES


class AppState(QObject):
    selection_changed = Signal(object)
    slice_volume_changed = Signal(str)
    visibility_changed = Signal(object)
    slice_changed = Signal(str, float)
    focus_changed = Signal(object)

    def __init__(self, atlas: Atlas) -> None:
        super().__init__()
        self.atlas = atlas
        self.geometry_ids = tuple(s.id for s in atlas.structures if atlas.has_mesh(s.id))
        self._geometry = set(self.geometry_ids)
        self._selected: int | None = None
        tracts = {s.id for s in atlas.structures if s.kind == "tract"}
        self.tract_ids = tuple(i for i in self.geometry_ids if i in tracts)
        self._tracts = frozenset(self.tract_ids)
        self._hidden: set[int] = set(self.tract_ids)
        self.slice_axis = "axial"
        self.slice_mm = 0.0
        self.slice_volume = atlas.volumes[0].name if atlas.volumes else ""
        self.focus: frozenset[int] | None = None
        self.emphasis: tuple[int, ...] = ()

    @property
    def selected(self) -> int | None:
        return self._selected

    def select(self, structure_id: int | None, emphasis: Iterable[int] = ()) -> None:
        if structure_id is not None and structure_id not in self.atlas:
            raise KeyError(structure_id)
        if structure_id is not None:
            inside = self.geometry_in(structure_id)
            if inside and all(i in self._tracts for i in inside):
                self.set_hidden(inside, False)
        emphasis = tuple(i for i in emphasis if i in self._geometry)
        if (structure_id, emphasis) != (self._selected, self.emphasis):
            self._selected, self.emphasis = structure_id, emphasis
            self.selection_changed.emit(structure_id)

    def geometry_in(self, structure_id: int) -> list[int]:
        subtree = self.atlas.structures[self.atlas.subtree(structure_id)]
        return [s.id for s in subtree if s.id in self._geometry]

    def highlighted_ids(self) -> list[int]:
        if self.emphasis:
            return list(self.emphasis)
        return [] if self._selected is None else self.geometry_in(self._selected)

    def set_focus(self, ids: Iterable[int] | None) -> None:
        focus = None if ids is None else frozenset(ids) & self._geometry
        if focus != self.focus:
            self.focus = focus
            self.focus_changed.emit(focus)

    def in_focus(self, structure_id: int) -> bool:
        return self.focus is None or structure_id in self.focus

    def is_hidden(self, structure_id: int) -> bool:
        return structure_id in self._hidden

    def is_tract(self, structure_id: int) -> bool:
        return structure_id in self._tracts

    def toggle_tracts(self) -> None:
        any_hidden = any(i in self._hidden for i in self.tract_ids)
        self.set_hidden(self.tract_ids, not any_hidden)

    def set_hidden(self, ids: Iterable[int], hidden: bool) -> bool:
        ids = set(ids) & self._geometry
        changed = ids - self._hidden if hidden else ids & self._hidden
        if not changed:
            return False
        if hidden:
            self._hidden |= changed
        else:
            self._hidden -= changed
        self.visibility_changed.emit(frozenset(changed))
        return True

    def show_all(self) -> None:
        self.set_hidden([i for i in self._hidden if i not in self._tracts], False)

    def isolate(self, structure_id: int) -> None:
        keep = set(self.geometry_in(structure_id))
        self.set_hidden(keep, False)
        self.set_hidden([i for i in self.geometry_ids if i not in keep], True)

    def set_slice_volume(self, name: str) -> None:
        if name not in {v.name for v in self.atlas.volumes}:
            raise ValueError(f"unknown slice volume {name!r}")
        if name != self.slice_volume:
            self.slice_volume = name
            self.slice_volume_changed.emit(name)

    def set_slice(self, axis: str, mm: float) -> None:
        if axis not in AXES:
            raise ValueError(f"unknown slice axis {axis!r}")
        mm = float(mm)
        if not math.isfinite(mm):
            raise ValueError(f"slice position must be finite, got {mm}")
        if (axis, mm) != (self.slice_axis, self.slice_mm):
            self.slice_axis, self.slice_mm = axis, mm
            self.slice_changed.emit(axis, mm)
