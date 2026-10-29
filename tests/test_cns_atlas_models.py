import json

import pytest

from atlas_package import tiny_structures, write_package
from cns_atlas import Atlas, AtlasError, LabModel
from cns_atlas.models import (Check, Edit, Effect, Experiment, LabTest, NormalNote, Option, Parameter,
                              Part, Reading, Term, Value)

REFERENCES = 'purves2018 = { authors = "Purves D", title = "Neuroscience", year = 2018, ' \
             'isbn = "9781605353807" }\n'


def toy_model() -> LabModel:
    return LabModel(
        key="toy", name="Toy axis", version=2, route=None, start_clock=480.0,
        settle_speedup=50.0, settle_days=10, max_step=30.0, why_threshold=0.1,
        values=(Value("x", "X", "model units", 1.0, 9.0, "µg/dL", "nmol/L", 27.59,
                      normal=(5.0, 25.0), lane=1, refs=("purves2018",)),
                Value("m", "M", "times normal", 1.0, 1.0, "times normal", relative=True,
                      slow=True)),
        parameters=(Parameter("w", "Clearance", 0.1, "/min", 0.01, 1.0, ("purves2018",)),),
        effects=(Effect("fb", "hill(x, 4, 3)", "holds back", ("b", "a")),),
        terms=(Term("make_x", "x", 1, "w * fb * m", "drives", ("a", "b")),
               Term("clear_x", "x", -1, "w * x", "clears", None)),
        parts=(Part("a", "Alpha", 101, 0.0, 0.0, ("x",)), Part("b", "Body", None, 1.0, 0.0, ())),
        experiments=(Experiment("remove", "Remove or cut", "Remove alpha", "present", None, (),
                                (Edit("clamp", "m", "0"),)),
                     Experiment("pill", "Drugs", "Pill", "from a time", 60.0,
                                (Option("dose", "Dose", "mg", 1.0, 0.0, 10.0),),
                                (Edit("dose", "x", "dose", daily=True),), weeks=True)),
        tests=(LabTest("t", "Toy test", ((0.0, "x", "1"),), (Reading("x", 60.0),), "below",
                       1.8),),
        checks=(Check("c", 2880.0, ({"experiment": "pill", "start": 0.0},),
                      ({"kind": "within", "value": "x", "at": 1920.0, "low": 1, "high": 2},)),),
        normal_notes=(NormalNote("morning", 240.0, 600.0),))


def test_a_model_round_trips_through_json():
    model = toy_model()
    assert LabModel.from_json(json.loads(json.dumps(model.to_json()))) == model


def test_an_atlas_without_models_json_has_no_models(tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures())
    assert Atlas.open(root).models == {}


def test_models_are_read_by_key(tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures())
    (root / "models.json").write_text(json.dumps([toy_model().to_json()]))
    assert Atlas.open(root).models == {"toy": toy_model()}


def test_a_malformed_models_file_is_an_atlas_error(tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures())
    (root / "models.json").write_text(json.dumps([{"key": "toy"}]))
    with pytest.raises(AtlasError):
        Atlas.open(root)


def test_lab_text_falls_back_to_english_and_numbers_citations(tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), references=REFERENCES)
    (root / "knowledge" / "en").mkdir(exist_ok=True)
    (root / "knowledge" / "en" / "lab-toy.toml").write_text(
        '"term.clear" = "Cleared fast [purves2018]."\n')
    atlas = Atlas.open(root)
    text, refs = atlas.lab_text("toy", "term.clear", "ar")
    assert text == "Cleared fast [1]." and [r.key for r in refs] == ["purves2018"]
    assert atlas.lab_text("toy", "missing") is None
    assert atlas.lab_text("other", "term.clear") is None
