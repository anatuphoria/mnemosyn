import pytest

from cns_lab.engine import Simulator
from cns_lab.experiment import Block, Experiment
from cns_lab.why import chain, normal_note, phrase
from lab_helpers import toy_model

DAY = 1440.0


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    return Simulator(toy_model(tmp_path_factory.mktemp("toy")))


def run_of(sim, *blocks, length=DAY):
    return sim.run(Experiment("toy", 1, length, 480.0, tuple(blocks)))


def test_removing_b_explains_x_through_the_feedback(sim):
    run = run_of(sim, Block("remove_b", 0.0, None, (), "present"))
    steps = chain(sim, run, 240.0)
    assert [s.source for s in steps] == ["remove_b", "make_y", "fb", "make_x"]
    assert steps[0].text_key == "experiment.remove_b" and steps[0].since is None
    assert steps[1].value == "y" and steps[1].ratio == pytest.approx(0.0, abs=1e-6)
    assert steps[2].text_key == "effect.fb" and steps[2].ratio > 1.5
    assert steps[3].value == "x" and steps[3].ratio > 1.2


def test_no_changes_give_no_chain(sim):
    assert chain(sim, run_of(sim), 240.0) == ()


def test_small_changes_are_left_out(sim):
    run = run_of(sim, Block("pill", 120.0, None, (("dose", 0.01),)))
    assert [s.source for s in chain(sim, run, 200.0)] == ["pill"]


def test_the_chain_is_the_same_every_time(sim):
    run = run_of(sim, Block("stress", 120.0, 60.0, (("strength", 2.0),)),
                 Block("pill", 130.0, None, (("dose", 1.0),)))
    assert chain(sim, run, 150.0) == chain(sim, run, 150.0)


def test_blocks_are_ordered_by_their_start(sim):
    run = run_of(sim, Block("pill", 130.0, None, (("dose", 2.0),)),
                 Block("stress", 120.0, 60.0, (("strength", 2.0),)))
    steps = chain(sim, run, 150.0)
    blocks = [s.source for s in steps if s.kind == "change"]
    assert blocks == ["stress", "pill"]
    assert steps[0].since == 120.0


def test_blocks_not_started_yet_are_left_out(sim):
    run = run_of(sim, Block("stress", 600.0, 60.0, (("strength", 2.0),)))
    assert chain(sim, run, 300.0) == ()


def test_the_limit_caps_the_chain(sim):
    run = run_of(sim, Block("remove_b", 0.0, None, (), "present"))
    assert len(chain(sim, run, 240.0, limit=2)) == 2


@pytest.mark.parametrize(("ratio", "text"), [
    (0.1, "falls to 10% of normal"), (2.44, "rises to 2.4 times normal"),
    (1.2, "rises by 20%"), (1.01, "is unchanged"), (0.99, "is unchanged"),
    (0.0, "falls to 0% of normal"), (float("inf"), "rises from nothing"),
])
def test_phrases(sim, ratio, text):
    assert phrase(sim.values["x"], ratio) == text


def test_normal_notes_wrap_midnight(sim):
    assert normal_note(sim.model, 300.0) == "morning"
    assert normal_note(sim.model, 23 * 60.0) == "night" and normal_note(sim.model, 60.0) == "night"
    assert normal_note(sim.model, 12 * 60.0) is None
