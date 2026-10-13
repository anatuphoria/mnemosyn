import dataclasses
import json
import zipfile

import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import SPINE_AFFINE, spine_volume, write_extended_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.labels import load_label_image, load_members
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import check_sources, check_templates


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def edit(path, old, new):
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))


def spec_of(src, name):
    return next(s for s in load_recipe(src / "recipe.toml").sources if s.source.id == name)


def test_a_mask_threshold_keeps_values_at_or_above_it(tmp_path):
    path = tmp_path / "p.nii.gz"
    nib.save(nib.Nifti1Image(np.array([[[0.2, 0.6], [0.5, 0.0]]], dtype=np.float32), np.eye(4)),
             path)
    data = np.asarray(load_label_image(path, mask=True, threshold=0.5).dataobj)
    assert data.tolist() == [[[0, 1], [1, 0]]]


def test_members_use_the_threshold(tmp_path):
    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    archive = tmp_path / "prob.zip"
    shape = (20, 20, 20)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, value in (("Pair_L", 0.4), ("Pair_R", 0.7), ("Mid", 0.5)):
            data = np.zeros(shape, dtype=np.float32)
            data[5:8, 5:8, 5:8] = value
            data[0, 0, {"Pair_L": 1, "Pair_R": 2, "Mid": 3}[name]] = 0.9
            zipped.writestr(f"MEM/{name}.nii", nib.Nifti1Image(data, affine).to_bytes())
    spec = dataclasses.replace(spec_of(src, "toymembers"), threshold=0.5)
    image, lost = load_members(spec, archive)
    data = np.asarray(image.dataobj)
    assert (data[5:8, 5:8, 5:8] == 2).all() and lost == 27
    assert data[0, 0, 1] == 1 and data[0, 0, 3] == 3


def blobs(tmp_path):
    data = np.zeros((40, 30, 80), dtype=np.float32)
    data[10:14, 5:9, 20:25] = 2.0
    data[20:22, 12:15, 60:63] = 5.0
    affine = np.array([[0.5, 0, 0, -10.0], [0, 0.5, 0, -7.0], [0, 0, 0.5, -20.0],
                       [0, 0, 0, 1.0]])
    path = tmp_path / "fine.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), path)
    return path


def test_a_crop_margin_grows_the_box_and_keeps_positions(tmp_path):
    path = blobs(tmp_path)
    full = load_label_image(path)
    cut = load_label_image(path, cropped=True, margin=1.0)
    assert cut.shape == (18, 16, 49)
    for value in (2, 5):
        a = nib.affines.apply_affine(full.affine, np.argwhere(np.asarray(full.dataobj) == value))
        b = nib.affines.apply_affine(cut.affine, np.argwhere(np.asarray(cut.dataobj) == value))
        assert np.allclose(np.sort(a, axis=0), np.sort(b, axis=0))


def test_a_crop_margin_stops_at_the_image_edge(tmp_path):
    assert load_label_image(blobs(tmp_path), cropped=True, margin=100.0).shape == (40, 30, 80)


def test_the_recipe_reads_threshold_and_margin(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    edit(src / "recipe.toml", 'url = "https://example.org/toy-masks"\n',
         'url = "https://example.org/toy-masks"\nthreshold = 0.5\n')
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\ncrop = true\nmargin = 3\n')
    assert spec_of(src, "toymembers").threshold == 0.5
    assert spec_of(src, "toyhyp").margin == 3.0 and spec_of(src, "toyhyp").threshold is None
    assert problems_for(src) == []


def test_a_threshold_needs_mask_or_members(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False)
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\nthreshold = 0.5\n')
    assert "source toyhyp: threshold needs mask = true or members" in problems_for(src)


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def spine_tree(tmp_path):
    return write_extended_source_tree(tmp_path, tracts=False, spine=True)


def test_a_spine_tree_passes_every_check(tmp_path):
    src = spine_tree(tmp_path)
    recipe = load_recipe(src / "recipe.toml")
    assert problems_for(src) == [] and check_templates(recipe, src) == []
    assert [t.source.id for t in recipe.templates if t.local_only] == ["toyspine-t2"]


def test_a_shared_source_on_a_local_only_volume_is_refused(tmp_path):
    src = spine_tree(tmp_path)
    edit(src / "recipe.toml", 'volume = "brain"\npriority = 0\ndrop = [4]',
         'volume = "spine"\npriority = 0\ndrop = [4]')
    assert ("volume spine: grid source 'toyspine' is local-only, so every source and template "
            "of the volume must be local-only") in problems_for(src)


def test_a_shareable_template_cannot_be_local_only(tmp_path):
    src = spine_tree(tmp_path)
    edit(src / "recipe.toml", 'title = "Toy spinal template"\nauthors = "Test G"\nyear = 2024\n'
         'version = "1"\nlicence = "No licence stated"\nredistribution = false',
         'title = "Toy spinal template"\nauthors = "Test G"\nyear = 2024\n'
         'version = "1"\nlicence = "No licence stated"\nredistribution = true')
    assert ("template toyspine-t2: a shareable template must not be local-only"
            in check_templates(load_recipe(src / "recipe.toml"), src))


def test_a_normal_build_leaves_the_spine_volume_out(tmp_path):
    with_spine = quiet_build(spine_tree(tmp_path / "a"), tmp_path / "a" / "out", tmp_path / "c")
    plain = quiet_build(write_extended_source_tree(tmp_path / "b", tracts=False),
                        tmp_path / "b" / "out", tmp_path / "c")
    for name in ("structures.json", "sources.json", "volumes/brain.nii.gz"):
        assert (with_spine / name).read_bytes() == (plain / name).read_bytes(), name
    metadata = json.loads((with_spine / "metadata.json").read_text())
    assert [v["file"] for v in metadata["volumes"]] == [v["file"] for v in json.loads(
        (plain / "metadata.json").read_text())["volumes"]]
    assert not (with_spine / "volumes" / "spine.nii.gz").exists()
    report = (with_spine / "build-report.md").read_text()
    assert "- local-only sources left out: toyspine, toyspine-t2\n" in report


def test_a_local_build_adds_a_ras_spine_volume_and_template(toy_spine_atlas):
    atlas = Atlas.open(toy_spine_atlas)
    assert [v.name for v in atlas.volumes] == ["brain", "spine"]
    spine = atlas.volumes[1]
    assert nib.aff2axcodes(spine.affine) == ("R", "A", "S") and spine.shape == (10, 10, 56)
    for value, structure_id in ((1, 200), (2, 210)):
        want = nib.affines.apply_affine(SPINE_AFFINE, np.argwhere(spine_volume() == value))
        got = nib.affines.apply_affine(spine.affine,
                                       np.argwhere(np.asarray(spine.data) == structure_id))
        assert np.allclose(np.sort(want, axis=0), np.sort(got, axis=0))
    records = json.loads((toy_spine_atlas / "metadata.json").read_text())["volumes"]
    assert {"file": "volumes/spine-template.nii.gz", "labels": "spine"}.items() <= next(
        r for r in records if r.get("labels") == "spine").items()
    assert atlas.local_only == ("toyspine", "toyspine-t2")
    assert atlas.has_mesh(200) and atlas.has_mesh(210)
