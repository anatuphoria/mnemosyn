import pytest

from atlas_fixtures import TOY_LAB_TEXTS, TOY_MODEL
from cns_atlas import Atlas
from lab_helpers import load_toy
from tools.build_atlas.recipe import BuildError


def test_the_toy_model_loads(tmp_path):
    (model,) = load_toy(tmp_path)
    assert model.key == "toy" and model.name == "Toy axis" and model.route == "mood"
    assert [p.structure for p in model.parts] == [111, 100, None]
    assert model.experiment("stress").length == 60 and model.max_step == 30
    assert model.experiment("pill").options[0].name == "Dose"
    assert model.tests[0].readings[0].after == 60
    stressed = next(c for c in model.checks if c.key == "stressed")
    assert stressed.blocks[0]["start"] == 120
    assert stressed.asserts[1]["by"] == 900
    rhythm = next(c for c in model.checks if c.key == "rhythm")
    assert rhythm.asserts[0]["expect"] == [240, 600]


def test_the_toy_model_builds_into_the_package(toy_lab_atlas):
    atlas = Atlas.open(toy_lab_atlas)
    assert atlas.models["toy"].parts[0].structure == 111
    assert atlas.lab_text("toy", "effect.fb")[0] == "Y holds back the making of X [1]."


def swap(old: str, new: str, text: str = TOY_MODEL) -> str:
    assert old in text
    return text.replace(old, new, 1)


MISTAKES = [
    ("unknown key", swap('version = 1', 'version = 1\ncolour = 1'), "unknown keys ['colour']"),
    ("unknown name", swap('"w * x"', '"w * x * q"'), "unknown names ['q']"),
    ("bad grammar", swap('"w * x"', '"w.x"'), "not allowed"),
    ("unknown value", swap('value = "x"\nsign = -1', 'value = "z"\nsign = -1'),
     "unknown value 'z'"),
    ("default outside range", swap("value = 0.1\n", "value = 5\n"), "outside 0.01 to 1"),
    ("unknown structure", swap("structure = 111", "structure = 999"), "unknown structure 999"),
    ("unknown arrow part", swap('arrow = ["b", "a"]', 'arrow = ["b", "q"]'),
     "unknown part 'q'"),
    ("unknown edit target", swap('target = "m"', 'target = "q"'), "clamp needs a value"),
    ("option outside range", swap("default = 1, low = 0, high = 10 }]\nedits = [{ op = \"dose\", "
                                  "target = \"y\", expr = \"dose\" }]",
                                  "default = 11, low = 0, high = 10 }]\nedits = [{ op = \"dose\", "
                                  "target = \"y\", expr = \"dose\" }]"), "outside 0 to 10"),
    ("bad time", swap('length = "1 h"', 'length = "1 hour"'), "a duration is written"),
    ("unknown route", swap('route = "mood"', 'route = "sleep"'), "unknown route 'sleep'"),
    ("unknown assert", swap('kind = "within"', 'kind = "near"'), "kind must be one of"),
    ("unknown check experiment", swap('experiment = "pill_test"', 'experiment = "nope"'),
     "needs a known experiment or test"),
]


@pytest.mark.parametrize(("label", "model", "problem"), MISTAKES, ids=[m[0] for m in MISTAKES])
def test_model_mistakes_are_reported(tmp_path, label, model, problem):
    with pytest.raises(BuildError) as found:
        load_toy(tmp_path, model)
    assert any(problem in p and "toy.toml" in p for p in found.value.problems), found.value.problems


TEXT_MISTAKES = [
    ("missing text", TOY_LAB_TEXTS.replace('"term.clear_x" = "X is cleared."\n', ""),
     "text 'term.clear_x' is missing"),
    ("missing note", TOY_LAB_TEXTS.replace('"value.y.note" = "Y has no measured unit."\n', ""),
     "text 'value.y.note' is missing"),
    ("unused text", TOY_LAB_TEXTS + '"term.gone" = "Not used."\n', "'term.gone'"),
    ("missing reference", TOY_LAB_TEXTS.replace("[ref2020].\"\n\"normal.night", "[nope].\"\n"
                                                "\"normal.night"), "missing reference [nope]"),
]


@pytest.mark.parametrize(("label", "texts", "problem"), TEXT_MISTAKES,
                         ids=[m[0] for m in TEXT_MISTAKES])
def test_text_mistakes_are_reported(tmp_path, label, texts, problem):
    with pytest.raises(BuildError) as found:
        load_toy(tmp_path, TOY_MODEL, texts)
    assert any(problem in p for p in found.value.problems), found.value.problems


def test_the_file_name_must_match_the_key(tmp_path):
    from tools.build_atlas.models import load_models

    load_toy(tmp_path)
    (tmp_path / "models" / "toy.toml").rename(tmp_path / "models" / "other.toml")
    with pytest.raises(BuildError) as found:
        load_models(tmp_path / "models", tmp_path / "knowledge", {111, 101}, {"ref2020": 1},
                    {"mood"})
    assert any("file name must be toy.toml" in p for p in found.value.problems)
