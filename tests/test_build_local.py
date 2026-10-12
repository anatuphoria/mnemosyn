import json

import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import write_extended_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import load_structures, without_sources
from tools.build_atlas.idlock import load_lock
from tools.build_atlas.labels import load_label_image
from tools.build_atlas.recipe import load_recipe
from tools.build_atlas.validate import check_sources


@pytest.fixture
def local_src(tmp_path):
    return write_extended_source_tree(tmp_path, tracts=True, local=True)


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def edit_recipe(src, old, new):
    recipe = src / "recipe.toml"
    assert old in recipe.read_text()
    recipe.write_text(recipe.read_text().replace(old, new, 1))


def test_mask_sources_turn_every_nonzero_voxel_into_label_one(tmp_path):
    path = tmp_path / "gland.nii.gz"
    values = np.array([[[0.0, 0.3], [0.9, 0.0]]], dtype=np.float32)
    nib.save(nib.Nifti1Image(values, np.eye(4)), path)
    assert np.asarray(load_label_image(path, mask=True).dataobj).tolist() == [[[0, 1], [1, 0]]]
    assert np.asarray(load_label_image(path).dataobj).tolist() == [[[0, 0], [0, 0]]]


def test_recipe_reads_local_only_and_mask(local_src):
    spec = next(s for s in load_recipe(local_src / "recipe.toml").sources
                if s.source.id == "toylocal")
    assert spec.local_only and spec.mask and spec.priority == -1
    toy = next(s for s in load_recipe(local_src / "recipe.toml").sources if s.source.id == "toy")
    assert not toy.local_only and not toy.mask


def test_a_local_only_source_passes_the_source_checks(local_src):
    assert problems_for(local_src) == []


@pytest.mark.parametrize(("old", "new", "message"), [
    ("local_only = true\n", "", "source toylocal: redistribution is not allowed"),
    ("redistribution = false\nlocal_only = true", "redistribution = true\nlocal_only = true",
     "source toylocal: a shareable source must not be local-only"),
    ('grid_source = "toy"', 'grid_source = "toylocal"',
     "volume brain: grid source 'toylocal' is local-only"),
])
def test_local_only_recipe_rules(local_src, old, new, message):
    edit_recipe(local_src, old, new)
    assert message in problems_for(local_src)


def quiet_build(src, out, cache, local=False):
    return build(src, out, cache=cache, log=lambda *_: None, local=local)


def test_structures_shaped_only_by_skipped_sources_are_left_out(tmp_path):
    path = tmp_path / "s.toml"
    path.write_text("""\
default_source = "a"
groups = [
  { id = 1, acronym = "R", name = "Root" },
  { id = 2, parent = 1, acronym = "G", name = "Group" },
]
concepts = [
  { id = 10, parent = 2, acronym = "S", name = "Sided", source = "x", left = 1, right = 2 },
  { id = 20, parent = 2, acronym = "M", name = "Mid", source = "x", midline = 3 },
  { id = 30, parent = 2, acronym = "K", name = "Kept", midline = 4 },
]
""")
    raws = load_structures(path)
    assert [r.id for r in without_sources(raws, {"x"})] == [1, 2, 30]
    assert [r.id for r in without_sources(raws, set())] == [r.id for r in raws]


def test_a_normal_build_leaves_local_only_sources_out_without_fetching_them(local_src, tmp_path):
    (tmp_path / "upstream" / "toy_local.nii.gz").unlink()
    out = quiet_build(local_src, tmp_path / "out", tmp_path / "cache")
    atlas = Atlas.open(out)
    assert 170 not in atlas and atlas.local_only == () and "toylocal" not in atlas.sources
    assert "local_only" not in json.loads((out / "metadata.json").read_text())
    assert "- local-only sources left out: toylocal\n" in (out / "build-report.md").read_text()
    assert 170 in load_lock(local_src / "ids.lock").published


def test_a_local_build_includes_them_and_says_so(local_src, tmp_path):
    out = quiet_build(local_src, tmp_path / "out", tmp_path / "cache", local=True)
    atlas = Atlas.open(out)
    assert atlas.local_only == ("toylocal",) and atlas.has_mesh(170)
    assert atlas.sources["toylocal"].redistribution is False
    centre = np.asarray(atlas.mesh(170).vertices).mean(axis=0)
    assert np.allclose(centre, (0.0, 60.0, -20.0), atol=2.0)
    assert (np.asarray(atlas.volumes[0].data) == 170).any()
    assert "- local-only sources included: toylocal\n" in (out / "build-report.md").read_text()
    assert "Makes toy hormones" in atlas.knowledge(170).sections["Function"]


def test_a_normal_build_after_a_local_one_leaves_no_trace(local_src, tmp_path):
    out, cache = tmp_path / "out", tmp_path / "cache"
    quiet_build(local_src, out, cache, local=True)
    atlas = Atlas.open(quiet_build(local_src, out, cache))
    assert 170 not in atlas and atlas.local_only == ()


def test_local_without_local_only_sources_changes_nothing(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=True)
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True)
    assert "local_only" not in json.loads((out / "metadata.json").read_text())
    assert "local-only" not in (out / "build-report.md").read_text()


def test_cli_passes_local_to_the_build(monkeypatch, tmp_path):
    import tools.build_atlas.__main__ as cli

    seen = {}

    def fake(src, out, cache, local=False):
        seen["local"] = local
        return out

    monkeypatch.setattr(cli, "build", fake)
    assert cli.main(["--out", str(tmp_path / "o"), "--local"]) == 0 and seen == {"local": True}
    assert cli.main(["--out", str(tmp_path / "o")]) == 0 and seen == {"local": False}
