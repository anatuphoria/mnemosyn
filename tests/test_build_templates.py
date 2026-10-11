import nibabel as nib
import numpy as np

from tools.build_atlas.templates import covers, on_grid, to_uint8


def test_to_uint8_maps_percentiles_to_full_range():
    data = np.arange(1000, dtype=np.float32)
    out = to_uint8(data)
    assert out.dtype == np.uint8
    assert out[0] == 0 and out[-1] == 255
    assert 120 <= out[500] <= 135


def test_to_uint8_of_constant_data_is_zero():
    assert not to_uint8(np.full((3, 3), 7.0)).any()


def test_on_grid_resamples_linearly_and_covers():
    image = nib.Nifti1Image(np.arange(8, dtype=np.float32).reshape(2, 2, 2) * 10,
                            np.diag([2.0, 2.0, 2.0, 1.0]))
    target = np.eye(4)
    assert covers(image, (3, 3, 3), target)
    data = on_grid(image, (3, 3, 3), target)
    assert data.shape == (3, 3, 3) and data.dtype == np.float32
    assert np.isclose(data[1, 0, 0], 20.0)
    assert not covers(image, (6, 6, 6), target)
