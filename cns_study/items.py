from __future__ import annotations

from dataclasses import dataclass

from cns_atlas import Atlas, Structure

LEVELS = ("structures", "groups")


@dataclass(frozen=True)
class Item:
    id: int
    level: str
    name: str
    acronym: str
    answers: tuple[str, ...]
    geometry: frozenset[int]
    path: tuple[int, ...]


def _meshed(atlas: Atlas) -> frozenset[int]:
    return frozenset(s.id for s in atlas.structures if atlas.has_mesh(s.id))


def _item(atlas: Atlas, structure: Structure, level: str, meshed: frozenset[int]) -> Item:
    subtree = atlas.structures[atlas.subtree(structure.id)]
    geometry = frozenset(s.id for s in subtree if s.id in meshed)
    answers = tuple(dict.fromkeys((structure.name, structure.acronym, *structure.synonyms)))
    return Item(structure.id, level, structure.name, structure.acronym, answers, geometry,
                structure.structure_id_path)


def structure_items(atlas: Atlas) -> list[Item]:
    meshed = _meshed(atlas)
    found = (_item(atlas, s, "structures", meshed) for s in atlas.structures
             if s.kind != "group" and s.concept is None)
    return [item for item in found if item.geometry]


def group_items(atlas: Atlas) -> list[Item]:
    meshed = _meshed(atlas)
    singles = structure_items(atlas)
    candidates = []
    for structure in atlas.structures:
        if structure.kind != "group":
            continue
        item = _item(atlas, structure, "groups", meshed)
        members = frozenset(single.id for single in singles if structure.id in single.path)
        if len(members) >= 2 and item.geometry != meshed:
            candidates.append((item, members))
    return [item for item, members in candidates
            if not any(other.id != item.id and item.id in other.path and same == members
                       for other, same in candidates)]


def items(atlas: Atlas, level: str, scope: int | None = None) -> list[Item]:
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}")
    pool = structure_items(atlas) if level == "structures" else group_items(atlas)
    return pool if scope is None else [item for item in pool if scope in item.path]


def item_for(pool: list[Item], structure_id: int) -> Item | None:
    matches = [item for item in pool if structure_id in item.geometry]
    return max(matches, key=lambda item: len(item.path), default=None)
