from __future__ import annotations

import numpy as np

from cns_atlas.cells import Polyline

from .recipe import BuildError

TOLERANCE = 0.002
MIN_WIDTH = 0.002
SOMA, BASAL, APICAL = 1, 3, 4
KEPT = (SOMA, BASAL, APICAL)


def parse_swc(text: str, origin: str) -> np.ndarray:
    rows, seen = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        try:
            if len(parts) != 7:
                raise ValueError(f"expected 7 columns, got {len(parts)}")
            values = [float(v) for v in parts]
        except ValueError as exc:
            raise BuildError([f"{origin}: line {number}: {exc}"]) from exc
        point, parent = int(values[0]), int(values[6])
        if parent != -1 and parent not in seen:
            raise BuildError([f"{origin}: line {number}: parent {parent} is not an earlier point"])
        seen.add(point)
        rows.append(values)
    if not rows:
        raise BuildError([f"{origin}: no points"])
    return np.array(rows)


def _kept(rows: np.ndarray) -> np.ndarray:
    keep: dict[int, bool] = {}
    for point, kind, parent in zip(rows[:, 0].astype(int), rows[:, 1].astype(int),
                                   rows[:, 6].astype(int)):
        keep[point] = kind in KEPT and (parent == -1 or keep.get(parent, False))
    return np.array([keep[int(p)] for p in rows[:, 0]])


def _simplify(points: np.ndarray, tolerance: float) -> list[int]:
    if len(points) < 3:
        return list(range(len(points)))
    start, end = points[0], points[-1]
    line = end - start
    length = np.linalg.norm(line)
    offsets = points - start
    if length == 0:
        distances = np.linalg.norm(offsets, axis=1)
    else:
        distances = np.abs(offsets[:, 0] * line[1] - offsets[:, 1] * line[0]) / length
    worst = int(np.argmax(distances))
    if distances[worst] <= tolerance:
        return [0, len(points) - 1]
    left = _simplify(points[:worst + 1], tolerance)
    right = _simplify(points[worst:], tolerance)
    return left + [worst + i for i in right[1:]]


def _runs(ids: list[int], parents: list[int], dendrite: set[int]) -> list[list[int]]:
    children: dict[int, list[int]] = {}
    for point, parent in zip(ids, parents):
        children.setdefault(parent, []).append(point)

    def dendritic(point: int) -> list[int]:
        return [c for c in children.get(point, []) if c in dendrite]

    parent_of = dict(zip(ids, parents))
    runs = []
    for point in ids:
        if point not in dendrite:
            continue
        parent = parent_of[point]
        if parent in dendrite and len(dendritic(parent)) == 1:
            continue
        run = [parent, point] if parent != -1 else [point]
        while len(dendritic(run[-1])) == 1:
            run.append(dendritic(run[-1])[0])
        runs.append(run)
    return runs


def flatten(rows: np.ndarray, origin: str, tolerance: float = TOLERANCE) -> tuple[Polyline, ...]:
    rows = rows[_kept(rows)]
    kinds = rows[:, 1].astype(int)
    if not np.any(kinds == SOMA):
        raise BuildError([f"{origin}: no soma"])
    if not np.any(kinds != SOMA):
        raise BuildError([f"{origin}: no dendrites"])
    xyz = rows[:, 2:5] - rows[kinds == SOMA, 2:5].mean(axis=0)
    _, _, axes = np.linalg.svd(xyz - xyz.mean(axis=0), full_matrices=False)
    flat = xyz @ axes[:2].T
    target = kinds == APICAL if np.any(kinds == APICAL) else kinds != SOMA
    main = flat[target].mean(axis=0)
    angle = np.arctan2(main[0], main[1])
    turn = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    flat = flat @ turn.T
    scale = 1.0 / (flat[:, 1].max() - flat[:, 1].min())
    flat *= scale
    widths = np.maximum(rows[:, 5] * 2 * scale, MIN_WIDTH)
    ids = rows[:, 0].astype(int).tolist()
    index = {point: i for i, point in enumerate(ids)}
    dendrite = {point for point, kind in zip(ids, kinds) if kind != SOMA}
    lines = []
    for run in _runs(ids, rows[:, 6].astype(int).tolist(), dendrite):
        where = [index[p] for p in run]
        keep = _simplify(flat[where], tolerance)
        lines.append(Polyline(tuple(
            (round(float(flat[where[k], 0]), 4), round(float(flat[where[k], 1]), 4),
             round(float(widths[where[k]]), 4)) for k in keep)))
    return tuple(lines)
