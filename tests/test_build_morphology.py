import numpy as np
import pytest

from tools.build_atlas.morphology import flatten, parse_swc
from tools.build_atlas.recipe import BuildError


def toy_swc() -> str:
    rows = [(1, 1, 0, 0, 0, 5, -1), (2, 1, 2, 0, 0, 4, 1)]
    direction = np.array([1.0, 2.0, 0.5]) / np.linalg.norm([1.0, 2.0, 0.5])
    side = np.cross(direction, [0, 0, 1.0])
    side /= np.linalg.norm(side)
    parent = 1
    for n in range(1, 6):
        point = direction * 4 * n
        rows.append((len(rows) + 1, 4, *point, 1.0, parent))
        parent = len(rows)
    fork = parent
    for sign in (-1, 1):
        parent = fork
        for n in range(1, 4):
            point = direction * (20 + 4 * n) + side * sign * 3 * n
            rows.append((len(rows) + 1, 4, *point, 0.6, parent))
            parent = len(rows)
    for angle in (0.8, 1.6, 2.4):
        parent = 1
        for n in range(1, 3):
            point = -direction * 3 * n + side * np.cos(angle) * 4 * n
            rows.append((len(rows) + 1, 3, *point, 0.5, parent))
            parent = len(rows)
    parent = 1
    for n in range(1, 5):
        rows.append((len(rows) + 1, 2, *(-direction * 10 * n), 0.3, parent))
        parent = len(rows)
    return "# toy\n" + "".join(" ".join(str(round(float(v), 4)) for v in r) + "\n" for r in rows)


STRAIGHT_SWC = "1 1 0 0 0 2 -1\n" + "".join(f"{n} 3 0 {n * 5} 0 1 {n - 1}\n" for n in range(2, 9))


def points_of(lines) -> np.ndarray:
    return np.array([p[:2] for line in lines for p in line.points])


def apical_tip(lines) -> np.ndarray:
    points = points_of(lines)
    return points[np.argmax(np.linalg.norm(points, axis=1))]


def test_apical_dendrite_points_up_and_height_is_one():
    lines = flatten(parse_swc(toy_swc(), "toy"), "toy")
    points = points_of(lines)
    assert points[:, 1].max() - points[:, 1].min() == pytest.approx(1, abs=1e-3)
    upper = points[points[:, 1] > 0.2]
    assert abs(upper[:, 0].mean()) < 0.05 and apical_tip(lines)[1] > 0.5


def test_soma_is_at_the_origin():
    lines = flatten(parse_swc(toy_swc(), "toy"), "toy")
    starts = np.array([line.points[0][:2] for line in lines])
    assert np.min(np.linalg.norm(starts, axis=1)) < 0.05


def test_axon_is_dropped():
    lines = flatten(parse_swc(toy_swc(), "toy"), "toy")
    assert points_of(lines)[:, 1].min() > -0.6


def test_straight_runs_collapse_to_their_ends():
    lines = flatten(parse_swc(STRAIGHT_SWC, "s"), "s")
    assert [len(line.points) for line in lines] == [2]


def test_widths_follow_the_traced_radius():
    lines = flatten(parse_swc(toy_swc(), "toy"), "toy")
    widths = [p[2] for line in lines for p in line.points]
    assert min(widths) >= 0.002 and max(widths) < 0.5


def test_no_dendrites_is_a_build_error():
    with pytest.raises(BuildError, match="no dendrites"):
        flatten(parse_swc("1 1 0 0 0 5 -1\n2 2 0 9 0 1 1\n", "x"), "x")


def test_no_soma_is_a_build_error():
    with pytest.raises(BuildError, match="no soma"):
        flatten(parse_swc("1 3 0 0 0 5 -1\n2 3 0 9 0 1 1\n", "x"), "x")


def test_bad_parent_is_a_build_error():
    with pytest.raises(BuildError, match="x"):
        parse_swc("1 1 0 0 0 5 -1\n2 3 0 9 0 1 7\n", "x")


def test_malformed_line_is_a_build_error():
    with pytest.raises(BuildError, match="line 2"):
        parse_swc("1 1 0 0 0 5 -1\n2 3 zero 9 0 1 1\n", "x")


def test_empty_file_is_a_build_error():
    with pytest.raises(BuildError, match="no points"):
        parse_swc("# nothing\n", "x")
