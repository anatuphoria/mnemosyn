import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import write_extended_source_tree
from tools.build_atlas.hierarchy import load_structures
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
