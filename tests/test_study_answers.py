import pytest

from cns_study.answers import AnswerIndex, distance, normalize
from cns_study.items import group_items, structure_items
from study_atlas import study_atlas


@pytest.fixture(scope="module")
def pool(tmp_path_factory):
    atlas = study_atlas(tmp_path_factory.mktemp("answers"))
    return {item.id: item for item in structure_items(atlas) + group_items(atlas)}


@pytest.fixture(scope="module")
def index(pool):
    return AnswerIndex(list(pool.values()))


def test_normalize_folds_case_accents_punctuation_side_words_and_a_leading_the():
    assert normalize("  The LEFT Précentral-gyrus, ") == "precentral gyrus"


def test_distance_counts_a_transposition_as_one_and_caps_at_the_limit():
    assert distance("gyrus", "gyrsu", 2) == 1
    assert distance("abc", "abc", 0) == 0
    assert distance("kitten", "sitting", 1) == 2
    assert distance("", "ab", 2) == 2


def test_name_acronym_and_synonym_are_accepted(index, pool):
    for typed in ("Precentral gyrus", "precg", "Motor strip", "the left precentral gyrus"):
        verdict = index.check(typed, pool[100])
        assert verdict.correct and verdict.exact, typed


def test_word_order_is_free(index, pool):
    verdict = index.check("opercular part of inferior frontal gyrus", pool[120])
    assert verdict.correct and verdict.exact


def test_typo_allowance_grows_with_length(index, pool):
    verdict = index.check("precentrl gyris", pool[100])
    assert verdict.correct and not verdict.exact and verdict.matched == "Precentral gyrus"
    assert not index.check("precntrl gyris", pool[100]).correct
    assert index.check("thalamos", pool[31]).correct
    assert not index.check("thalmos", pool[31]).correct
    assert not index.check("lcc", pool[400]).correct


def test_a_typo_closer_to_another_item_is_rejected(index, pool):
    assert not index.check("vermis lobul vii", pool[610]).correct
    verdict = index.check("vermis lobule viiii", pool[610])
    assert verdict.correct and not verdict.exact


def test_another_items_name_is_wrong(index, pool):
    assert not index.check("Medial geniculate nucleus", pool[300]).correct
    assert not index.check("MGN", pool[300]).correct
    assert not index.check("vervii", pool[610]).correct


def test_a_blank_answer_is_wrong(index, pool):
    assert not index.check("   ", pool[100]).correct
    assert not index.check("the", pool[100]).correct
