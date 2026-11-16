import tomllib
from pathlib import Path

import numpy as np
import pytest

from cns_atlas.knowledge import load_references
from cns_lab.checks import run_check
from cns_lab.engine import Simulator
from cns_lab.experiment import PRESENT, Block, Experiment
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
DAY = 1440.0
LANES = ["map", "ecf", "excretion", "renin", "ang", "aldo"]
SWITCHES = {"salt", "stenosis", "ace", "at1", "mr", "aldo_auto", "diuretic", "resist", "kidney"}
CHECKS = {"rest", "salt_loaded", "salt_restricted", "tightened", "narrowed_artery",
          "excess_aldosterone", "ace_blocked", "receptor_blocked", "diuretic_given",
          "aldosterone_blocked", "kidney_and_salt", "fluid_lost", "saline_given"}


@pytest.fixture(scope="module")
def model():
    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    models = load_models(SRC / "models", SRC / "knowledge", ids, references, routes)
    return next(m for m in models if m.key == "volume")


@pytest.fixture(scope="module")
def sim(model):
    return Simulator(model)


def run(sim, *blocks, days=8.0, values=()):
    model = sim.model
    return sim.run(Experiment(model.key, model.version, days * DAY, model.start_clock,
                              tuple(blocks), tuple(values)))


def test_the_system_runs_in_hours_and_shows_six_lanes(model):
    assert model.name == "Blood pressure over days" and model.scale == "hours"
    lanes = sorted((v for v in model.values if v.lane is not None), key=lambda v: v.lane)
    assert [v.key for v in lanes] == LANES
    assert all(part.structure is None for part in model.parts)


def test_every_number_has_a_source(model):
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-volume.toml").read_text())
    for value in model.values:
        assert value.refs, value.key
    for parameter in model.parameters:
        if parameter.key not in SWITCHES:
            meaning = texts[f"parameter.{parameter.key}.meaning"]
            assert parameter.refs or "ssumption of this project" in meaning, parameter.key
    assert {p.key for p in model.parameters if not p.panel} <= SWITCHES


def test_a_usual_diet_is_steady(sim):
    normal = sim.normal(3 * DAY, sim.model.start_clock)
    for key, (low, high) in {"map": (92.5, 93.5), "ecf": (13.95, 14.05), "renin": (0.98, 1.02),
                             "ang": (0.98, 1.02), "aldo": (0.98, 1.02)}.items():
        levels = np.asarray(normal.value(key))
        assert low <= levels.min() and levels.max() <= high, key
    assert abs(normal.display("excretion", 2 * DAY) - 150) < 2


def test_every_published_outcome_holds(sim):
    assert {c.key for c in sim.model.checks} == CHECKS
    for check in sim.model.checks:
        outcome = run_check(sim, check)
        assert outcome.passed, (check.key, outcome)


def test_in_balance_the_kidney_excretes_what_is_eaten(sim):
    for experiment, intake, slack in (("high_salt", 450, 0.05), ("low_salt", 19.5, 0.2)):
        made = run(sim, Block(experiment, 240.0))
        assert abs(made.display("excretion", 7 * DAY) - intake) < slack * intake, experiment


def test_tight_vessels_alone_do_not_keep_the_pressure_high(sim):
    made = run(sim, Block("vasoconstrictor", 240.0))
    assert made.at("map", 360.0) > 100
    assert abs(made.at("map", 7 * DAY) - 93) < 1
    assert made.at("ecf", 7 * DAY) < 13.2


def test_a_narrowed_renal_artery_raises_pressure_until_the_kidney_is_perfused_again(sim):
    made = run(sim, Block("stenosis", 240.0))
    assert made.at("renin", 480.0) > 5
    late = made.at("map", 7 * DAY)
    assert 115 < late < 121 and abs(made.at("renin", 7 * DAY) - 1) < 0.1
    treated = run(sim, Block("stenosis", 240.0), Block("ace_inhibitor", 240.0))
    assert treated.at("map", 7 * DAY) < late - 5


def test_the_two_angiotensin_drugs_differ_only_in_angiotensin(sim):
    ace = run(sim, Block("ace_inhibitor", 240.0))
    arb = run(sim, Block("arb", 240.0))
    at = 7 * DAY
    assert abs(ace.at("map", at) - arb.at("map", at)) < 0.5
    assert ace.at("ang", at) < 0.6 and arb.at("ang", at) > 2


def test_salt_raises_pressure_more_when_the_hormones_cannot_fall(sim):
    at = 7 * DAY
    healthy = run(sim, Block("high_salt", 240.0)).at("map", at) - 93
    fixed = (run(sim, Block("aldosteronism", 240.0), Block("high_salt", 240.0)).at("map", at)
             - run(sim, Block("aldosteronism", 240.0)).at("map", at))
    small = (run(sim, Block("kidney_loss", 0.0, None, (), PRESENT),
                 Block("high_salt", 240.0)).at("map", at)
             - run(sim, Block("kidney_loss", 0.0, None, (), PRESENT)).at("map", at))
    assert 0 < healthy < 9 and fixed > 2 * healthy and small > healthy


def test_a_bigger_fluid_loss_takes_longer_to_replace(sim):
    small = run(sim, Block("fluid_loss", 240.0, None, (("volume", 0.5),)))
    large = run(sim, Block("fluid_loss", 240.0, None, (("volume", 3.0),)))
    assert large.at("ecf", DAY) < small.at("ecf", DAY) < 14
    assert large.at("renin", 600.0) > small.at("renin", 600.0) > 1.2


@pytest.mark.parametrize("key", ["set_point", "nat", "vol_gain", "ang_press", "ang_ret", "aldo_ret",
                                 "renin_pressure", "renin_salt", "short", "k_renin", "k_aldo"])
def test_each_panel_setting_settles_at_both_ends(model, key):
    parameter = model.parameter(key)
    for level in (parameter.low, parameter.high):
        made = run(Simulator(model), days=3.0, values=((key, level),))
        for value in ("map", "ecf", "renin"):
            levels = np.asarray(made.value(value))
            assert np.all(np.isfinite(levels)) and levels.min() > 0, (key, level, value)
            assert abs(levels[-1] - levels[len(levels) // 2]) < 0.05 * levels[-1], (key, level)


def test_the_texts_say_what_the_model_leaves_out(model):
    scope = tomllib.loads((SRC / "knowledge" / "en" / "lab-volume.toml").read_text())["scope"]
    for word in ("Potassium", "natriuretic peptides", "fast nerve reflex", "assumptions"):
        assert word in scope, word
