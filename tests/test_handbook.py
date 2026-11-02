import json
import re
from pathlib import Path

import pytest

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
from tools.handbook.shots import SHOTS, take

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "atlas_src"
HANDBOOK = ROOT / "site" / "handbook"
PAGES = sorted(HANDBOOK.rglob("*.md"))
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
    pages = {p.stem for p in (HANDBOOK / "experiments").glob("*.md")} - {"index"}
    assert len(slugs) == 8 and pages == slugs
    for entry in lab:
        text = (HANDBOOK / "experiments" / f"{entry.slug}.md").read_text()
        assert f"files/{entry.slug}/{entry.file}" in text, (entry.slug, entry.file)
    for slug in slugs:
        text = (HANDBOOK / "experiments" / f"{slug}.md").read_text()
        assert "This page is being written" not in text, slug


@pytest.fixture
def local_toy_atlas(tmp_path):
    from atlas_package import tetra, tiny_structures, write_package

    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["local_only"] = ["toylocal"]
    (root / "metadata.json").write_text(json.dumps(metadata))
    return root


def test_shots_refuse_a_local_atlas(tmp_path, local_toy_atlas):
    with pytest.raises(ValueError, match="shareable atlas"):
        take(local_toy_atlas, tmp_path)


def test_every_page_reference_exists(tmp_path):
    from tools.build_site import build_site

    out = tmp_path / "site"
    build_site(ROOT, out)
    for page in sorted((out / "handbook").rglob("*.md")):
        for target in re.findall(r"\]\(([^)#\s]+)", page.read_text()):
            if "://" not in target:
                assert (page.parent / target).resolve().exists(), (page, target)


def test_every_shot_is_used_and_every_used_shot_is_defined():
    used = {m for p in PAGES for m in re.findall(r"shots/([\w-]+)\.png", p.read_text())}
    assert used == set(SHOTS)
    for name in used:
        assert (HANDBOOK / "shots" / f"{name}.png").exists(), name


def test_handbook_pages_follow_the_writing_rules():
    for page in PAGES:
        for number, line in enumerate(page.read_text().splitlines(), 1):
            assert "\u2014" not in line and "\u2013" not in line, (page, number)
            assert " - " not in line and not line.lstrip().startswith("- "), (page, number)


def test_no_handbook_page_is_a_placeholder():
    for page in PAGES:
        assert "This page is being written" not in page.read_text(), page


def test_the_old_guide_points_into_the_handbook(tmp_path):
    from tools.build_site import build_site

    build_site(ROOT, tmp_path / "out")
    guide = (tmp_path / "out/guide.md").read_text()
    assert "handbook/index.md" in guide and "handbook/lab.md" in guide
    for target in re.findall(r"\]\(([^)#\s]+)", guide):
        assert (tmp_path / "out" / target).exists(), target


def test_every_handbook_page_is_in_the_navigation():
    nav = (ROOT / "mkdocs.yml").read_text()
    assert "Handbook:" in nav and "Using the app: guide.md" not in nav
    for page in PAGES:
        assert str(page.relative_to(ROOT / "site")) in nav, page


@pytest.fixture
def real_window():
    import tempfile

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from cns_atlas import Atlas
    from cns_desktop.app import default_atlas
    from cns_desktop.main_window import MainWindow

    path = default_atlas()
    if not (path / "metadata.json").exists():
        pytest.skip("no built atlas")
    QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as scratch:
        settings = QSettings(f"{scratch}/s.ini", QSettings.Format.IniFormat)
        window = MainWindow(Atlas.open(path), progress_path=Path(scratch) / "p.sqlite",
                            settings=settings)
        yield window
        window.close()


def test_every_app_shortcut_is_in_the_handbook(real_window):
    from PySide6.QtGui import QAction

    text = "\n".join(p.read_text() for p in PAGES)
    for action in real_window.findChildren(QAction):
        key = action.shortcut().toString()
        if key:
            assert f"`{key}`" in text, (action.text(), key)
