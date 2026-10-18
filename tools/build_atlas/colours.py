from __future__ import annotations

from dataclasses import replace

import numpy as np

NEAR_MM = 10.0
PALETTE: tuple[tuple[int, int, int], ...] = (
    (230, 80, 70), (240, 150, 50), (235, 205, 70), (150, 200, 70), (70, 170, 90),
    (60, 200, 180), (70, 160, 230), (90, 100, 220), (180, 95, 215), (220, 100, 190),
    (240, 160, 170), (180, 120, 80), (250, 230, 160), (160, 230, 150), (150, 220, 240),
    (190, 180, 250), (140, 40, 60), (40, 110, 110), (110, 60, 140), (200, 200, 200),
)
_XYZ = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
_WHITE = np.array([0.95047, 1.0, 1.08883])


def _lab(rgb) -> np.ndarray:
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = (_XYZ @ c) / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def delta_e(a, b) -> float:
    return float(np.linalg.norm(_lab(a) - _lab(b)))


def distinct_colours(order: list[int], centres: dict[int, np.ndarray],
                     near_mm: float = NEAR_MM) -> dict[int, tuple[int, int, int]]:
    chosen: dict[int, tuple[int, int, int]] = {}
    used = dict.fromkeys(PALETTE, 0)
    for member in order:
        mine = np.asarray(centres[member], dtype=float).reshape(-1, 3)
        near = [chosen[other] for other in chosen
                if np.min(np.linalg.norm(mine[:, None] - np.asarray(centres[other],
                                                                   dtype=float).reshape(-1, 3),
                                         axis=-1)) < near_mm]
        best = max(PALETTE, key=lambda c: (min((delta_e(c, n) for n in near), default=np.inf),
                                           -used[c], -PALETTE.index(c)))
        chosen[member] = best
        used[best] += 1
    return chosen


def recolour(structures: list, groups: set[int], explicit: set[int], meshes: dict) -> list:
    members = [s for s in structures if groups & set(s.structure_id_path[:-1])
               and s.kind not in ("group", "shell", "cover") and s.concept is None
               and s.id not in explicit]
    centres = {}
    for s in members:
        own = [s.id] + [t.id for t in structures if t.concept == s.id]
        points = [np.asarray(meshes[i].vertices, dtype=float).mean(axis=0)
                  for i in own if i in meshes]
        if points:
            centres[s.id] = np.array(points)
    colours = distinct_colours(sorted(centres), centres)
    return [replace(s, rgb_triplet=colours.get(s.concept if s.concept in colours else s.id,
                                               s.rgb_triplet))
            for s in structures]
