import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import MEMBER_AFFINE, write_extended_source_tree, write_member_archive
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import LabelRef, load_structures, resolve_members
from tools.build_atlas.labels import load_members
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import check_sources


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def edit(path, old, new):
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))


def members_spec(src):
    return next(s for s in load_recipe(src / "recipe.toml").sources
                if s.source.id == "toymembers")


def test_the_recipe_reads_members_in_order(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    spec = members_spec(src)
    assert spec.members == (("Pair_L", "MEM/Pair_L.nii"), ("Pair_R", "MEM/Pair_R.nii"),
                            ("Mid", "MEM/Mid.nii"))
    assert spec.member_values == {"Pair_L": 1, "Pair_R": 2, "Mid": 3}
    assert not spec.manual and not spec.crop
    assert problems_for(src) == []


@pytest.mark.parametrize(("where", "old", "new", "message"), [
    ("recipe", 'url = "https://example.org/toy-masks"\n',
     'url = "https://example.org/toy-masks"\nmember = "MEM/Mid.nii"\n',
     "source toymembers: give member or members, not both"),
    ("structures", 'midline = "Mid"', 'midline = "Midd"',
     "structure 190: source toymembers has no member 'Midd'"),
    ("structures", 'midline = "Mid"', 'midline = "Midd"',
     "source toymembers: member 'Mid' has no structure"),
    ("structures", 'midline = "Mid"', "midline = 3",
     "structure 190: source toymembers needs a member name, not 3"),
])
def test_member_rules(tmp_path, where, old, new, message):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    edit(src / f"{where}.toml", old, new)
    assert message in problems_for(src)


def test_member_names_resolve_to_label_numbers():
    from tools.build_atlas.hierarchy import RawStructure

    raw = RawStructure(id=191, parent=190, acronym="X", name="X", kind="nucleus", side="left",
                       concept=190, color=None, synonyms=(), xrefs={}, sources=("m",),
                       labels=(LabelRef("m", "Mid"), LabelRef("other", 4)))
    [out] = resolve_members([raw], {"m": {"Mid": 3}})
    assert out.labels == (LabelRef("m", 3), LabelRef("other", 4))


def test_overlapping_members_keep_the_first_and_report_the_rest(tmp_path):
    archive = write_member_archive(tmp_path / "m")
    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    image, lost = load_members(members_spec(src), archive)
    data = np.asarray(image.dataobj)
    assert lost == 200
    assert (data[8, 5:15, 5:15] == 1).all() and (data[12, 5:15, 5:15] == 2).all()
    assert (data[9:12, 5:15, 5:15] == 3).all() and (data == 3).sum() == 300


def test_a_member_on_another_grid_stops_the_build(tmp_path):
    moved = MEMBER_AFFINE.copy()
    moved[0, 3] += 2.0
    archive = write_member_archive(tmp_path / "m", affines={"Mid": moved})
    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    with pytest.raises(BuildError) as error:
        load_members(members_spec(src), archive)
    assert error.value.problems == ["source toymembers: member Mid is on another grid"]


def test_a_build_shapes_every_member_and_reports_overlaps(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    atlas = Atlas.open(out)
    assert atlas.has_mesh(181) and atlas.has_mesh(182) and atlas.has_mesh(190)
    x = np.asarray(atlas.mesh(190).vertices)[:, 0]
    assert x.min() > -4.0 and x.max() < 4.0
    assert "- overlapping voxels in toymembers: 200\n" in (out / "build-report.md").read_text()
