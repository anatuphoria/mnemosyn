import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import (AFFINE, BLOBS, SPINE_AFFINE, spine_volume,
                            write_extended_source_tree)
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.labels import load_parts, trim_against
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import check_sources


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def parts_file(tmp_path, data, affine=None):
    path = tmp_path / "parts.nii.gz"
    affine = np.eye(4) if affine is None else affine
    nib.save(nib.Nifti1Image(data.astype(np.float32), affine), path)
    return path


def test_parts_fill_every_voxel_of_the_whole(tmp_path):
    data = np.zeros((6, 1, 1, 4), dtype=np.float32)
    data[:, 0, 0, 0] = 1.0
    data[0, 0, 0] = (0.1, 0.9, 0.0, 0.0)
    data[1, 0, 0] = (0.2, 0.0, 0.8, 0.0)
    data[2, 0, 0] = (0.3, 0.3, 0.3, 0.1)
    data[3, 0, 0] = (0.2, 0.1, 0.2, 0.5)
    data[4, 0, 0] = (0.6, 0.2, 0.1, 0.1)
    values = np.asarray(load_parts(parts_file(tmp_path, data), (1, 2), 0.5).dataobj)[:, 0, 0]
    assert values.tolist() == [1, 2, 1, 2, 0, 0]


def test_a_part_beyond_the_channels_stops_the_build(tmp_path):
    with pytest.raises(BuildError) as error:
        load_parts(parts_file(tmp_path, np.zeros((3, 3, 3, 3))), (1, 9), 0.5, name="toyparts")
    assert error.value.problems == ["source toyparts: part 9 is not a channel of the image "
                                    "(it has 3)"]


def test_a_3d_image_cannot_be_read_as_parts(tmp_path):
    with pytest.raises(BuildError) as error:
        load_parts(parts_file(tmp_path, np.zeros((3, 3, 3))), (1,), 0.5, name="flat")
    assert error.value.problems == ["source flat: parts need a 4D probability image"]


def test_trim_clears_voxels_under_other_labels_only():
    image = nib.Nifti1Image(np.ones((10, 10, 10), dtype=np.int32), np.eye(4))
    other = np.zeros((10, 10, 10), dtype=np.uint16)
    other[:, :, :3] = 7
    other[:, :, 3:5] = 3
    kept = np.asarray(trim_against(image, other, np.eye(4), allowed={3}).dataobj)
    assert (kept[:, :, :3] == 0).all() and (kept[:, :, 3:] == 1).all()
    cleared = np.asarray(trim_against(image, other, np.eye(4), allowed=None).dataobj)
    assert (cleared[:, :, :5] == 0).all() and (cleared[:, :, 5:] == 1).all()


def test_trim_reads_the_other_volume_on_its_own_grid():
    image = nib.Nifti1Image(np.ones((10, 10, 10), dtype=np.int32), np.eye(4))
    other = np.zeros((10, 10, 10), dtype=np.uint16)
    other[:, :, :3] = 7
    shifted = np.eye(4)
    shifted[2, 3] = 4.0
    trimmed = np.asarray(trim_against(image, other, shifted, allowed=None).dataobj)
    assert (trimmed[:, :, :4] == 1).all() and (trimmed[:, :, 4:7] == 0).all()
    assert (trimmed[:, :, 7:] == 1).all()


def alpha_left_world():
    centre, radii = BLOBS[1]
    return AFFINE @ np.append(centre, 1.0), np.array(radii) * 4.0


def deep_inside_alpha(points, margin=4.0):
    centre, radii = alpha_left_world()
    shrunk = np.maximum(radii - margin, 0.1)
    return (((points - centre[:3]) / shrunk) ** 2).sum(axis=1) <= 1.0


def test_bodies_yield_to_labels_outside_their_group(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, shells=True)
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    points = np.asarray(atlas.mesh(230).vertices)
    assert atlas.get(230).kind == "shell" and not deep_inside_alpha(points).any()
    assert atlas.has_mesh(240)


def test_bodies_inside_their_own_group_are_kept_whole(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, shells=True)
    recipe = src / "recipe.toml"
    recipe.write_text(recipe.read_text().replace("trim_outside = 6", "trim_outside = 2"))
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    assert deep_inside_alpha(np.asarray(atlas.mesh(230).vertices)).any()


def test_a_normal_build_leaves_the_bodies_out(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, shells=True)
    (tmp_path / "upstream" / "toy_body.nii.gz").unlink()
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache"))
    assert 230 not in atlas and 240 not in atlas
    assert all(i in atlas for i in (101, 102, 111, 112, 120))


def spine_box():
    index = np.argwhere(spine_volume() > 0)
    corners = np.c_[np.r_[index - 0.5, index + 0.5], np.ones(2 * len(index))] @ SPINE_AFFINE.T
    return corners[:, :3].min(axis=0), corners[:, :3].max(axis=0)


def test_bodies_stop_where_the_cord_begins(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, spine=True, shells=True)
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    points = np.asarray(atlas.mesh(240).vertices)
    lo, hi = spine_box()
    assert not ((points > lo + 1.0) & (points < hi - 1.0)).all(axis=1).any()
    assert len(points)


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def test_parts_need_a_threshold(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, shells=True)
    recipe = src / "recipe.toml"
    recipe.write_text(recipe.read_text().replace("threshold = 0.5\n", ""))
    assert "source toybody: parts need a threshold" in problems_for(src)


def test_trim_outside_must_name_a_group(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, shells=True)
    recipe = src / "recipe.toml"
    recipe.write_text(recipe.read_text().replace("trim_outside = 6", "trim_outside = 100"))
    assert "source toybody: trim_outside 100 is not a group" in problems_for(src)
