from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from cns_atlas import Atlas

from .slices import AXES


class AppState(QObject):
    selection_changed = Signal(object)
    visibility_changed = Signal(object)
    slice_changed = Signal(str, float)

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

    @property
    def selected(self) -> int | None:
        return self._selected

    def select(self, structure_id: int | None) -> None:
        if structure_id is not None and structure_id not in self.atlas:
            raise KeyError(structure_id)
        if structure_id is not None:
            inside = self.geometry_in(structure_id)
            if inside and all(i in self._tracts for i in inside):
                self.set_hidden(inside, False)
        if structure_id != self._selected:
            self._selected = structure_id
            self.selection_changed.emit(structure_id)

    def geometry_in(self, structure_id: int) -> list[int]:
        subtree = self.atlas.structures[self.atlas.subtree(structure_id)]
        return [s.id for s in subtree if s.id in self._geometry]

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

    def set_slice(self, axis: str, mm: float) -> None:
        if axis not in AXES:
            raise ValueError(f"unknown slice axis {axis!r}")
        mm = float(mm)
        if not math.isfinite(mm):
            raise ValueError(f"slice position must be finite, got {mm}")
        if (axis, mm) != (self.slice_axis, self.slice_mm):
            self.slice_axis, self.slice_mm = axis, mm
            self.slice_changed.emit(axis, mm)
