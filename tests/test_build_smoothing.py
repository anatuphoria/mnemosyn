import numpy as np
import pytest

pytest.importorskip("pyvista")

from tools.build_atlas.meshing import surface

ITERATIONS, PASS_BAND = 30, 0.05


def mesh_of(volume, label=1, blur_mm=1.0):
    return surface(volume, np.eye(4), label, ITERATIONS, PASS_BAND, blur_mm=blur_mm)


def sphere(radius: float, size: int = 40) -> np.ndarray:
    grid = np.indices((size, size, size)).transpose(1, 2, 3, 0)
    return (np.linalg.norm(grid - size / 2, axis=-1) <= radius).astype(np.uint8)


def tilted(size: int = 40) -> np.ndarray:
    g = np.indices((size, size, size))
    return ((g[2] < 10 + 0.15 * g[0] + 0.1 * g[1]) & (g[2] > 2)).astype(np.uint8)


def terraces(mesh) -> float:
    p = np.asarray(mesh.points)
    top = p[(p[:, 2] > 5) & (p[:, 0] > 5) & (p[:, 0] < 33) & (p[:, 1] > 5) & (p[:, 1] < 33)]
    plane = np.c_[top[:, 0], top[:, 1], np.ones(len(top))]
    fit = np.linalg.lstsq(plane, top[:, 2], rcond=None)[0]
    return float(np.sqrt(np.mean((top[:, 2] - plane @ fit) ** 2)))


def pieces(mesh) -> int:
    return len(np.unique(mesh.connectivity().point_data["RegionId"]))


def centre_of(volume, label=1):
    return np.argwhere(volume == label).mean(axis=0)


def test_blur_removes_the_staircase():
    volume = tilted()
    assert terraces(mesh_of(volume, blur_mm=1.0)) < 0.6 * terraces(mesh_of(volume, blur_mm=0.0))


@pytest.mark.parametrize("radius", [8, 3])
def test_spheres_keep_their_volume(radius):
    volume = sphere(radius)
    mesh = mesh_of(volume)
    assert abs(mesh.volume / volume.sum() - 1) < 0.10


@pytest.mark.parametrize("count", [2, 3, 4])
def test_tiny_blobs_survive_smoothing(count):
    volume = np.zeros((20, 20, 20), dtype=np.uint8)
    volume[10:10 + count, 10, 10] = 1
    mesh = mesh_of(volume)
    assert pieces(mesh) == 1 and mesh.volume > 0
    assert np.linalg.norm(np.asarray(mesh.points).mean(axis=0) - centre_of(volume)) < 1.0


def test_thin_slabs_are_never_thinner_than_unblurred():
    volume = np.zeros((20, 30, 30), dtype=np.uint8)
    volume[10, 9:21, 9:21] = 1
    raw = abs(mesh_of(volume, blur_mm=0.0).volume / volume.sum() - 1)
    assert abs(mesh_of(volume).volume / volume.sum() - 1) <= raw + 0.01


def test_touching_structures_stay_apart():
    volume = np.zeros((30, 20, 20), dtype=np.uint8)
    volume[5:15, 5:15, 5:15] = 1
    volume[15:25, 5:15, 5:15] = 2
    mesh = mesh_of(volume, label=1)
    points = np.asarray(mesh.points)
    assert points[:, 0].max() <= 15.5
    assert np.linalg.norm(points.mean(axis=0) - centre_of(volume, 1)) < 1.0
