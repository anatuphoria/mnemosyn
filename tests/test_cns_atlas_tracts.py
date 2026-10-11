import shutil

import numpy as np
import pytest

from cns_atlas import Atlas, AtlasError


def test_the_tract_layer_loads_with_sorted_voxels(toy_tract_atlas):
    layer = Atlas.open(toy_tract_atlas).tracts
    assert layer is not None and layer.ids == (151, 152, 160)
    assert layer.shape == (40, 48, 36)
    assert len(layer.voxels(151)) == 384 and layer.size(160) == 72
    assert np.all(np.diff(np.asarray(layer.voxels(151), dtype=np.int64)) > 0)
    assert len(layer.voxels(999)) == 0


def test_tracts_at_lists_the_smallest_tract_first(toy_tract_atlas):
    layer = Atlas.open(toy_tract_atlas).tracts
    assert layer.tracts_at((-48.0, -44.0, -4.0)) == (160, 151)
    assert layer.tracts_at((-40.0, -48.0, 16.0)) == (151,)
    assert layer.tracts_at((0.0, 60.0, 0.0)) == ()
    assert layer.tracts_at((500.0, 0.0, 0.0)) == ()


def test_an_atlas_without_tracts_has_no_layer(toy_atlas):
    assert Atlas.open(toy_atlas).tracts is None


@pytest.mark.parametrize("damage", ["offsets", "missing"])
def test_a_damaged_tract_layer_raises(toy_tract_atlas, tmp_path, damage):
    root = shutil.copytree(toy_tract_atlas, tmp_path / "pkg")
    if damage == "offsets":
        np.save(root / "tracts" / "offsets.npy", np.array([0, 500, 400, 840], dtype=np.int64))
    else:
        (root / "tracts" / "voxels.npy").unlink()
    with pytest.raises(AtlasError, match="tracts"):
        Atlas.open(root)
