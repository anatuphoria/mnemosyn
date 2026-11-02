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


def test_parameters_carry_group_control_and_stops(tmp_path):
    (model,) = load_toy(tmp_path)
    w, a = model.parameter("w"), model.parameter("a")
    assert (w.group, w.control) == ("clearing", "rate")
    assert a.control == "switch" and [s.value for s in a.stops] == [0.0, 0.3, 0.9]
    assert [s.name for s in a.stops] == ["None", "Normal", "Deep"]
    assert model.parameter("stress").control == "slider"


def test_a_curve_names_its_parameters_and_axis(tmp_path):
    (model,) = load_toy(tmp_path)
    curve = model.curve("feedback")
    assert curve.parameters == ("k",) and (curve.x_low, curve.x_high) == (0.0, 10.0)
    assert curve.name == "Feedback curve" and model.curve_of("k") is curve
    assert (curve.x_name, curve.y_name) == ("Y", "brake on X")
    assert model.parameter("k").control == "curve" and model.curve_of("w") is None


def test_groups_stops_and_curves_reach_the_package(toy_lab_atlas):
    model = Atlas.open(toy_lab_atlas).models["toy"]
    assert model.parameter("a").stops[2].name == "Deep"
    assert model.curve("feedback").expr == "hill(x, k, 2) / hill(1, k, 2)"


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
    ("panel not true or false", swap('value = 0.1\n', 'value = 0.1\npanel = "no"\n'),
     "panel must be true or false"),
    ("unknown via part", swap('arrow = ["b", "body"]', 'arrow = ["b", "body"]\nvia = ["q"]'),
     "via names unknown part 'q'"),
    ("via without arrow", swap('kind = "clears"', 'kind = "clears"\nvia = ["a"]'),
     "via needs an arrow"),
    ("unknown edit target", swap('target = "m"', 'target = "q"'), "clamp needs a value"),
    ("option outside range", swap("default = 1, low = 0, high = 10 }]\nedits = [{ op = \"dose\", "
                                  "target = \"y\", expr = \"dose\" }]",
                                  "default = 11, low = 0, high = 10 }]\nedits = [{ op = \"dose\", "
                                  "target = \"y\", expr = \"dose\" }]"), "outside 0 to 10"),
    ("bad time", swap('length = "1 h"', 'length = "1 hour"'), "a duration is written"),
    ("unknown route", swap('route = "mood"', 'route = "sleep"'), "unknown route 'sleep'"),
    ("unknown assert", swap('kind = "within"', 'kind = "near"'), "kind must be one of"),
    ("reserved clock", swap('key = "w"\nvalue = 0.1', 'key = "clock"\nvalue = 0.1'),
     "reserved name 'clock'"),
    ("reserved pi", swap('key = "w"\nvalue = 0.1', 'key = "pi"\nvalue = 0.1'),
     "reserved name 'pi'"),
    ("reserved underscore", swap('key = "m"\nunit', 'key = "_speed"\nunit'),
     "reserved name '_speed'"),
    ("reserved function", swap('key = "fb"', 'key = "hill"'), "reserved name 'hill'"),
    ("unknown check experiment", swap('experiment = "pill_test"', 'experiment = "nope"'),
     "needs a known experiment or test"),
    ("unknown icon", swap('key = "pill"\ngroup = "Drugs"', 'key = "pill"\ngroup = "Drugs"\n'
                          'icon = "no-such-icon"'), "unknown icon 'no-such-icon'"),
    ("unknown test edit target", swap('edits = [{ op = "set", target = "stress", expr = "3" }]',
                                      'edits = [{ op = "set", target = "q", expr = "3" }]'),
     "set needs a parameter"),
    ("bad test length", swap('length = "2 h"', 'length = "two hours"'),
     "a duration is written"),
    ("unknown control", swap('control = "rate"', 'control = "dial"'), "control must be one of"),
    ("rate from zero", swap('low = 0.01\nhigh = 1', 'low = 0\nhigh = 1'), "rate needs low above 0"),
    ("stop outside range", swap('{ key = "deep", value = 0.9 }', '{ key = "deep", value = 9 }'),
     "stop deep is outside 0 to 0.9"),
    ("switch with one stop", swap('stops = [{ key = "none", value = 0 }, { key = "normal", value = 0.3 }, '
                                  '{ key = "deep", value = 0.9 }]', 'stops = [{ key = "none", value = 0 }]'),
     "switch needs at least two stops"),
    ("unknown curve parameter", swap('parameters = ["k"]', 'parameters = ["nope"]'),
     "unknown parameter 'nope'"),
    ("unknown curve name", swap('"hill(x, k, 2) / hill(1, k, 2)"', '"hill(y, k, 2) / hill(1, k, 2)"'), "unknown names ['y']"),
    ("curve range", swap('x_low = 0\nx_high = 10', 'x_low = 5\nx_high = 1'), "x_low must be below x_high"),
    ("curve handle outside range", swap('x_low = 0\nx_high = 10', 'x_low = 0\nx_high = 5'),
     "k runs outside the curve's x range"),
    ("curve setting without curve control", swap('group = "feedback"\ncontrol = "curve"', 'group = "feedback"'),
     "k is in curve feedback, so its control must be curve"),
    ("curve setting off the panel", swap('group = "feedback"\ncontrol = "curve"',
                                         'group = "feedback"\ncontrol = "curve"\npanel = false'),
     "k is in curve feedback but is kept off the panel"),
    ("curve across groups", swap('parameters = ["k"]', 'parameters = ["k", "stress"]',
                                 swap('group = "stress"\n', 'group = "stress"\ncontrol = "curve"\n')),
     "curve feedback mixes the groups feedback and stress"),
    ("curve differs from its effect", swap('"hill(x, k, 2) / hill(1, k, 2)"', '"hill(x, k, 3) / hill(1, k, 3)"'),
     "curve feedback does not match fb"),
    ("curve matches nothing", swap('matches = "fb"', 'matches = "nope"'),
     "curve feedback matches unknown effect or term 'nope'"),
    ("curve input unknown", swap('input = "y"', 'input = "q"'), "curve feedback: unknown input 'q'"),
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
    ("missing group name", TOY_LAB_TEXTS.replace('"group.clearing.name" = "Clearing"\n', ""),
     "text 'group.clearing.name' is missing"),
    ("missing stop name", TOY_LAB_TEXTS.replace('"parameter.a.stop.deep" = "Deep"\n', ""),
     "text 'parameter.a.stop.deep' is missing"),
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


def test_experiments_and_tests_can_name_an_icon(tmp_path):
    model_text = swap('key = "pill"\ngroup = "Drugs"', 'key = "pill"\ngroup = "Drugs"\nicon = "pill"')
    model_text = swap('key = "pill_test"\n', 'key = "pill_test"\nicon = "test-tube"\n', model_text)
    (model,) = load_toy(tmp_path, model_text)
    assert model.experiment("pill").icon == "pill"
    assert model.tests[0].icon == "test-tube"
    assert model.experiment("stress").icon == ""


def test_the_stress_model_names_only_bundled_icons():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "atlas_src" / "models" / "stress.toml").read_text())
    named = {row.get("icon") for row in data["experiments"] + data["tests"]}
    assert None not in named
    icons = {p.stem for p in (root / "cns_desktop" / "resources" / "icons").glob("*.svg")}
    assert named <= icons
