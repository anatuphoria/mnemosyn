from __future__ import annotations

import numpy as np
import pyvista as pv
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from cns_atlas.meshes import MeshData


BLUR_STEPS = (1.0, 0.7, 0.5, 0.3, 0.0)
VOLUME_TOLERANCE = 0.10
CENTRE_TOLERANCE_MM = 1.0
FINE_STEPS = (2, 4)
FINE_BLUR_STEPS = (0.5, 0.25)
FINE_VOXELS = 8_000_000


def isosurface(field: np.ndarray, origin: tuple[float, float, float],
               level: float = 0.5) -> pv.PolyData:
    grid = pv.ImageData(dimensions=field.shape, origin=origin, spacing=(1.0, 1.0, 1.0))
    grid.point_data["mask"] = field.ravel(order="F")
    mesh = grid.contour([level], scalars="mask", method="marching_cubes").triangulate()
    return mesh.clean(polys_to_lines=False, lines_to_points=False)


def _contour(crop: np.ndarray, lo: np.ndarray, affine: np.ndarray, sigma: np.ndarray,
             iterations: int, pass_band: float, fine: int = 1,
             matched: bool = False) -> pv.PolyData:
    if fine > 1:
        crop = crop.repeat(fine, axis=0).repeat(fine, axis=1).repeat(fine, axis=2)
        scale = np.eye(4)
        scale[:3, :3] /= fine
        scale[:3, 3] = lo + (1.0 / fine - 1) / 2
        affine, lo, sigma = np.asarray(affine) @ scale, np.zeros(3, dtype=int), sigma * fine
    pad = int(np.ceil(3 * sigma.max())) + 2
    mask = np.pad(crop.astype(np.float32), pad)
    if sigma.max() > 0:
        mask = gaussian_filter(mask, sigma)
    level = 0.5
    if matched:
        count = int(crop.sum())
        level = min(level, float(np.partition(mask.ravel(), -count)[-count]))
    mesh = isosurface(mask, tuple(float(v) for v in lo - pad), level)
    if mesh.n_points:
        mesh = mesh.smooth_taubin(n_iter=iterations, pass_band=pass_band)
        mesh.points = (np.c_[mesh.points, np.ones(mesh.n_points)] @ np.asarray(affine).T)[:, :3]
    return mesh


def _centroid(mesh: pv.PolyData) -> np.ndarray:
    points = np.asarray(mesh.points, dtype=float)
    a, b, c = (points[np.asarray(mesh.regular_faces)[:, k]] for k in range(3))
    volumes = np.einsum("ij,ij->i", a, np.cross(b, c))
    if abs(volumes.sum()) < 1e-9:
        return points.mean(axis=0)
    return (volumes[:, None] * (a + b + c)).sum(axis=0) / (4.0 * volumes.sum())


def _pieces(mesh: pv.PolyData, voxel: float = 0.0) -> int:
    parts = mesh.connectivity().split_bodies()
    return sum(1 for part in parts if abs(part.extract_surface(algorithm="dataset_surface").volume) >= voxel)


def surface(volume: np.ndarray, affine: np.ndarray, label: int, iterations: int,
            pass_band: float, blur_mm: float = 0.0) -> pv.PolyData:
    index = np.argwhere(volume == label)
    lo, hi = index.min(axis=0), index.max(axis=0) + 1
    crop = volume[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] == label
    affine = np.asarray(affine, dtype=float)
    sizes = np.linalg.norm(affine[:3, :3], axis=0)
    voxel = abs(np.linalg.det(affine[:3, :3]))
    voxels = crop.sum() * voxel
    centre = (affine @ np.append(index.mean(axis=0), 1.0))[:3]
    if blur_mm == 0.0:
        return _contour(crop, lo, affine, np.zeros(3), iterations, pass_band)
    allowed = ndimage.label(crop, structure=np.ones((3, 3, 3)))[1]
    best, best_error = None, np.inf
    for mesh, whole in _attempts(crop, lo, affine, blur_mm / sizes, iterations, pass_band):
        if not mesh.n_points or (whole and _pieces(mesh, voxel) > allowed):
            continue
        error = abs(mesh.volume / voxels - 1)
        close = np.linalg.norm(_centroid(mesh) - centre)
        if error < VOLUME_TOLERANCE and close < CENTRE_TOLERANCE_MM:
            return mesh
        if close < CENTRE_TOLERANCE_MM and error < best_error:
            best, best_error = mesh, error
    return best if best is not None else mesh


def _attempts(crop: np.ndarray, lo: np.ndarray, affine: np.ndarray, sigma: np.ndarray,
              iterations: int, pass_band: float):
    for step in BLUR_STEPS:
        yield _contour(crop, lo, affine, sigma * step, iterations, pass_band), True
    fits = [k for k in FINE_STEPS if crop.size * k ** 3 <= FINE_VOXELS]
    for fine in fits:
        for step in FINE_BLUR_STEPS:
            yield _contour(crop, lo, affine, sigma * step, iterations, pass_band, fine, True), True
    if fits:
        yield _contour(crop, lo, affine, np.zeros(3), iterations, pass_band, fits[-1]), False


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
