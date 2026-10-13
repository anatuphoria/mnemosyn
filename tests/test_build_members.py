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


def manual_tree(tmp_path):
    return write_extended_source_tree(tmp_path, tracts=False, members="manual")


def test_a_missing_manual_source_stops_the_build_before_any_download(tmp_path):
    src = manual_tree(tmp_path)
    cache = tmp_path / "cache"
    with pytest.raises(BuildError) as error:
        quiet_build(src, tmp_path / "out", cache)
    sha = members_spec(src).sha256
    assert error.value.problems == [
        f"source toymembers: download toy_members.zip from https://example.org/toy-masks "
        f"and put it in {cache / sha}"]
    assert not cache.exists()


def test_a_manual_dir_is_used_and_cached(tmp_path):
    src = manual_tree(tmp_path)
    cache = tmp_path / "cache"
    quiet_build(src, tmp_path / "out", cache, manual_dir=tmp_path / "upstream" / "members")
    assert (cache / members_spec(src).sha256 / "toy_members.zip").exists()
    out = quiet_build(src, tmp_path / "again", cache)
    assert Atlas.open(out).has_mesh(190)


def test_a_wrong_manual_file_is_refused(tmp_path):
    src = manual_tree(tmp_path)
    wrong = tmp_path / "wrong"
    wrong.mkdir()
    (wrong / "toy_members.zip").write_bytes(b"not the file")
    with pytest.raises(BuildError) as error:
        quiet_build(src, tmp_path / "out", tmp_path / "cache", manual_dir=wrong)
    assert error.value.problems[0].startswith("source toymembers: checksum mismatch (expected ")


def test_a_normal_build_does_not_ask_for_a_local_only_manual_source(tmp_path):
    src = manual_tree(tmp_path)
    edit(src / "recipe.toml", 'redistribution = true\nurl = "https://example.org/toy-masks"',
         'redistribution = false\nlocal_only = true\nurl = "https://example.org/toy-masks"')
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache"))
    assert 190 not in atlas


def test_the_command_line_takes_a_manual_dir(tmp_path):
    from tools.build_atlas.__main__ import main

    src = manual_tree(tmp_path)
    assert main(["--src", str(src), "--out", str(tmp_path / "out"), "--cache",
                 str(tmp_path / "cache"), "--manual-dir",
                 str(tmp_path / "upstream" / "members")]) == 0


def blobs_file(tmp_path):
    data = np.zeros((40, 30, 80), dtype=np.float32)
    data[10:14, 5:9, 20:25] = 2.0
    data[20:22, 12:15, 60:63] = 5.0
    affine = np.array([[0.5, 0, 0, -10.0], [0, 0.5, 0, -7.0], [0, 0, 0.5, -20.0],
                       [0, 0, 0, 1.0]])
    path = tmp_path / "fine.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), path)
    return path, data, affine


def world(image, value):
    index = np.argwhere(np.asarray(image.dataobj) == value)
    return np.sort(nib.affines.apply_affine(image.affine, index), axis=0)


def test_a_cropped_read_keeps_the_box_and_the_positions(tmp_path, monkeypatch):
    import tools.build_atlas.labels as labels

    monkeypatch.setattr(labels, "CROP_SLAB", 8)
    path, data, affine = blobs_file(tmp_path)
    full = labels.load_label_image(path)
    cut = labels.load_label_image(path, cropped=True)
    assert cut.shape == (14, 12, 45)
    for value in (2, 5):
        assert np.allclose(world(cut, value), world(full, value))


def test_a_source_without_labels_cannot_be_cropped(tmp_path):
    from tools.build_atlas.labels import load_label_image

    path = tmp_path / "empty.nii.gz"
    nib.save(nib.Nifti1Image(np.zeros((4, 4, 4), dtype=np.float32), np.eye(4)), path)
    with pytest.raises(BuildError) as error:
        load_label_image(path, name="empty", cropped=True)
    assert error.value.problems == ["source empty: has no labels"]


def test_a_cropped_build_gives_the_same_shapes(tmp_path):
    plain = write_extended_source_tree(tmp_path / "a", tracts=False)
    cut = write_extended_source_tree(tmp_path / "b", tracts=False)
    edit(cut / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\ncrop = true\n')
    first = Atlas.open(quiet_build(plain, tmp_path / "a" / "out", tmp_path / "cache"))
    second = Atlas.open(quiet_build(cut, tmp_path / "b" / "out", tmp_path / "cache"))
    for structure_id in (131, 132):
        assert np.allclose(np.asarray(first.mesh(structure_id).vertices),
                           np.asarray(second.mesh(structure_id).vertices), atol=1e-4)
    assert np.array_equal(np.asarray(first.volumes[0].data), np.asarray(second.volumes[0].data))


def bad_cache(src, cache):
    target = cache / members_spec(src).sha256 / "toy_members.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"half a download")
    return target


def test_a_bad_cached_manual_file_names_the_file_to_delete(tmp_path):
    src = manual_tree(tmp_path)
    target = bad_cache(src, tmp_path / "cache")
    with pytest.raises(BuildError) as error:
        quiet_build(src, tmp_path / "out", tmp_path / "cache")
    assert error.value.problems == [
        f"source toymembers: {target} does not match its checksum; delete it and download "
        f"toy_members.zip again from https://example.org/toy-masks"]


def test_a_manual_dir_replaces_a_bad_cached_file(tmp_path):
    from tools.build_atlas.fetch import sha256_of

    src = manual_tree(tmp_path)
    target = bad_cache(src, tmp_path / "cache")
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache",
                      manual_dir=tmp_path / "upstream" / "members")
    assert Atlas.open(out).has_mesh(190)
    assert sha256_of(target) == members_spec(src).sha256


def test_a_cropped_read_keeps_the_gzip_open_between_slabs(tmp_path, monkeypatch):
    import tools.build_atlas.labels as labels

    seen = []
    real = labels.nib.load
    monkeypatch.setattr(labels.nib, "load", lambda path, **kw: seen.append(kw) or real(path, **kw))
    path, _, _ = blobs_file(tmp_path)
    labels.load_label_image(path, cropped=True)
    assert seen == [{"keep_file_open": True}]
