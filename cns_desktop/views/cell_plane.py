from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cns_atlas.cells import CellView

SIZE_FACTOR = 1.4


@dataclass(frozen=True)
class Plane:
    centre: np.ndarray
    normal: np.ndarray
    u: np.ndarray
    v: np.ndarray
    size: float


def mid_body_plane(vertices: np.ndarray) -> Plane:
    points = np.asarray(vertices, dtype=float)
    _, _, axes = np.linalg.svd(points - points.mean(axis=0), full_matrices=False)
    normal, u, v = axes[0], axes[1], axes[2]
    along = points @ normal
    low, high = along.min(), along.max()
    third = (high - low) / 3
    middle = points[(along >= low + third) & (along <= high - third)]
    centre = (middle if len(middle) else points).mean(axis=0)
    return Plane(centre, normal, u, v, float(SIZE_FACTOR * np.ptp(points @ u)))


def side_structure(atlas, view: CellView, side: str) -> int | None:
    wanted = set(view.structures)
    return next((s.id for s in atlas.structures
                 if s.side == side and wanted.intersection(s.structure_id_path)
                 and atlas.has_mesh(s.id)), None)
