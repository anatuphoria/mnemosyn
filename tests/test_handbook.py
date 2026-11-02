from pathlib import Path

from cns_atlas.knowledge import load_references
from cns_lab.checks import check_experiment, run_check
from cns_lab.engine import Simulator
from cns_lab.experiment import Block, Experiment
from cns_lab.times import DAY
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "atlas_src"
_MODELS: dict = {}


def load_model(key: str):
    if not _MODELS:
        ids = {r.id for r in load_structures(SRC / "structures.toml")}
        references = load_references(SRC / "knowledge" / "references.toml")
        routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
        for model in load_models(SRC / "models", SRC / "knowledge", ids, references, routes):
            _MODELS[model.key] = model
    return _MODELS[key]


def test_check_experiment_passes_and_fails_like_a_model_check():
    sim = Simulator(load_model("water"))
    blocks = (Block("central_di", 0.0, mode="present"), Block("desmopressin_test", 0.0))
    experiment = Experiment("water", sim.model.version, DAY, sim.model.start_clock, blocks)
    good = check_experiment(sim, experiment, ({"kind": "test_result", "block": 1,
                                                 "expect": "abnormal"},))
    bad = check_experiment(sim, experiment, ({"kind": "test_result", "block": 1,
                                                "expect": "normal"},))
    assert good.passed and not bad.passed and "desmopressin_test" in bad.detail


def test_model_checks_still_pass_through_check_experiment():
    for key in ("water", "stress"):
        sim = Simulator(load_model(key))
        assert all(run_check(sim, c).passed for c in sim.model.checks)
