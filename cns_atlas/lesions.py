from __future__ import annotations

import re
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


def prepare(volume) -> None:
    _label_totals(volume)


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
    seen: set[tuple[int, frozenset[int]]] = set()
    for side in SIDES:
        text = atlas.pathway_text(pathway.key, side)
        if text is None:
            return []
        for index, step in enumerate(pathway.steps):
            if not isinstance(step, Station):
                continue
            stations = resolve(atlas, step, side)
            shares = sorted(((i, found[i]) for i in stations if i in found),
                            key=lambda pair: -pair[1])
            if not shares or shares[0][1] < BROKEN:
                continue
            words = text.steps[index]
            if (index, frozenset(stations)) in seen:
                continue
            seen.add((index, frozenset(stations)))
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


def sphere(volume, centre_mm, radius_mm: float) -> np.ndarray:
    affine = np.asarray(volume.affine, dtype=float)
    shape = np.array(volume.shape[:3])
    inverse = np.linalg.inv(affine)
    centre = inverse @ np.append(np.asarray(centre_mm, dtype=float), 1.0)
    reach = radius_mm / np.abs(np.diag(affine)[:3])
    low = np.clip(np.floor(centre[:3] - reach).astype(int), 0, shape)
    high = np.clip(np.ceil(centre[:3] + reach).astype(int) + 1, 0, shape)
    mask = np.zeros(volume.shape, dtype=bool)
    if np.any(high <= low):
        return mask
    grid = np.stack(np.meshgrid(*(np.arange(a, b) for a, b in zip(low, high, strict=True)),
                                indexing="ij"), axis=-1)
    world = grid @ affine[:3, :3].T + affine[:3, 3]
    inside = np.linalg.norm(world - np.asarray(centre_mm, dtype=float), axis=-1) <= radius_mm
    mask[low[0]:high[0], low[1]:high[1], low[2]:high[2]] = inside
    return mask


def structure_lesion(atlas, structure_id: int) -> Lesion:
    ids = [s.id for s in atlas.structures[atlas.subtree(structure_id)]]
    lesion = Lesion.empty(atlas)
    for volume in atlas.volumes:
        lesion = lesion.with_mask(volume.name, np.isin(np.asarray(volume.data), ids))
    tract_volume = _tract_volume(atlas)
    if tract_volume is not None:
        mask = lesion.masks[tract_volume.name].copy()
        for structure in ids:
            mask.flat[atlas.tracts.voxels(structure)] = True
        lesion = lesion.with_mask(tract_volume.name, mask)
    return lesion


def territory_lesion(atlas, structure_id: int) -> Lesion:
    source = atlas.territories
    brain = atlas.volumes[0]
    inside = np.asarray(source.data) == structure_id
    if tuple(source.shape) != tuple(brain.shape) or not np.allclose(source.affine, brain.affine):
        grid = np.indices(brain.shape).reshape(3, -1)
        world = np.asarray(brain.affine)[:3, :3] @ grid + np.asarray(brain.affine)[:3, 3:4]
        voxels = np.rint(np.linalg.inv(source.affine)[:3, :3] @ world
                         + np.linalg.inv(source.affine)[:3, 3:4]).astype(int)
        ok = np.all((voxels >= 0) & (voxels < np.array(source.shape)[:, None]), axis=0)
        resampled = np.zeros(grid.shape[1], dtype=bool)
        resampled[ok] = inside[tuple(voxels[:, ok])]
        inside = resampled.reshape(brain.shape)
    return Lesion.empty(atlas).with_mask(brain.name, inside)


CITATION = re.compile(r"\s*\[\d+(?:,\s*\d+)*\]")
CASE_TRIES = 12


@dataclass(frozen=True)
class Case:
    target: Lesion
    target_id: int
    label: str
    signs: tuple[str, ...]


def clean_sign(sign: str) -> str:
    return CITATION.sub("", sign).strip()


def signs_of(found: Report) -> tuple[str, ...]:
    signs: list[str] = []
    for deficit in found.deficits:
        if deficit.partly:
            continue
        sign = clean_sign(deficit.sign)
        if sign and sign not in signs:
            signs.append(sign)
    return tuple(signs)


def compare(case: tuple[str, ...], mine: tuple[str, ...]) -> tuple[list[str], list[str],
                                                                   list[str]]:
    return ([s for s in case if s in mine], [s for s in case if s not in mine],
            [s for s in mine if s not in case])


def _case_candidates(atlas) -> list[int]:
    found: list[int] = []
    for pathway in atlas.pathways:
        if pathway.texts != "lesion":
            continue
        for side in SIDES:
            text = atlas.pathway_text(pathway.key, side)
            if text is None:
                continue
            for index, step in enumerate(pathway.steps):
                if isinstance(step, Station) and text.steps[index].sign:
                    found += [i for i in resolve(atlas, step, side) if i not in found]
    return found + [s.id for s in territories(atlas)]


def new_case(atlas, rng) -> Case | None:
    candidates = _case_candidates(atlas)
    if not candidates:
        return None
    for _ in range(CASE_TRIES):
        target_id = rng.choice(candidates)
        kind = atlas.get(target_id).kind
        target = (territory_lesion(atlas, target_id) if kind == "territory"
                  else structure_lesion(atlas, target_id))
        signs = signs_of(report(atlas, target))
        if signs:
            return Case(target, target_id, atlas.get(target_id).name, signs)
    return None
