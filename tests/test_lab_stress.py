import dataclasses
from pathlib import Path

import numpy as np
import pytest

from cns_atlas.knowledge import load_references
from cns_lab.checks import run_check
from cns_lab.engine import SettleError, Simulator
from cns_lab.experiment import Block, Experiment
from cns_lab.solver import SolverError
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
OFFERED = ["hypophysectomy", "stalk_cut", "adrenalectomy", "dexamethasone", "hydrocortisone",
           "hydrocortisone_course", "addison", "cushing_disease", "adrenal_tumour",
           "short_stressor", "long_stressor"]
LEFT_OUT = ["metyrapone", "mifepristone"]


def load_stress():
    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    return next(m for m in load_models(SRC / "models", SRC / "knowledge", ids, references, routes)
                if m.key == "stress")


@pytest.fixture(scope="module")
def sim():
    return Simulator(load_stress())


def test_the_stress_model_builds():
    model = load_stress()
    assert model.route == "stress" and model.name == "Stress axis"
    assert [p.structure for p in model.parts] == [2510, 2700, None, None]


@pytest.mark.parametrize("key", [c.key for c in load_stress().checks])
def test_every_check_in_the_stress_model_passes(sim, key):
    outcome = run_check(sim, next(c for c in sim.model.checks if c.key == key))
    assert outcome.passed, outcome.detail


def test_every_spec_experiment_is_offered_or_explained():
    model = load_stress()
    assert [e.key for e in model.experiments] == OFFERED
    assert [t.key for t in model.tests] == ["low_dose_test", "high_dose_test", "acth_test"]
    scope = (SRC / "knowledge" / "en" / "lab-stress.toml").read_text(encoding="utf-8")
    assert all(name in scope for name in LEFT_OUT)


def test_cortisol_is_shown_in_ug_dl_and_nmol_l():
    cortisol = load_stress().value("cortisol")
    assert (cortisol.display_unit, cortisol.other_unit, cortisol.other_scale) == (
        "µg/dL", "nmol/L", 27.59)


def test_unmeasured_values_are_shown_relative_to_normal():
    model = load_stress()
    assert [v.key for v in model.values if v.relative] == ["crh", "acth", "corticotrophs",
                                                           "adrenal"]


def test_stress_model_survives_every_parameter_at_its_limits():
    model = load_stress()
    cases = [{p.key: p.low} for p in model.parameters] + [{p.key: p.high} for p in model.parameters]
    for values in cases:
        sim = Simulator(model)
        experiment = Experiment("stress", 1, 1440.0, 480.0, (), tuple(values.items()))
        try:
            run = sim.run(experiment)
        except (SettleError, SolverError) as exc:
            assert str(exc), values
            continue
        assert np.all(np.isfinite(run.states)), values


def test_a_test_block_reads_its_result_on_the_timeline(sim):
    block = Block("low_dose_test", 900.0)
    run = sim.run(Experiment("stress", 1, 2880.0, 480.0, (block,)))
    assert run.display("cortisol", 1440.0) < 1.8


def test_twenty_mg_of_hydrocortisone_peaks_near_the_measured_level(sim):
    run = sim.run(Experiment("stress", 1, 1440.0, 480.0,
                             (Block("hydrocortisone", 60.0, None, (("dose", 20.0),)),)))
    normal = sim.normal(1440.0, 480.0)
    grid = np.arange(60.0, 400.0)
    extra = [run.display("cortisol", t) - normal.display("cortisol", t) for t in grid]
    assert 30 <= max(extra) <= 40


def test_the_model_does_not_change_the_paper_values():
    model = load_stress()
    paper = {"w1": 0.17, "w2": 0.035, "w3": 0.0091, "K_GR": 4, "n": 3}
    assert {k: model.parameter(k).value for k in paper} == paper
    assert model.parameter("wC").value * 1440 == pytest.approx(0.099, rel=1e-3)
    assert model.parameter("wA").value * 1440 == pytest.approx(0.049, rel=1e-3)
    assert dataclasses.replace(model) == model


def test_a_finished_course_is_still_explained_through_the_shrunken_adrenal(sim):
    from cns_lab.why import chain

    experiment = Experiment("stress", 1, 8 * 7 * 1440.0, 480.0,
                            (Block("hydrocortisone_course", 0.0, 28 * 1440.0, (("dose", 40.0),)),))
    run = sim.run(experiment)
    steps = chain(sim, run, 30 * 1440.0)
    sources = [s.source for s in steps]
    assert sources[0] == "hydrocortisone_course"
    assert "make_cortisol" in sources or "grow_adrenal" in sources


def test_values_inside_their_ranges_give_a_run_or_a_clean_error():
    import random

    model = load_stress()
    cases = [((("n", 3.73), ("K_GR", 1.0), ("K_MR", 0.25)),
              (Block("hypophysectomy", 60.0), Block("high_dose_test", 900.0)))]
    rng = random.Random(7)
    experiments = [e.key for e in model.experiments] + [t.key for t in model.tests]
    for _ in range(10):
        values = tuple((p.key, rng.uniform(p.low, p.high))
                       for p in rng.sample(list(model.parameters), 3))
        chosen = rng.sample(experiments, 2)
        cases.append((values, tuple(Block(k, 60.0 + 300 * n) for n, k in enumerate(chosen))))
    for values, blocks in cases:
        sim = Simulator(model)
        try:
            run = sim.run(Experiment("stress", 1, 1440.0, 480.0, blocks, values))
        except (SettleError, SolverError):
            continue
        assert np.all(np.isfinite(run.states)), (values, blocks)


def test_a_cut_stalk_shows_as_a_cut_link(sim):
    model = sim.model
    arrows = [f.key for f in (*model.effects, *model.terms) if f.arrow == ("pvn", "pituitary")]
    assert arrows == ["portal_crh"]
    run = sim.run(Experiment("stress", 1, 1440.0, 480.0, (Block("stalk_cut", 60.0),)))
    assert run.factor("portal_crh", 600.0) == 0.0
    assert run.factor("make_crh", 600.0) > 0
