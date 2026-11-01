import tomllib
from pathlib import Path

import numpy as np
import pytest

from cns_atlas.knowledge import load_references
from cns_lab.checks import run_check
from cns_lab.engine import Simulator
from cns_lab.experiment import Experiment
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
DAY = 1440.0
LANES = ["sodium", "avp", "uosm", "thirst"]


def load_water():
    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    return next(m for m in load_models(SRC / "models", SRC / "knowledge", ids, references, routes)
                if m.key == "water")


@pytest.fixture(scope="module")
def sim():
    return Simulator(load_water())


def test_the_water_model_builds_with_its_route_and_parts():
    model = load_water()
    assert model.route == "thirst" and model.name == "Water balance"
    lanes = sorted((v for v in model.values if v.lane is not None), key=lambda v: v.lane)
    assert [v.key for v in lanes] == LANES
    structures = {p.key: p.structure for p in model.parts}
    assert structures["son"] == 2580 and structures["pvn"] == 2510
    assert structures["pituitary"] == 2700
    assert structures["osmoreceptors"] is None and structures["kidney"] is None


def test_every_number_has_a_source():
    model = load_water()
    for value in model.values:
        if value.lane is not None:
            assert value.refs, value.key
    switches = {"drinking", "avp_scale", "kidney", "avp_auto", "salt_in", "iv_water",
                "habit_scale"}
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-water.toml").read_text())
    for parameter in model.parameters:
        if parameter.key not in switches:
            meaning = texts[f"parameter.{parameter.key}.meaning"]
            assert parameter.refs or "assumption of this project" in meaning, parameter.key


def test_the_normal_day_checks_pass(sim):
    for check in sim.model.checks:
        if check.key.startswith("normal"):
            outcome = run_check(sim, check)
            assert outcome.passed, (check.key, outcome.messages)


def test_a_normal_day_sits_in_its_published_ranges(sim):
    run = sim.normal(2 * DAY, sim.model.start_clock)
    sodium = np.array([run.display("sodium", t) for t in np.linspace(DAY, 2 * DAY, 49)])
    assert 135 <= sodium.min() and sodium.max() <= 145
    assert 300 <= run.display("uosm", 1.5 * DAY) <= 900
    assert 0.5 <= run.display("avp", 1.5 * DAY) <= 5


@pytest.mark.parametrize("values", [(("drinking", 0.0),), (("habit_scale", 8.0),),
                                    (("avp_scale", 0.0),), (("avp_auto", 20.0),)])
def test_extremes_from_a_normal_day_stay_finite(sim, values):
    start = sim.settle((), ())
    experiment = Experiment("water", 1, 3 * DAY, sim.model.start_clock, (), values)
    times, states = [], []
    sim._march(experiment, 0.0, 3 * DAY, list(start), 1.0, False, times, states)
    states = np.asarray(states)
    assert np.all(np.isfinite(states))
    sodium = states[:, sim.keys.index("sodium")] * sim.values["sodium"].display_scale
    assert 80 < sodium.min() and sodium.max() < 200


OFFERED = ["water_load", "stop_drinking", "hypertonic_saline", "desmopressin", "central_di",
           "nephrogenic_di", "siadh", "primary_polydipsia"]
CHECKS = {"normal_day", "water_load", "deprivation_normal", "central_di_tests",
          "nephrogenic_di_tests", "polydipsia_tests", "siadh_sodium", "saline_vasopressin"}


def test_the_water_experiments_and_tests_are_offered():
    model = load_water()
    assert [e.key for e in model.experiments] == OFFERED
    assert [t.key for t in model.tests] == ["water_deprivation_test", "desmopressin_test"]
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-water.toml").read_text())
    for test in model.tests:
        for suffix in ("", ".description", ".normal", ".abnormal"):
            assert texts[f"test.{test.key}{suffix}"]


def test_every_published_outcome_holds(sim):
    assert {c.key for c in sim.model.checks} == CHECKS
    for check in sim.model.checks:
        outcome = run_check(sim, check)
        assert outcome.passed, (check.key, outcome)


def why_at(sim, blocks, t, length=DAY):
    from cns_lab.experiment import Block
    from cns_lab.why import chain

    run = sim.run(Experiment("water", 1, length, 480.0, tuple(Block(*b) for b in blocks)))
    return [step.source for step in chain(sim, run, t)]


def test_why_follows_the_deprivation_test(sim):
    assert "drink" in why_at(sim, [("water_deprivation_test", 60.0)], 60.0 + 360.0)


def test_why_explains_a_water_load_by_dilution(sim):
    sources = why_at(sim, [("water_load", 120.0, None, (("volume", 1.0),))], 150.0)
    assert "dilute" in sources and "concentrate" not in sources


def test_small_sodium_changes_are_not_called_unchanged(sim):
    from cns_lab.why import phrase

    assert sim.model.why_unchanged < 0.01
    assert phrase(sim.values["sodium"], 1.006, band=sim.model.why_unchanged) == "rises by 1%"


def test_thirst_and_drinking_numbers_are_named_parameters():
    model = load_water()
    parameters = {p.key: p for p in model.parameters}
    assert parameters["thirst_threshold"].value == 281 and parameters["thirst_slope"].value == 0.3
    assert parameters["thirst_threshold"].refs and parameters["thirst_slope"].refs
    effects = {e.key: e.expr for e in model.effects}
    assert "281" not in effects["thirst_drive"] and "0.3" not in effects["thirst_drive"]
    assert "drink_max" in parameters and "min(" in effects["drink"]


def test_the_diet_solute_and_deprivation_cutoff_follow_their_sources():
    model = load_water()
    solute = next(p for p in model.parameters if p.key == "solute")
    assert abs(solute.value * 1440 - 600) < 15
    deprivation = next(t for t in model.tests if t.key == "water_deprivation_test")
    assert deprivation.cutoff == 800


def test_the_texts_say_what_the_model_leaves_out_and_when_a_test_stops():
    texts = tomllib.loads((SRC / "knowledge" / "en" / "lab-water.toml").read_text())
    assert "escape" in texts["scope"] and "escape" in texts["experiment.siadh.description"]
    assert "stopped early" in texts["test.water_deprivation_test.description"]
    assert "Baylis" not in texts["experiment.hypertonic_saline.description"]
    assert "choice of this project" in texts["experiment.hypertonic_saline.description"]
