from pathlib import Path

from cns_atlas.knowledge import load_references
from cns_lab.checks import check_experiment, run_check
from cns_lab.files import read
from cns_lab.engine import Simulator
from cns_lab.experiment import Block, Experiment
from cns_lab.times import DAY
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways
from tools.handbook.experiments import FILES, experiment, load, write_files

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


def test_every_handbook_lab_claim_holds():
    lab, _atlas = load()
    assert lab
    for entry in lab:
        sim = Simulator(load_model(entry.system))
        outcome = check_experiment(sim, experiment(entry, sim.model), entry.asserts, entry.file)
        assert outcome.passed, (entry.slug, entry.file, outcome.detail)


def test_every_handbook_file_opens_cleanly():
    lab, _atlas = load()
    models = {key: load_model(key) for key in ("stress", "water")}
    for entry in lab:
        path = FILES / entry.slug / entry.file
        opened, warnings = read(path, models)
        assert warnings == () and opened == experiment(entry, models[entry.system]), path


def test_the_committed_files_match_the_definitions(tmp_path):
    models = {key: load_model(key) for key in ("stress", "water")}
    written = write_files(models, tmp_path)
    assert written
    for path in written:
        committed = FILES / path.relative_to(tmp_path)
        assert committed.read_text() == path.read_text(), committed
    assert len(list(FILES.rglob("*.mnemolab"))) == len(written)


def test_every_lab_experiment_has_a_page_and_every_page_its_files():
    lab, atlas = load()
    slugs = {e.slug for e in lab} | {c.slug for c in atlas}
    assert len(slugs) == 8
