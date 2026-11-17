import tempfile
from pathlib import Path

import pytest

from cns_lab.relations import drivers, names_in, selection_name
from lab_helpers import load_toy


@pytest.fixture(scope="module")
def model():
    return load_toy(Path(tempfile.mkdtemp()))[0]


def test_names_are_read_from_a_formula():
    assert names_in("w * fb * (1 + stress)") == {"w", "fb", "stress"}
    assert names_in("hill(y, k, 2)") == {"hill", "y", "k"}


def test_a_value_is_shaped_by_the_settings_in_its_own_terms_and_their_effects(model):
    assert drivers(model, ("value", "x")) == ("k", "w", "a", "stress")
    assert drivers(model, ("value", "y")) == ("w",)
    assert drivers(model, ("value", "m")) == ()


def test_a_link_is_shaped_by_its_own_formula(model):
    assert drivers(model, ("link", "fb")) == ("k",)
    assert selection_name(model, ("link", "fb")) == "the link from Beta to Alpha"


def test_a_part_gathers_its_values_and_the_arrows_into_it(model):
    assert drivers(model, ("part", "body")) == ("w",)
    assert set(drivers(model, ("part", "b"))) == {"k", "w", "a", "stress"}
    assert selection_name(model, ("part", "body")) == "Body gland"
    assert selection_name(model, ("value", "x")) == "X"


def test_other_selections_shape_nothing(model):
    for selection in (None, ("block", 0), ("value", "nope"), ("part", "nope"), ("link", "nope")):
        assert drivers(model, selection) == ()
    assert selection_name(model, ("block", 0)) == ""


def test_settings_kept_off_the_panel_are_not_offered(model):
    from dataclasses import replace

    hidden = replace(model, parameters=tuple(replace(p, panel=p.key != "stress")
                                             for p in model.parameters))
    assert drivers(hidden, ("value", "x")) == ("k", "w", "a")
