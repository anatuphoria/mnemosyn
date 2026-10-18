from __future__ import annotations

from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet
from vtkmodules.vtkRenderingCore import (vtkActor, vtkCompositeDataDisplayAttributes,
                                         vtkCompositePolyDataMapper)

CHUNK_FACES = 120_000


def _composite(blocks: list):
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


class Chunks:
    """Neighbouring structures share one composite; a change rebuilds only its own chunks."""

    def __init__(self, ids: list[int], blocks: dict, colors: dict, hidden) -> None:
        groups, current, faces = [], [], 0
        for structure_id in ids:
            size = blocks[structure_id].n_cells
            if current and faces + size > CHUNK_FACES:
                groups.append(current)
                current, faces = [], 0
            current.append(structure_id)
            faces += size
        if current:
            groups.append(current)
        self.ids = groups
        self.actors, self.mappers, self.attributes = [], [], []
        self._where: dict[int, tuple[int, int]] = {}
        self._blocks = blocks
        self._hidden: list[set[int]] = []
        self._marked: list[set[int]] = []
        for chunk, members in enumerate(groups):
            actor, mapper, attributes = _composite([blocks[i] for i in members])
            for index, structure_id in enumerate(members):
                self._where[structure_id] = (chunk, index)
                attributes.SetBlockColor(blocks[structure_id], colors[structure_id])
            self.actors.append(actor)
            self.mappers.append(mapper)
            self.attributes.append(attributes)
            self._hidden.append(set())
            self._marked.append(set())
        self.set_hidden({i: i in hidden for i in ids})

    def attributes_for(self, structure_id: int) -> vtkCompositeDataDisplayAttributes:
        return self.attributes[self._where[structure_id][0]]

    def block_count(self) -> int:
        return sum(len(members) for members in self.ids)

    def set_hidden(self, changes: dict[int, bool]) -> None:
        touched = set()
        for structure_id, hide in changes.items():
            if structure_id in self._where:
                chunk = self._where[structure_id][0]
                (self._hidden[chunk].add if hide else self._hidden[chunk].discard)(structure_id)
                touched.add(chunk)
        for chunk in touched:
            whole = len(self._hidden[chunk]) == len(self.ids[chunk])
            self.actors[chunk].SetVisibility(not whole)
            if whole:
                continue
            attributes = self.attributes[chunk]
            for structure_id in self._hidden[chunk] ^ self._marked[chunk]:
                attributes.SetBlockVisibility(self._blocks[structure_id],
                                              structure_id not in self._hidden[chunk])
            self._marked[chunk] = set(self._hidden[chunk])

    def is_visible(self, structure_id: int) -> bool:
        chunk = self._where[structure_id][0]
        return structure_id not in self._hidden[chunk]

    def pick(self, actor, flat_index: int) -> int | None:
        for chunk, candidate in enumerate(self.actors):
            if candidate is actor:
                index = flat_index - 1
                members = self.ids[chunk]
                return members[index] if 0 <= index < len(members) else None
        return None

    def apply_focus(self, focus, faint: float) -> None:
        for chunk, members in enumerate(self.ids):
            attributes = self.attributes[chunk]
            if focus is None:
                attributes.RemoveBlockOpacities()
                attributes.RemoveBlockPickabilities()
                continue
            for structure_id in members:
                block = self._blocks[structure_id]
                attributes.SetBlockOpacity(block, 1.0 if structure_id in focus else faint)
                attributes.SetBlockPickability(block, structure_id in focus)

    def has_opacities(self) -> bool:
        return any(a.HasBlockOpacities() for a in self.attributes)

    def has_pickabilities(self) -> bool:
        return any(a.HasBlockPickabilities() for a in self.attributes)

    def set_opacity(self, opacity: float) -> None:
        for actor in self.actors:
            actor.GetProperty().SetOpacity(opacity)

    def bounds(self) -> tuple[float, ...]:
        boxes = [actor.GetBounds() for actor in self.actors]
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                min(b[2] for b in boxes), max(b[3] for b in boxes),
                min(b[4] for b in boxes), max(b[5] for b in boxes))

