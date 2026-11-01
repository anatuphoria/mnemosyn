import numpy as np
import pytest

from cns_atlas import Atlas
from cns_atlas.lesions import BROKEN, PARTLY, Lesion, hits, report, sphere, structure_lesion


@pytest.fixture(scope="module")
def atlas(toy_pathway_atlas):
    return Atlas.open(toy_pathway_atlas)


def brain(atlas):
    return atlas.volumes[0]


def label_mask(atlas, structure_id, share=1.0):
    data = brain(atlas).data
    mask = data == structure_id
    if share < 1.0:
        where = np.flatnonzero(mask)
        keep = where[:max(1, round(len(where) * share))]
        mask = np.zeros(data.shape, dtype=bool)
        mask.flat[keep] = True
    return mask


def tract_mask(atlas, structure_id):
    mask = np.zeros(brain(atlas).shape, dtype=bool)
    mask.flat[atlas.tracts.voxels(structure_id)] = True
    return mask


def lesion_of(atlas, mask):
    return Lesion.empty(atlas).with_mask(brain(atlas).name, mask)


def test_an_empty_lesion_is_empty_and_spares_every_lesion_route(atlas):
    lesion = Lesion.empty(atlas)
    assert lesion.is_empty and set(lesion.masks) == {v.name for v in atlas.volumes}
    result = report(atlas, lesion)
    assert result.hits == {} and result.deficits == ()
    assert result.spared == ("loop", "short")


def test_shares_count_labels_and_tracts(atlas):
    mask = label_mask(atlas, 101, 0.5) | tract_mask(atlas, 152)
    found = hits(atlas, lesion_of(atlas, mask))
    assert found[101] == pytest.approx(0.5, abs=0.05)
    assert found[152] == pytest.approx(1.0)
    assert 102 not in found


def test_a_broken_step_reads_its_lesion_line_for_the_side(atlas):
    result = report(atlas, lesion_of(atlas, label_mask(atlas, 101)))
    (deficit,) = [d for d in result.deficits if d.route == "loop"]
    assert (deficit.side, deficit.step) == ("left", 0)
    assert deficit.lesion == "Loss on the right side." and deficit.route_name == "Toy loop"
    assert deficit.structures == ((101, pytest.approx(1.0)),) and not deficit.partly
    assert result.spared == ("short",)


def test_a_station_after_the_crossing_turns_the_side(atlas):
    result = report(atlas, lesion_of(atlas, tract_mask(atlas, 152)))
    steps = {(d.route, d.side, d.step): d for d in result.deficits}
    assert steps[("loop", "left", 2)].lesion == "Loss on the left side."
    assert ("loop", "right", 2) not in steps


def test_a_small_share_is_partly_and_a_tiny_one_is_ignored(atlas):
    partly = report(atlas, lesion_of(atlas, label_mask(atlas, 101, 0.10)))
    assert [d.partly for d in partly.deficits] == [True]
    assert BROKEN <= 0.10 < PARTLY
    tiny = report(atlas, lesion_of(atlas, label_mask(atlas, 101, 0.02)))
    assert tiny.deficits == () and tiny.hits[101] > 0


def test_a_midline_station_is_listed_once(atlas):
    result = report(atlas, lesion_of(atlas, label_mask(atlas, 120)))
    assert [(d.route, d.step) for d in result.deficits] == [("loop", 5)]


def test_a_lesion_on_both_sides_lists_each_side_once(atlas):
    mask = label_mask(atlas, 101) | label_mask(atlas, 102)
    result = report(atlas, lesion_of(atlas, mask))
    assert [(d.route, d.side, d.step) for d in result.deficits] == [
        ("loop", "left", 0), ("loop", "right", 0)]


def test_a_lesion_outside_every_route_spares_them_all(atlas):
    data = brain(atlas).data
    mask = np.zeros(data.shape, dtype=bool)
    mask[0, 0, 0] = True
    result = report(atlas, lesion_of(atlas, mask))
    assert result.deficits == () and result.spared == ("loop", "short")


def test_deficits_carry_signs_and_references(atlas):
    result = report(atlas, lesion_of(atlas, label_mask(atlas, 112)))
    steps = {(d.route, d.side, d.step): d for d in result.deficits}
    assert {("loop", "left", 3), ("short", "right", 0)} <= set(steps)
    assert all(d.sign == "" for d in result.deficits)
    assert all(isinstance(d.references, tuple) for d in result.deficits)


def test_a_lesion_in_two_volumes_counts_both(toy_spine_atlas):
    atlas = Atlas.open(toy_spine_atlas)
    lesion = Lesion.empty(atlas)
    assert len(lesion.masks) == len(atlas.volumes) >= 2
    for volume in atlas.volumes:
        data = volume.data
        ids = [i for i in np.unique(data) if i and int(i) in atlas]
        lesion = lesion.with_mask(volume.name, data == ids[0])
    found = hits(atlas, lesion)
    assert len(found) >= 2


def test_a_sphere_holds_the_voxels_within_its_radius(atlas):
    volume = brain(atlas)
    centre = volume.affine @ np.array([20, 24, 18, 1.0])
    mask = sphere(volume, centre[:3], 8.0)
    assert mask.shape == volume.shape and mask[20, 24, 18]
    voxel = abs(volume.affine[0, 0])
    assert mask.sum() == pytest.approx(4 / 3 * np.pi * (8.0 / voxel) ** 3, rel=0.35)
    assert not mask[20 + 3, 24, 18]


def test_a_sphere_at_the_edge_is_clipped_to_the_grid(atlas):
    volume = brain(atlas)
    corner = volume.affine @ np.array([0, 0, 0, 1.0])
    mask = sphere(volume, corner[:3], 8.0)
    assert mask.shape == volume.shape and mask[0, 0, 0]
    assert 0 < mask.sum() < sphere(volume, (volume.affine @ np.array([20, 24, 18, 1.0]))[:3],
                                   8.0).sum()


def test_a_structure_lesion_takes_all_of_it(atlas):
    assert hits(atlas, structure_lesion(atlas, 101))[101] == pytest.approx(1.0)
    assert hits(atlas, structure_lesion(atlas, 152))[152] == pytest.approx(1.0)
    both = hits(atlas, structure_lesion(atlas, 100))
    assert both[101] == pytest.approx(1.0) and both[102] == pytest.approx(1.0)
