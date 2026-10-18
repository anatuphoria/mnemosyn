import itertools

import numpy as np
import pytest

from atlas_fixtures import make_source_archive, write_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.colours import NEAR_MM, PALETTE, delta_e, distinct_colours
from tools.build_atlas.hierarchy import ALTERNATE, load_structures, shade
from tools.build_atlas.recipe import BuildError
from tools.build_atlas.validate import check_hierarchy

BRAIN = '{ id = 2, parent = 1, acronym = "Br", name = "Brain", color = [120, 140, 200] }'


def test_palette_colours_are_far_apart():
    assert len(PALETTE) == 20
    assert min(delta_e(a, b) for a, b in itertools.combinations(PALETTE, 2)) >= 20


def test_near_members_get_clearly_different_colours():
    centres = {i: np.array([[i * 4.0, 0.0, 0.0]]) for i in range(12)}
    colours = distinct_colours(list(range(12)), centres)
    near = [(a, b) for a, b in itertools.combinations(range(12), 2) if abs(a - b) * 4 < NEAR_MM]
    assert near and all(delta_e(colours[a], colours[b]) >= 20 for a, b in near)


def test_crowded_members_still_get_colours():
    centres = {i: np.zeros((1, 3)) for i in range(30)}
    colours = distinct_colours(list(range(30)), centres)
    assert sorted(colours) == list(range(30)) and set(colours.values()) <= set(PALETTE)


def palette_build(tmp_path, palette):
    archive, sha256 = make_source_archive(tmp_path / "upstream")
    src = write_source_tree(tmp_path / "src", archive, sha256)
    path = src / "structures.toml"
    path.write_text(path.read_text().replace(BRAIN, BRAIN[:-2] + f', palette = "{palette}" }}'))
    out = build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    return Atlas.open(out)


def test_distinct_palette_colours_members_and_keeps_sides_together(tmp_path):
    atlas = palette_build(tmp_path, "distinct")
    alpha, gamma = atlas.get(100).rgb_triplet, atlas.get(120).rgb_triplet
    assert alpha in PALETTE and gamma in PALETTE and alpha != gamma
    assert atlas.get(101).rgb_triplet == atlas.get(102).rgb_triplet == alpha


def test_alternate_shades_neighbouring_children(tmp_path):
    atlas = palette_build(tmp_path, "alternate")
    brain = (120, 140, 200)
    assert atlas.get(100).rgb_triplet == shade(brain, ALTERNATE)
    assert atlas.get(120).rgb_triplet == shade(brain, -ALTERNATE)


@pytest.mark.parametrize("palette", ["distinct", "alternate"])
def test_explicit_colours_win_over_palettes(tmp_path, palette):
    assert palette_build(tmp_path, palette).get(110).rgb_triplet == (230, 120, 120)


def test_an_unknown_palette_is_a_problem(tmp_path):
    archive, sha256 = make_source_archive(tmp_path / "upstream")
    src = write_source_tree(tmp_path / "src", archive, sha256)
    path = src / "structures.toml"
    path.write_text(path.read_text().replace(BRAIN, BRAIN[:-2] + ', palette = "rainbow" }'))
    assert "group 2: unknown palette 'rainbow'" in check_hierarchy(load_structures(path))
    with pytest.raises(BuildError):
        build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
