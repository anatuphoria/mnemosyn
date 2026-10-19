from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cns_atlas import Atlas, AtlasError
from cns_atlas.model import Structure

from .recipe import BuildError, VolumeSpec

MOVED_COUNT = 0.05
MOVED_MM = 1.0
ACCEPT_HINT = "if these changes are intended, rebuild with --accept-changes"


@dataclass(frozen=True)
class Changes:
    removed: tuple[str, ...] = ()
    renamed: tuple[str, ...] = ()
    moved: tuple[str, ...] = ()

    @property
    def blocking(self) -> list[str]:
        return ([f"removed: {r}" for r in self.removed]
                + [f"renamed: {r}" for r in self.renamed])


def _is_package(path: Path) -> bool:
    try:
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(metadata, dict) and "format_version" in metadata


def _shapes(data: np.ndarray, affine: np.ndarray,
            step: int = 16) -> dict[int, tuple[int, np.ndarray]]:
    data = np.asarray(data)
    size = int(data.max()) + 1 if data.size else 1
    counts, sums = np.zeros(size), np.zeros((size, 3))
    for start in range(0, data.shape[0], step):
        slab = np.ascontiguousarray(data[start:start + step]).astype(np.int64)
        flat = slab.ravel()
        voxels = np.flatnonzero(flat)
        labels = flat[voxels]
        counts += np.bincount(labels, minlength=size)
        for axis, coordinate in enumerate(np.unravel_index(voxels, slab.shape)):
            offset = start if axis == 0 else 0
            sums[:, axis] += np.bincount(labels, weights=coordinate + offset, minlength=size)
    out = {}
    for label in np.flatnonzero(counts[1:]) + 1:
        centre = np.asarray(affine) @ np.append(sums[label] / counts[label], 1.0)
        out[int(label)] = (int(counts[label]), centre[:3])
    return out


def compare(previous: Path, structures: list[Structure],
            volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]],
            ignore: set[int]) -> Changes | None:
    if not _is_package(previous):
        return None
    try:
        return _compare(Atlas.open(previous), structures, volumes, ignore)
    except (AtlasError, OSError, ValueError) as exc:
        raise BuildError([f"{previous}: the previous build cannot be read ({exc}); move it aside "
                          "or delete it, then build again"]) from exc


def _compare(old: Atlas, structures: list[Structure],
             volumes: list[tuple[VolumeSpec, np.ndarray, np.ndarray]],
             ignore: set[int]) -> Changes:
    names = {s.id: s.name for s in structures}
    before = {s.id: s.name for s in old.structures}
    removed = tuple(f"{name} ({i})" for i, name in sorted(before.items())
                    if i not in names and i not in ignore)
    renamed = tuple(f"{name} ({i}), now {names[i]}" for i, name in sorted(before.items())
                    if i in names and names[i] != name)
    moved = []
    old_volumes = {v.name: v for v in old.volumes}
    for spec, data, affine in volumes:
        if spec.name not in old_volumes:
            continue
        was = old_volumes[spec.name]
        then, now = _shapes(was.data, was.affine), _shapes(data, affine)
        for label, (count, centre) in sorted(then.items()):
            if label not in names:
                continue
            new_count, new_centre = now.get(label, (0, centre))
            if (abs(new_count - count) > MOVED_COUNT * count
                    or np.linalg.norm(new_centre - centre) > MOVED_MM):
                moved.append(f"{names[label]} ({label})")
    return Changes(removed, renamed, tuple(dict.fromkeys(moved)))


def report_lines(changes: Changes | None) -> list[str]:
    if changes is None:
        return ["- changes since the previous build: no previous build"]
    rows = changes.blocking + [f"moved: {m}" for m in changes.moved]
    if not rows:
        return ["- changes since the previous build: none"]
    return ["- changes since the previous build:"] + [f"  - {row}" for row in rows]
