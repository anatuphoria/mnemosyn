import dataclasses

import pytest

from cns_atlas.models import Check
from cns_lab.checks import read_test, run_check, run_checks
from cns_lab.engine import Simulator
from cns_lab.experiment import Block, Experiment
from lab_helpers import toy_model

DAY = 1440.0


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    return Simulator(toy_model(tmp_path_factory.mktemp("toy")))


def check(*asserts, blocks=(), length=2 * DAY):
    return Check("probe", length, tuple(blocks), tuple(asserts))


def test_every_toy_check_passes(sim):
    outcomes = run_checks(sim)
    assert [o.key for o in outcomes] == ["rhythm", "removal", "stressed", "tested"]
    assert all(o.passed for o in outcomes), [o.detail for o in outcomes]


@pytest.mark.parametrize(("good", "bad"), [
    ({"kind": "peak_within", "value": "x", "window": [1440, 2880], "expect": [240, 600]},
     {"kind": "peak_within", "value": "x", "window": [1440, 2880], "expect": [900, 1000]}),
    ({"kind": "trough_within", "value": "x", "window": [1440, 2880], "expect": [960, 1320]},
     {"kind": "trough_within", "value": "x", "window": [1440, 2880], "expect": [240, 600]}),
    ({"kind": "within", "value": "x", "at": 1440, "low": 5, "high": 15},
     {"kind": "within", "value": "x", "at": 1440, "low": 20, "high": 30}),
    ({"kind": "back_to_normal", "value": "x", "by": 1440, "tolerance": 0.01},
     {"kind": "vs_normal", "value": "x", "at": 1440, "rises": 1.2}),
])
def test_each_kind_passes_and_fails(sim, good, bad):
    assert run_check(sim, check(good)).passed
    outcome = run_check(sim, check(bad))
    assert not outcome.passed
    assert "X" in outcome.detail and any(ch.isdigit() for ch in outcome.detail)


def test_vs_normal_and_peak_before_with_blocks(sim):
    stress = {"experiment": "stress", "start": 120.0}
    assert run_check(sim, check({"kind": "peak_before", "first": "x", "then": "y",
                                 "window": [120, 360]}, blocks=[stress])).passed
    assert not run_check(sim, check({"kind": "peak_before", "first": "y", "then": "x",
                                     "window": [120, 360]}, blocks=[stress])).passed
    removal = {"experiment": "remove_b"}
    assert run_check(sim, check({"kind": "vs_normal", "value": "x", "at": 240, "rises": 1.2},
                                blocks=[removal])).passed
    assert not run_check(sim, check({"kind": "vs_normal", "value": "x", "at": 240, "falls": 0.9},
                                    blocks=[removal])).passed


def test_a_test_reading_below_the_cutoff_is_normal(sim):
    block = Block("pill_test", 120.0)
    run = sim.run(Experiment("toy", 1, DAY, 480.0, (block,)))
    result = read_test(sim, run, block)
    assert result.test == "pill_test" and result.unit == "ng/mL" and result.cutoff == 10.8
    assert result.value == pytest.approx(run.display("x", 180.0))
    assert result.normal == (result.value < 10.8)
    assert run_check(sim, check({"kind": "test_result", "block": 0, "expect": "normal"},
                                blocks=[{"experiment": "pill_test", "start": 120.0}])).passed


def test_suppression_compares_with_the_run_without_the_test(sim):
    model = sim.model
    test = dataclasses.replace(model.tests[0], rule="suppressed by", cutoff=0.05)
    other = Simulator(dataclasses.replace(model, tests=(test,)))
    block = Block("pill_test", 120.0)
    run = other.run(Experiment("toy", 1, DAY, 480.0, (block,)))
    without = other.run(Experiment("toy", 1, DAY, 480.0))
    result = read_test(other, run, block)
    expected = 1 - run.display("x", 180.0) / without.display("x", 180.0)
    assert result.value == pytest.approx(expected) and result.unit == "fraction"
    assert result.normal == (expected >= 0.05)
