import math
import tomllib
from pathlib import Path

import pytest

from cns_atlas.knowledge import load_references
from cns_atlas.models import CONTROLS
from cns_desktop.lab.scales import curve_points
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.models import load_models
from tools.build_atlas.pathways import load_pathways

SRC = Path(__file__).resolve().parent.parent / "atlas_src"


@pytest.fixture(scope="module")
def shipped():
    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    return {m.key: m for m in load_models(SRC / "models", SRC / "knowledge", ids, references, routes)}


@pytest.mark.parametrize("key", ["stress", "water"])
def test_every_panel_setting_has_a_group_and_a_fitting_control(shipped, key):
    model = shipped[key]
    shown = [p for p in model.parameters if p.panel]
    assert all(p.group for p in shown), [p.key for p in shown if not p.group]
    assert all(p.control in CONTROLS for p in shown)
    assert all(model.curve_of(p.key) for p in shown if p.control == "curve")
    assert all(p.low > 0 for p in shown if p.control == "rate")


def test_the_named_stops_match_the_disease_experiments(shipped):
    water, stress = shipped["water"], shipped["stress"]
    assert [s.value for s in water.parameter("avp_scale").stops] == [1.0, 0.5, 0.05]
    assert [s.value for s in water.parameter("kidney").stops] == [1.0, 0.5, 0.05]
    assert [s.name for s in stress.parameter("stalk").stops] == ["Intact", "Half", "Cut"]
    assert [s.value for s in stress.parameter("stalk").stops] == [1.0, 0.5, 0.0]


def test_the_planned_curves_exist(shipped):
    assert [c.key for c in shipped["stress"].curves] == ["gr", "mr", "sat", "tumour"]
    assert [c.key for c in shipped["water"].curves] == ["avp", "kidney", "thirst", "drinking"]
    assert shipped["stress"].curve("gr").parameters == ("K_GR", "n")
    assert shipped["water"].curve("drinking").parameters == ("drink_threshold", "drink_gain")


def test_each_curve_draws_finite_points_at_normal(shipped):
    for model in shipped.values():
        for curve in model.curves:
            points = curve_points(model, curve, {}, 50)
            assert all(math.isfinite(y) for _, y in points), (model.key, curve.key)


def test_every_rate_has_both_notes(shipped):
    for model in shipped.values():
        texts = tomllib.loads((SRC / "knowledge" / "en" / f"lab-{model.key}.toml").read_text())
        for p in model.parameters:
            if p.panel and p.control == "rate":
                assert f"parameter.{p.key}.up" in texts and f"parameter.{p.key}.down" in texts, p.key


def test_every_curve_is_checked_against_its_model_effect():
    linked = {}
    for key in ("stress", "water"):
        rows = tomllib.loads((SRC / "models" / f"{key}.toml").read_text())["curves"]
        linked |= {(key, row["key"]): row.get("matches") for row in rows}
    assert {k for k, v in linked.items() if v is None} == {("stress", "tumour")}
