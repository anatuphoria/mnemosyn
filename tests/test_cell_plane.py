import numpy as np

from cns_desktop.views.cell_plane import mid_body_plane


def long_cloud(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(4000, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    return directions * [30, 6, 3] + [5, -2, 1]


def test_plane_is_across_the_long_axis_through_the_middle():
    plane = mid_body_plane(long_cloud())
    assert abs(abs(plane.normal @ [1, 0, 0]) - 1) < 0.01
    assert np.allclose(plane.centre, [5, -2, 1], atol=1.5)


def test_plane_axes_are_unit_and_square_to_the_normal():
    plane = mid_body_plane(long_cloud())
    for axis in (plane.u, plane.v):
        assert abs(np.linalg.norm(axis) - 1) < 1e-9 and abs(axis @ plane.normal) < 1e-9
    assert abs(plane.u @ plane.v) < 1e-9


def test_plane_size_follows_the_second_axis():
    plane = mid_body_plane(long_cloud())
    extent = np.ptp(long_cloud() @ plane.u)
    assert np.isclose(plane.size, 1.4 * extent)


def test_middle_third_is_used_for_the_centre():
    points = np.concatenate([long_cloud(), [[200.0, 0.0, 0.0]] * 50])
    plane = mid_body_plane(points)
    assert abs(plane.centre[0] - mid_body_plane(long_cloud()).centre[0]) < 40
