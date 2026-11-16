import tomllib
from pathlib import Path

import numpy as np
import pytest

from cns_atlas.knowledge import load_references
from cns_lab.checks import run_check
from cns_lab.engine import Simulator
from cns_lab.experiment import Block, Experiment
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
LANES = ["map", "hr", "symp", "vagal", "tpr"]
SWITCHES = {"afferent", "reflex", "pooling", "beta", "muscarinic", "alpha", "dilate", "constrict",
            "sinus_press", "command"}
CHECKS = {"rest", "standing", "bleeding", "tightening", "relaxing", "beta_blocked",
          "vagus_blocked", "alpha_blocked", "nerves_cut", "failure_standing", "sinus_pressed",
          "alarm"}


def load_all():
    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    return load_models(SRC / "models", SRC / "knowledge", ids, references, routes)


@pytest.fixture(scope="module")
def model():
    return next(m for m in load_all() if m.key == "pressure")


@pytest.fixture(scope="module")
def sim(model):
    return Simulator(model)


def run(sim, *blocks, length=10.0):
    model = sim.model
    return sim.run(Experiment(model.key, model.version, length, model.start_clock, tuple(blocks)))


def test_the_slow_systems_stay_first_and_the_reflex_runs_in_minutes(model):
    assert [m.key for m in load_all()] == ["stress", "water", "pressure"]
    assert model.name == "Blood pressure reflex" and model.route is None
    assert model.scale == "minutes" and model.period == 10.0
    lanes = sorted((v for v in model.values if v.lane is not None), key=lambda v: v.lane)
    assert [v.key for v in lanes] == LANES
    structures = {p.key: p.structure for p in model.parts}
    assert structures["nts"] == 2830 and structures["vasomotor"] == 2840
    assert structures["vagus"] == 3450 and structures["heart"] is None


def test_every_number_has_a_source(model):
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-pressure.toml").read_text())
    for value in model.values:
        assert value.refs, value.key
    for parameter in model.parameters:
        if parameter.key not in SWITCHES:
            meaning = texts[f"parameter.{parameter.key}.meaning"]
            assert parameter.refs or "ssumption of this project" in meaning, parameter.key
    assert {p.key for p in model.parameters if not p.panel} <= SWITCHES


def test_rest_is_steady_and_in_the_normal_ranges(sim):
    normal = sim.normal(10.0, sim.model.start_clock)
    for key, (low, high) in {"map": (90, 96), "hr": (68, 72), "symp": (0.99, 1.01),
                             "vagal": (0.99, 1.01), "blood": (4.99, 5.01)}.items():
        levels = np.asarray(normal.value(key))
        assert low <= levels.min() and levels.max() <= high, key


def test_every_published_outcome_holds(sim):
    assert {c.key for c in sim.model.checks} == CHECKS
    for check in sim.model.checks:
        outcome = run_check(sim, check)
        assert outcome.passed, (check.key, outcome)


def test_standing_dips_the_pressure_before_the_reflex_restores_it(sim):
    standing = run(sim, Block("stand", 2.0))
    dip = min(standing.at("map", 2.0 + s / 60) for s in range(40))
    settled = standing.at("map", 6.0)
    assert dip < 85 < settled < 93
    assert standing.at("hr", 6.0) > 75


def test_a_bigger_blood_loss_costs_more_pressure_and_a_faster_heart(sim):
    small = run(sim, Block("blood_loss", 2.0, None, (("volume", 0.5),)))
    large = run(sim, Block("blood_loss", 2.0, None, (("volume", 1.5),)))
    assert large.at("map", 6.0) < small.at("map", 6.0) < 93
    assert large.at("hr", 6.0) > small.at("hr", 6.0) > 70
    refilled = run(sim, Block("blood_loss", 2.0, None, (("volume", 1.0),)), length=180.0)
    assert 4.0 < refilled.at("blood", 10.0) < refilled.at("blood", 170.0) < 5.0


def test_blocking_both_sets_of_nerves_leaves_the_pacemakers_own_rate(sim):
    both = run(sim, Block("beta_blocker", 1.0), Block("atropine", 1.0))
    intrinsic = sim.model.parameter("hr_intrinsic").value
    assert abs(both.at("hr", 8.0) - intrinsic) < 12


def test_a_short_press_on_the_carotid_sinus_keeps_its_length_and_passes(sim, model):
    assert model.experiment("carotid_massage").length == 0.25
    pressed = run(sim, Block("carotid_massage", 2.0, 0.25))
    assert pressed.at("hr", 2.25) < 60
    assert abs(pressed.at("hr", 5.0) - 70) < 1 and abs(pressed.at("map", 5.0) - 93) < 1


@pytest.mark.parametrize("key", ["set_point", "steepness", "k_symp", "k_vagal", "hr_intrinsic",
                                 "starling", "tpr_gain", "symp_range", "afterload"])
def test_each_panel_setting_settles_at_both_ends(model, key):
    parameter = model.parameter(key)
    for level in (parameter.low, parameter.high):
        sim = Simulator(model)
        made = sim.run(Experiment(model.key, model.version, 10.0, model.start_clock, (),
                                  ((key, level),)))
        for value in ("map", "hr"):
            levels = np.asarray(made.value(value))
            assert np.all(np.isfinite(levels)) and levels.min() > 0, (key, level, value)


def test_the_texts_say_what_the_model_leaves_out(model):
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-pressure.toml").read_text())
    scope = texts["scope"]
    for word in ("kidneys", "renin", "resetting", "first seconds to minutes"):
        assert word in scope, word
    assert "does not follow" in texts["experiment.denervation.description"]


def test_a_short_run_and_a_short_change_survive_saving_and_opening(model, tmp_path):
    from cns_lab.files import loads, read, write

    made = Experiment(model.key, model.version, 10.0, model.start_clock,
                      (Block("carotid_massage", 2.5, 0.25), Block("stand", 9.9)))
    path = tmp_path / "short.mnemolab"
    write(path, made)
    opened, report = read(path, {model.key: model})
    assert report == () and opened == made
    assert loads(path.read_text(), {model.key: model})[0] == made
    tiny = Experiment(model.key, model.version, 0.2, model.start_clock)
    write(path, tiny)
    opened, report = read(path, {model.key: model})
    assert opened.length == 1.0 and "it is now 1 min" in report[0]
