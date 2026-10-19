import numpy as np
import pytest

from cns_atlas.model import Structure
from cns_desktop.slices import (centre_from_table, centre_mm, color_table, compose, draw_tract,
                                extract, index_for_mm, label_centres, mask_table, mm_for_index,
                                over, overlay, pixels_for_voxels, slice_count, voxel_for_pixel,
                                world_for_voxel)
from timing_baseline import best_of

AAL = np.array([[1.0, 0, 0, -90.0], [0, 1.0, 0, -126.0], [0, 0, 1.0, -72.0], [0, 0, 0, 1.0]])
COLORS = np.array([[0, 0, 0], [200, 0, 0], [0, 200, 0]], dtype=np.uint8)
NONE = np.zeros(3, dtype=bool)


def test_neurological_orientation():
    volume = np.zeros((4, 5, 6), dtype=np.uint16)
    volume[0, 4, 2] = 1
    volume[0, 4, 5] = 2
    volume[0, 3, 5] = 3
    assert extract(volume, np.eye(4), "axial", 2)[0, 0] == 1
    assert extract(volume, np.eye(4), "coronal", 4)[0, 0] == 2
    assert extract(volume, np.eye(4), "sagittal", 0)[0, 0] == 2
    assert extract(volume, np.eye(4), "sagittal", 0)[0, 1] == 3
    assert extract(volume, np.eye(4), "axial", 2).shape == (5, 4)
    assert extract(volume, np.eye(4), "coronal", 4).shape == (6, 4)
    assert extract(volume, np.eye(4), "sagittal", 0).shape == (6, 5)


def test_non_ras_volume_is_refused():
    with pytest.raises(ValueError, match="RAS"):
        extract(np.zeros((2, 2, 2)), np.diag([-1.0, 1.0, 1.0, 1.0]), "axial", 0)


@pytest.mark.parametrize("axis, index", [("axial", 3), ("coronal", 1), ("sagittal", 4)])
def test_voxel_for_pixel_inverts_extract(axis, index):
    volume = np.random.default_rng(0).integers(0, 1000, size=(5, 6, 7))
    image = extract(volume, np.eye(4), axis, index)
    for row in range(image.shape[0]):
        for col in range(image.shape[1]):
            assert image[row, col] == volume[voxel_for_pixel(volume.shape, axis, index, row, col)]


def test_millimetres_and_indices():
    shape = (181, 217, 181)
    assert slice_count(shape, "coronal") == 217
    assert index_for_mm(AAL, shape, "axial", 0.0) == 72
    assert mm_for_index(AAL, "axial", 72) == 0.0
    assert mm_for_index(AAL, "sagittal", 0) == -90.0
    assert index_for_mm(AAL, shape, "coronal", -500.0) == 0
    assert index_for_mm(AAL, shape, "coronal", 500.0) == 216
    assert world_for_voxel(AAL, (90, 126, 72)) == (0.0, 0.0, 0.0)


def test_compose_blends_labels_over_template():
    labels = np.array([[0, 1], [2, 0]])
    template = np.array([[100, 100], [100, 50]], dtype=np.uint8)
    rgba = compose(labels, template, COLORS, NONE, NONE, opacity=0.5)
    assert rgba.shape == (2, 2, 4) and rgba.dtype == np.uint8
    assert tuple(rgba[0, 0]) == (100, 100, 100, 255)
    assert tuple(rgba[0, 1]) == (150, 50, 50, 255)
    assert tuple(rgba[1, 0]) == (50, 150, 50, 255)


def test_compose_without_template_uses_black():
    rgba = compose(np.array([[0, 1]]), None, COLORS, NONE, NONE, opacity=0.5)
    assert tuple(rgba[0, 0]) == (0, 0, 0, 255)
    assert tuple(rgba[0, 1]) == (100, 0, 0, 255)


def block_labels():
    labels = np.zeros((5, 5), dtype=np.int64)
    labels[1:4, 1:4] = 1
    return labels, np.full((5, 5), 80, dtype=np.uint8)


def test_hidden_structures_are_not_coloured():
    labels, template = block_labels()
    rgba = compose(labels, template, COLORS, mask_table(3, [1]), NONE)
    assert tuple(rgba[2, 2]) == (80, 80, 80, 255)


def test_selected_structures_are_full_colour_with_white_outline():
    labels, template = block_labels()
    rgba = compose(labels, template, COLORS, NONE, mask_table(3, [1]))
    assert tuple(rgba[1, 1]) == (255, 255, 255, 255)
    assert tuple(rgba[2, 2]) == (200, 0, 0, 255)
    assert tuple(rgba[0, 0]) == (80, 80, 80, 255)


def test_selected_but_hidden_is_not_drawn():
    labels, template = block_labels()
    rgba = compose(labels, template, COLORS, mask_table(3, [1]), mask_table(3, [1]))
    assert (rgba[..., :3] == 80).all()


def test_color_and_mask_tables():
    structures = [Structure(1, "A", "A", (1,), (1, 2, 3)),
                  Structure(5, "B", "B", (1, 5), (9, 8, 7))]
    table = color_table(structures)
    assert table.shape == (6, 3) and tuple(table[5]) == (9, 8, 7) and tuple(table[2]) == (0, 0, 0)
    assert mask_table(4, [1, 3, 99]).tolist() == [False, True, False, True]


def test_centre_mm():
    volume = np.zeros((10, 10, 10), dtype=np.uint16)
    volume[2:5, 4:7, 6:9] = 5
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[:3, 3] = [-10.0, -10.0, -10.0]
    assert centre_mm(volume, affine, [5]) == (-4.0, 0.0, 4.0)
    assert centre_mm(volume, affine, [7]) is None


@pytest.mark.perf
def test_label_layer_of_a_full_slice_under_5ms(timing):
    rng = np.random.default_rng(1)
    labels = rng.integers(0, 2500, size=(217, 181))
    colors = rng.integers(0, 255, size=(2501, 3)).astype(np.uint8)
    hidden = mask_table(2501, range(0, 2500, 7))
    selected = mask_table(2501, range(100, 200))
    best = best_of(lambda: overlay(labels, colors, hidden, selected))
    timing.assert_within({"label layer of a full slice": (best, 0.005)})


def test_a_filled_tract_at_zero_opacity_warns_nothing():
    import warnings

    layer = np.zeros((4, 4, 4), np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        draw_tract(layer, np.array([1, 2]), np.array([1, 1]), (200, 0, 0), True, 0.0)
    assert layer[1, 1, 3] == 255 and layer[1, 1, :3].tolist() == [200, 0, 0]


def test_label_centre_table_matches_the_volume_scan():
    rng = np.random.default_rng(4)
    volume = rng.integers(0, 6, size=(23, 17, 11)).astype(np.uint16)
    volume[volume == 5] = 0
    affine = np.array([[2.0, 0, 0, -20.0], [0, 3.0, 0, -9.0], [0, 0, 1.5, 4.0], [0, 0, 0, 1.0]])
    table = label_centres(volume, step=4)
    for ids in ([1], [2, 3], [1, 2, 3, 4]):
        assert np.allclose(centre_from_table(table, affine, ids), centre_mm(volume, affine, ids))
    assert centre_from_table(table, affine, [5]) is None
    assert centre_from_table(table, affine, [99]) is None
    assert centre_from_table(table, affine, []) is None


def test_pixels_for_voxels_inverts_voxel_for_pixel():
    shape = (5, 6, 7)
    for axis in ("axial", "coronal", "sagittal"):
        for row, col in ((0, 0), (2, 3), (4, 1)):
            voxel = voxel_for_pixel(shape, axis, 2, row, col)
            rows, cols = pixels_for_voxels(shape, axis, tuple(np.array([v]) for v in voxel))
            assert (int(rows[0]), int(cols[0])) == (row, col), axis


def test_draw_tract_outlines_and_fills():
    image = np.zeros((6, 6, 4), dtype=np.uint8)
    image[..., 3] = 255
    rows = np.array([1, 1, 1, 2, 2, 2, 3, 3, 3])
    cols = np.array([1, 2, 3] * 3)
    color = np.array([200, 100, 0], dtype=np.uint8)
    draw_tract(image, rows, cols, color, False, 0.5)
    assert image[1, 1, :3].tolist() == [200, 100, 0]
    assert image[2, 2, :3].tolist() == [0, 0, 0]
    draw_tract(image, rows, cols, color, True, 0.5)
    assert image[2, 2, :3].tolist() == [100, 50, 0]
    assert image[0, 0, :3].tolist() == [0, 0, 0]


def test_is_ras_matches_nibabel_for_axis_flips_swaps_and_tilts():
    import itertools

    import nibabel as nib

    from cns_desktop.slices import is_ras

    rng = np.random.default_rng(3)
    for order in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            affine = np.eye(4)
            affine[:3, :3] = np.eye(3)[list(order)] * np.array(signs)[:, None] * 0.5
            affine[:3, :3] += rng.normal(0, 0.05, (3, 3))
            expected = nib.aff2axcodes(affine) == ("R", "A", "S")
            assert is_ras(affine) == expected


def test_is_ras_is_cheap():
    import time

    from cns_desktop.slices import is_ras

    affine = np.diag([0.5, 0.5, 0.5, 1.0])
    start = time.perf_counter()
    for _ in range(1000):
        is_ras(affine)
    assert (time.perf_counter() - start) / 1000 < 20e-6


def test_overlay_over_template_matches_compose():
    rng = np.random.default_rng(3)
    labels = rng.integers(0, 6, size=(20, 30))
    template = rng.integers(0, 255, size=(20, 30)).astype(np.uint8)
    colors = rng.integers(0, 255, size=(6, 3)).astype(np.uint8)
    hidden, selected = mask_table(6, [2]), mask_table(6, [4])
    composed = compose(labels, template, colors, hidden, selected, 0.45)
    layered = over(template, overlay(labels, colors, hidden, selected, 0.45))
    assert np.abs(composed.astype(int) - layered.astype(int)).max() <= 1


def test_overlay_is_clear_where_nothing_is_drawn():
    labels = np.array([[0, 1], [2, 0]])
    colors = np.full((3, 3), 200, np.uint8)
    layer = overlay(labels, colors, mask_table(3, [2]), mask_table(3, []))
    assert layer[0, 0, 3] == 0 and layer[1, 0, 3] == 0 and layer[0, 1, 3] == round(0.45 * 255)


def test_a_filled_tract_on_the_overlay_blends_like_on_the_picture():
    template = np.full((4, 4), 100, np.uint8)
    labels = np.zeros((4, 4), int)
    labels[1, 1] = 1
    colors = np.array([[0, 0, 0], [200, 0, 0]], np.uint8)
    picture = compose(labels, template, colors, mask_table(2, []), mask_table(2, []))
    layer = overlay(labels, colors, mask_table(2, []), mask_table(2, []))
    rows, cols = np.array([1, 1, 2]), np.array([1, 2, 2])
    draw_tract(picture, rows, cols, (0, 0, 250), True, 0.45)
    draw_tract(layer, rows, cols, (0, 0, 250), True, 0.45)
    assert np.abs(picture.astype(int) - over(template, layer).astype(int)).max() <= 1
