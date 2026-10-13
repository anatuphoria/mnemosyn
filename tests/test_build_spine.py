import dataclasses
import zipfile

import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import write_extended_source_tree
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.labels import load_label_image, load_members
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import check_sources


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
