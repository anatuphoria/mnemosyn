import random

import pytest

from cns_study.choices import choices
from cns_study.items import Item, structure_items
from study_atlas import study_atlas


@pytest.fixture(scope="module")
def pool(tmp_path_factory):
    return structure_items(study_atlas(tmp_path_factory.mktemp("choices")))


def make(sid, level, name, acronym, path):
    return Item(sid, level, name, acronym, (name, acronym), frozenset({sid}), path)


def test_four_options_with_the_item_and_its_siblings_first(pool):
    item = next(i for i in pool if i.id == 100)
    picked = choices(item, pool, random.Random(1))
    ids = [option.id for option in picked]
    assert len(ids) == 4 and len(set(ids)) == 4
    assert {100, 110, 120} <= set(ids)


def test_the_same_seed_gives_the_same_options(pool):
    item = next(i for i in pool if i.id == 300)
    first = [o.id for o in choices(item, pool, random.Random(7))]
    second = [o.id for o in choices(item, pool, random.Random(7))]
    assert first == second


def test_distractors_never_share_an_answer_or_cross_levels():
    target = make(1, "structures", "Alpha", "X", (9, 1))
    twin = make(2, "structures", "Beta", "X", (9, 2))
    other = make(3, "structures", "Gamma", "Y", (9, 3))
    group = make(4, "groups", "Delta", "Z", (9, 4))
    picked = choices(target, [target, twin, other, group], random.Random(1))
    assert {o.id for o in picked} == {1, 3}
