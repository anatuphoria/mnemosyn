from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from .atlas_data import Atlas


class AppState(QObject):
    selection_changed = Signal(object)
    visibility_changed = Signal(object)

    def __init__(self, atlas: Atlas) -> None:
        super().__init__()
        self.atlas = atlas
        self._selected: str | None = None
        self._hidden: set[str] = set()

    @property
    def selected(self) -> str | None:
        return self._selected

    def select(self, structure_id: str | None) -> None:
        if structure_id is not None and structure_id not in self.atlas.structures:
            raise KeyError(structure_id)
        if structure_id != self._selected:
            self._selected = structure_id
            self.selection_changed.emit(structure_id)

    def is_hidden(self, structure_id: str) -> bool:
        return structure_id in self._hidden

    def set_hidden(self, ids: Iterable[str], hidden: bool) -> None:
        ids = set(ids)
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

    def isolate(self, structure_id: str) -> None:
        self.set_hidden([structure_id], False)
        self.set_hidden([s for s in self.atlas.structures if s != structure_id], True)
