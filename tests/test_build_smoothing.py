import numpy as np
import pytest

pv = pytest.importorskip("pyvista")

from tools.build_atlas.meshing import isosurface, surface

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


def centroid_of(mesh):
    from tools.build_atlas.meshing import _centroid
    return _centroid(mesh)


def centre_of(volume, label=1):
    return np.argwhere(volume == label).mean(axis=0)


def test_blur_removes_the_staircase():
    volume = tilted()
    assert terraces(mesh_of(volume, blur_mm=1.0)) < 0.6 * terraces(mesh_of(volume, blur_mm=0.0))


def test_shapes_with_much_more_surface_on_one_side_are_still_smoothed():
    volume = tilted()
    volume[2:38, 1:3, 3:38] = 1
    assert terraces(mesh_of(volume, blur_mm=1.0)) < 0.6 * terraces(mesh_of(volume, blur_mm=0.0))


@pytest.mark.parametrize("radius", [8, 3])
def test_spheres_keep_their_volume(radius):
    volume = sphere(radius)
    mesh = mesh_of(volume)
    assert abs(mesh.volume / volume.sum() - 1) < 0.10


@pytest.mark.parametrize("count", [1, 2, 3, 4, 8])
def test_tiny_blobs_survive_smoothing(count):
    volume = np.zeros((20, 20, 20), dtype=np.uint8)
    volume[10:10 + count, 10, 10] = 1
    mesh = mesh_of(volume)
    assert pieces(mesh) == 1 and abs(mesh.volume / count - 1) < 0.10
    assert np.linalg.norm(np.asarray(mesh.points).mean(axis=0) - centre_of(volume)) < 1.0


def test_thin_slabs_keep_their_volume():
    volume = np.zeros((20, 30, 30), dtype=np.uint8)
    volume[10, 9:21, 9:21] = 1
    assert abs(mesh_of(volume).volume / volume.sum() - 1) < 0.10


def diagonal_shapes():
    edge = np.zeros((20, 20, 20), dtype=np.uint8)
    edge[8:10, 8:10, 8:10] = 1
    edge[10:12, 10:12, 8:10] = 1
    sparse = np.zeros((24, 24, 24), dtype=np.uint8)
    sparse[8:16, 8:16, 8:16] = np.random.default_rng(3).random((8, 8, 8)) < 0.35
    return {"edge": edge, "sparse": sparse}


@pytest.mark.parametrize("name", ["edge", "sparse"])
def test_shapes_touching_only_at_edges_keep_their_volume(name):
    volume = diagonal_shapes()[name]
    mesh = mesh_of(volume, blur_mm=2.0)
    assert abs(mesh.volume / volume.sum() - 1) < 0.10
    assert np.linalg.norm(centroid_of(mesh) - centre_of(volume)) < 1.0


def test_touching_structures_stay_apart():
    volume = np.zeros((30, 20, 20), dtype=np.uint8)
    volume[5:15, 5:15, 5:15] = 1
    volume[15:25, 5:15, 5:15] = 2
    mesh = mesh_of(volume, label=1)
    points = np.asarray(mesh.points)
    assert points[:, 0].max() <= 15.5
    assert np.linalg.norm(points.mean(axis=0) - centre_of(volume, 1)) < 1.0


def test_points_too_close_to_tell_apart_leave_only_triangles():
    field = np.zeros((12, 12, 12), dtype=np.float32)
    field[3:8, 3:8, 3:8] = 1.0
    field[9, 9, 9] = 0.5 + 1e-6
    mesh = isosurface(field, (100.0, 100.0, 60.0))
    assert mesh.n_cells and mesh.is_all_triangles


@pytest.mark.parametrize("radius", [1.5, 2.0])
def test_small_nuclei_come_out_round(radius):
    volume = sphere(radius, size=20)
    mesh = mesh_of(volume, blur_mm=2.0)
    distance = np.linalg.norm(np.asarray(mesh.points) - centroid_of(mesh), axis=1)
    assert distance.std() / distance.mean() < 0.05
    assert abs(mesh.volume / volume.sum() - 1) < 0.10


def test_slivers_smaller_than_a_voxel_are_not_counted_as_pieces():
    from tools.build_atlas.meshing import _pieces
    mesh = (pv.Sphere(radius=5.0) + pv.Sphere(radius=0.3, center=(9.0, 0.0, 0.0))).triangulate()
    assert _pieces(mesh, voxel=1.0) == 1
    assert _pieces(mesh, voxel=0.01) == 2
