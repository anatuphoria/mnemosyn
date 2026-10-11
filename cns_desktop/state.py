from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from cns_atlas import Atlas


class AppState(QObject):
    selection_changed = Signal(object)
    visibility_changed = Signal(object)

    def __init__(self, atlas: Atlas) -> None:
        super().__init__()
        self.atlas = atlas
        self.geometry_ids = tuple(s.id for s in atlas.structures if atlas.has_mesh(s.id))
        self._geometry = set(self.geometry_ids)
        self._selected: int | None = None
        self._hidden: set[int] = set()

    @property
    def selected(self) -> int | None:
        return self._selected

    def select(self, structure_id: int | None) -> None:
        if structure_id is not None and structure_id not in self.atlas:
            raise KeyError(structure_id)
        if structure_id != self._selected:
            self._selected = structure_id
            self.selection_changed.emit(structure_id)

    def geometry_in(self, structure_id: int) -> list[int]:
        subtree = self.atlas.structures[self.atlas.subtree(structure_id)]
        return [s.id for s in subtree if s.id in self._geometry]

    def is_hidden(self, structure_id: int) -> bool:
        return structure_id in self._hidden

    def set_hidden(self, ids: Iterable[int], hidden: bool) -> None:
        ids = set(ids) & self._geometry
        changed = ids - self._hidden if hidden else ids & self._hidden
        if not changed:
            return
        if hidden:
            self._hidden |= changed
        else:
            self._hidden -= changed
        self.visibility_changed.emit(frozenset(changed))

    def show_all(self) -> None:
        self.set_hidden(list(self._hidden), False)

    def isolate(self, structure_id: int) -> None:
        keep = set(self.geometry_in(structure_id))
        self.set_hidden(keep, False)
        self.set_hidden([i for i in self.geometry_ids if i not in keep], True)
