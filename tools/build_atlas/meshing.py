from __future__ import annotations

import numpy as np
import pyvista as pv

from cns_atlas.meshes import MeshData


def surface(volume: np.ndarray, affine: np.ndarray, label: int, iterations: int,
            pass_band: float) -> pv.PolyData:
    index = np.argwhere(volume == label)
    lo, hi = index.min(axis=0), index.max(axis=0) + 1
    crop = volume[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] == label
    mask = np.pad(crop.astype(np.float32), 1)
    grid = pv.ImageData(dimensions=mask.shape, origin=tuple(float(v) for v in lo - 1),
                        spacing=(1.0, 1.0, 1.0))
    grid.point_data["mask"] = mask.ravel(order="F")
    mesh = grid.contour([0.5], scalars="mask", method="marching_cubes").triangulate().clean()
    mesh = mesh.smooth_taubin(n_iter=iterations, pass_band=pass_band)
    mesh.points = (np.c_[mesh.points, np.ones(mesh.n_points)] @ np.asarray(affine).T)[:, :3]
    return mesh


def repair_normals(points: np.ndarray, normals: np.ndarray) -> int:
    weak = np.linalg.norm(normals, axis=1) < 1e-3
    if not weak.any():
        return 0
    outward = points[weak] - points.mean(axis=0)
    length = np.linalg.norm(outward, axis=1, keepdims=True)
    fallback = np.tile(np.array([0.0, 0.0, 1.0], dtype=normals.dtype), (len(outward), 1))
    normals[weak] = np.where(length > 1e-9, outward / np.maximum(length, 1e-9), fallback)
    return int(weak.sum())


def _mesh_data(mesh: pv.PolyData) -> tuple[MeshData, int]:
    mesh = mesh.compute_normals(cell_normals=False, split_vertices=False,
                                auto_orient_normals=True)
    points = np.asarray(mesh.points, dtype=np.float32)
    normals = np.asarray(mesh.point_data["Normals"], dtype=np.float32).copy()
    repaired = repair_normals(points, normals)
    return MeshData(vertices=points, normals=normals.astype(np.float16),
                    faces=np.asarray(mesh.regular_faces, dtype=np.uint32)), repaired


def levels(mesh: pv.PolyData, max_faces: int, fractions: tuple[float, ...],
           min_faces: int) -> tuple[list[MeshData], int]:
    base = mesh if mesh.n_cells <= max_faces else mesh.decimate(1.0 - max_faces / mesh.n_cells)
    out: list[MeshData] = []
    repaired = []
    previous = None
    for fraction in fractions:
        target = max(min_faces, int(base.n_cells * fraction))
        level = base if target >= base.n_cells else base.decimate(1.0 - target / base.n_cells)
        if level.n_cells < min_faces and previous is not None:
            level = previous
        previous = level
        data, count = _mesh_data(level)
        out.append(data)
        repaired.append(count)
    return out, repaired[0] if repaired else 0
