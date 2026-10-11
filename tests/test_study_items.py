import pytest

from cns_study.items import (Item, group_items, item_for, items, structure_items,
                             with_reviewed_entries)
from study_atlas import entry, study_atlas


@pytest.fixture(scope="module")
def atlas(tmp_path_factory):
    return study_atlas(tmp_path_factory.mktemp("items"))


def test_structure_items_are_concepts_and_midline_structures_with_geometry(atlas):
    assert [i.id for i in structure_items(atlas)] == [100, 110, 120, 200, 210, 300, 310, 400,
                                                      410, 600, 610]


def test_a_concept_item_covers_both_sides(atlas):
    item = next(i for i in structure_items(atlas) if i.id == 100)
    assert item.geometry == {101, 102}
    assert item.answers == ("Precentral gyrus", "PreCG", "motor strip")
    assert item.level == "structures"
    assert item.path == (1, 2, 10, 100)


def test_group_items_skip_whole_atlas_small_empty_and_duplicate_groups(atlas):
    assert [i.id for i in group_items(atlas)] == [10, 20, 31, 40, 60]
    thalamus = next(i for i in group_items(atlas) if i.id == 31)
    assert thalamus.geometry == {301, 302, 311, 312}


def test_scope_limits_items_to_a_subtree(atlas):
    assert [i.id for i in items(atlas, "structures", scope=10)] == [100, 110, 120]
    assert [i.id for i in items(atlas, "groups", scope=30)] == [31]
    assert len(items(atlas, "structures")) == 11


def test_unknown_level_is_rejected(atlas):
    with pytest.raises(ValueError):
        items(atlas, "lobes")


def test_item_for_returns_the_most_specific_item():
    outer = Item(1, "groups", "Outer", "O", ("Outer",), frozenset({5, 6}), (1,))
    inner = Item(2, "groups", "Inner", "I", ("Inner",), frozenset({5}), (1, 2))
    assert item_for([outer, inner], 5) is inner
    assert item_for([outer, inner], 6) is outer
    assert item_for([outer, inner], 7) is None


def test_with_reviewed_entries_keeps_items_with_a_reviewed_description(tmp_path):
    atlas = study_atlas(tmp_path, entries={300: entry(300, "reviewed"), 310: entry(310, "draft")})
    assert [i.id for i in with_reviewed_entries(atlas, structure_items(atlas))] == [300]
