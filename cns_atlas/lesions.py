from __future__ import annotations

from dataclasses import dataclass, field
from weakref import WeakKeyDictionary

import numpy as np

from .model import Station
from .pathways import resolve

BROKEN = 0.05
PARTLY = 0.25
SIDES = ("left", "right")

_totals: WeakKeyDictionary = WeakKeyDictionary()


@dataclass(frozen=True)
class Lesion:
    masks: dict[str, np.ndarray] = field(default_factory=dict)

    @classmethod
    def empty(cls, atlas) -> Lesion:
        return cls({v.name: np.zeros(v.shape, dtype=bool) for v in atlas.volumes})

    def with_mask(self, name: str, mask: np.ndarray) -> Lesion:
        return Lesion({**self.masks, name: np.asarray(mask, dtype=bool)})

    @property
    def is_empty(self) -> bool:
        return not any(mask.any() for mask in self.masks.values())


@dataclass(frozen=True)
class Deficit:
    route: str
    route_name: str
    side: str
    step: int
    lesion: str
    sign: str
    partly: bool
    structures: tuple[tuple[int, float], ...]
    references: tuple = ()


@dataclass(frozen=True)
class Report:
    hits: dict[int, float]
    deficits: tuple[Deficit, ...]
    spared: tuple[str, ...]


def territories(atlas) -> list:
    if atlas.territories is None:
        return []
    return [s for s in atlas.structures if s.kind == "territory" and s.side in SIDES]


def _label_totals(volume) -> np.ndarray:
    if volume not in _totals:
        _totals[volume] = np.bincount(np.asarray(volume.data).ravel())
    return _totals[volume]


def _tract_volume(atlas):
    tracts = atlas.tracts
    if tracts is None:
        return None
    return next((v for v in atlas.volumes if tuple(v.shape) == tuple(tracts.shape)
                 and np.allclose(v.affine, tracts.affine)), None)


def hits(atlas, lesion: Lesion) -> dict[int, float]:
    found: dict[int, float] = {}
    for volume in atlas.volumes:
        mask = lesion.masks.get(volume.name)
        if mask is None or not mask.any():
            continue
        totals = _label_totals(volume)
        inside = np.bincount(np.asarray(volume.data)[mask], minlength=len(totals))
        for label in np.flatnonzero(inside):
            if label and int(label) in atlas:
                found[int(label)] = float(inside[label] / totals[label])
    tract_volume = _tract_volume(atlas)
    mask = lesion.masks.get(tract_volume.name) if tract_volume is not None else None
    if mask is not None and mask.any():
        flat = mask.ravel()
        for structure_id in atlas.tracts.ids:
            voxels = atlas.tracts.voxels(structure_id)
            if len(voxels):
                share = float(flat[voxels].mean())
                if share > 0 and structure_id in atlas:
                    found[int(structure_id)] = max(found.get(int(structure_id), 0.0), share)
    return found


def _route_deficits(atlas, pathway, found: dict[int, float]) -> list[Deficit]:
    deficits: list[Deficit] = []
    seen: set[tuple[int, str]] = set()
    for side in SIDES:
        text = atlas.pathway_text(pathway.key, side)
        if text is None:
            return []
        for index, step in enumerate(pathway.steps):
            if not isinstance(step, Station):
                continue
            shares = sorted(((i, found[i]) for i in resolve(atlas, step, side) if i in found),
                            key=lambda pair: -pair[1])
            if not shares or shares[0][1] < BROKEN:
                continue
            words = text.steps[index]
            if (index, words.lesion) in seen:
                continue
            seen.add((index, words.lesion))
            deficits.append(Deficit(pathway.key, pathway.name, side, index, words.lesion,
                                    words.sign, shares[0][1] < PARTLY, tuple(shares),
                                    tuple(text.references)))
    return deficits


def report(atlas, lesion: Lesion) -> Report:
    found = hits(atlas, lesion)
    deficits: list[Deficit] = []
    spared: list[str] = []
    for pathway in atlas.pathways:
        if pathway.texts != "lesion" or atlas.pathway_text(pathway.key, SIDES[0]) is None:
            continue
        mine = _route_deficits(atlas, pathway, found)
        deficits += mine
        if not mine:
            spared.append(pathway.key)
    return Report(found, tuple(deficits), tuple(spared))
