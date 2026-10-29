import tomllib

import pytest

from cns_lab.experiment import Block, Experiment
from cns_lab.files import EXTENSION, FileError, read, write
from lab_helpers import toy_model


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    model = toy_model(tmp_path_factory.mktemp("toy"))
    return {model.key: model}


EXPERIMENT = Experiment(
    "toy", 1, 4320.0, 480.0,
    (Block("pill", 600.0, None, (("dose", 2.0),)),
     Block("stress", 700.5, 60.0, (("strength", 1.5),)),
     Block("remove_b", 0.0, None, (), "present")),
    (("k", 3.0),), "Morning test", 'A note with "quotes"\nand two lines.')


def test_the_extension():
    assert EXTENSION == ".mnemolab"


def test_an_experiment_round_trips(tmp_path, models):
    path = tmp_path / f"one{EXTENSION}"
    write(path, EXPERIMENT)
    experiment, report = read(path, models)
    assert experiment == EXPERIMENT and report == ()


def test_the_file_holds_only_the_experiment(tmp_path):
    path = tmp_path / "one.mnemolab"
    write(path, EXPERIMENT)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"format", "system", "model_version", "length", "start_clock", "title",
                         "note", "values", "blocks"}
    assert data["length"] == "3 d" and data["start_clock"] == "08:00"
    assert set(data["blocks"][1]) == {"experiment", "start", "length", "mode", "options"}
    assert "length" not in data["blocks"][0]


def edited(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_reading_drops_unknown_and_clamps_out_of_range_with_a_report(tmp_path, models):
    path = tmp_path / "one.mnemolab"
    write(path, EXPERIMENT)
    edited(path, "model_version = 1", "model_version = 2")
    edited(path, 'experiment = "stress"', 'experiment = "fever"')
    edited(path, "dose = 2.0", "dose = 11.0\ncolour = 1.0")
    edited(path, "k = 3.0", "k = 20.0\nq = 1.0")
    experiment, report = read(path, models)
    assert report == (
        "This file was made with version 2 of the model; this is version 1.",
        "Feedback halfway point was 20 model units, outside 0.1 to 10; it is now 10.",
        "The value q is not in this model and was left out.",
        "The change fever is not in this model and was left out.",
        "The option colour of Y pill is not in this model and was left out.",
        "Dose of Y pill was 11 units, outside 0 to 10; it is now 10.",
    )
    assert experiment.value_map == {"k": 10.0}
    assert [b.experiment for b in experiment.blocks] == ["pill", "remove_b"]
    assert experiment.blocks[0].option_map == {"dose": 10.0}


def test_a_change_outside_the_run_is_moved_inside(tmp_path, models):
    path = tmp_path / "one.mnemolab"
    write(path, EXPERIMENT.replace(blocks=(Block("pill", 9000.0, None, (("dose", 1.0),)),)))
    experiment, report = read(path, models)
    assert experiment.blocks[0].start == 4319.0
    assert report == ("Y pill started after the end of the run and was moved to its end.",)


def test_a_file_for_an_unknown_system_is_refused(tmp_path, models):
    path = tmp_path / "one.mnemolab"
    write(path, EXPERIMENT.replace(system="sleep"))
    with pytest.raises(FileError, match="sleep"):
        read(path, models)


@pytest.mark.parametrize("text", ["not toml [", 'format = 1\nsystem = "toy"\n',
                                  'format = 9\nsystem = "toy"\nmodel_version = 1\n'])
def test_a_broken_file_is_refused(tmp_path, models, text):
    path = tmp_path / "one.mnemolab"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(FileError):
        read(path, models)
