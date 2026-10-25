import math

import numpy as np

from atlas_package import toy_cell_view
from cns_desktop.cell_layout import normal_at, place_cells, point_along, to_frame


def distance_to_curve(points, p) -> float:
    pts, p = np.asarray(points, float), np.asarray(p, float)
    best = math.inf
    for a, b in zip(pts[:-1], pts[1:]):
        t = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1)
        best = min(best, float(np.linalg.norm(a + t * (b - a) - p)))
    return best


def layer(view, key):
    return next(item for item in view.layers if item.key == key)


def test_point_along_walks_by_arc_length():
    points = ((0.0, 0.0), (10.0, 0.0), (10.0, 30.0))
    assert point_along(points, 0.25) == (10.0, 0.0)
    assert point_along(points, 1.0) == (10.0, 30.0)


def test_normal_is_a_unit_vector_across_the_curve():
    nx, ny = normal_at(((0.0, 0.0), (10.0, 0.0)), 0.5)
    assert math.isclose(math.hypot(nx, ny), 1) and abs(nx) < 1e-9


def test_copies_sit_on_their_layer_curve():
    view = toy_cell_view()
    for placed in place_cells(view, "basic"):
        assert distance_to_curve(layer(view, placed.layer).points, (placed.x, placed.y)) < 1e-6


def test_dendrites_point_towards_the_target_layer():
    view = toy_cell_view()
    for placed in place_cells(view, "full"):
        target = layer(view, placed.towards).points
        tip = to_frame(placed, (0.0, 1.0))
        assert distance_to_curve(target, tip) < distance_to_curve(target, (placed.x, placed.y))


def test_counts_follow_level_and_layout_is_deterministic():
    view = toy_cell_view()
    assert len(place_cells(view, "basic")) == 7 and len(place_cells(view, "full")) == 9
    assert place_cells(view, "full") == place_cells(view, "full")


def test_reconstructions_are_used_in_turn_and_every_other_copy_is_mirrored():
    big = [p for p in place_cells(toy_cell_view(), "basic") if p.cell == "big"]
    assert [p.reconstruction for p in big] == [0, 1, 0]
    assert [p.mirrored for p in big] == [False, True, False]
    assert all(p.scale == 120.0 for p in big)


def test_mirroring_flips_the_side_of_a_branch():
    placed = next(p for p in place_cells(toy_cell_view(), "basic") if p.mirrored)
    straight = placed.__class__(**{**placed.__dict__, "mirrored": False})
    left, right = to_frame(placed, (0.2, 0.5)), to_frame(straight, (0.2, 0.5))
    middle = to_frame(placed, (0.0, 0.5))
    assert np.allclose(np.subtract(left, middle), np.subtract(middle, right), atol=1e-6)
