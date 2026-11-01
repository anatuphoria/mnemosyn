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
    assert 100 < sodium.min() and sodium.max() < 200
