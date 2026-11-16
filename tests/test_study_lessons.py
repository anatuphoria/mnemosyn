import json

import pytest

from cns_study.lessons import (EXTENSION, FORMAT, MAX_STEPS, NEWER, NOT_A_LESSON, Lesson,
                               LessonError, Step, dumps, loads, read, write)

VIEW = Step("view", "The motor strip", "Look in front of the central sulcus.",
            {"workspace": "Explore", "selected": 101, "hidden": [3, 5],
             "camera": [[1.0, 2.0, 3.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], "axis": "coronal",
             "mm": -12.5, "volume": ""})
ROUTE = Step("route", "Where it crosses", "", {"key": "motor", "side": "right", "index": 2})
LAB = Step("lab", "Standing", "Watch the dip.", {"experiment": "format = 1\n", "playhead": 2.5})
QUIZ = Step("quiz", "Check yourself", "", {"level": "routes", "mode": "route-next",
                                           "scope": "Sensory and motor"})
LESSON = Lesson("Movement", "A. Teacher", "cns-atlas", (VIEW, ROUTE, LAB, QUIZ))


def test_a_lesson_survives_a_round_trip(tmp_path):
    assert loads(dumps(LESSON)) == LESSON
    path = write(tmp_path / "movement", LESSON)
    assert path.suffix == EXTENSION and read(path) == LESSON
    assert json.loads(path.read_text())["format"] == FORMAT


def test_steps_can_be_added_moved_changed_and_removed():
    lesson = Lesson("T").with_step(VIEW).with_step(QUIZ).with_step(ROUTE, at=1)
    assert [s.kind for s in lesson.steps] == ["view", "route", "quiz"]
    assert [s.kind for s in lesson.moved(2, -2).steps] == ["quiz", "view", "route"]
    assert lesson.moved(0, -1) is lesson and lesson.moved(2, 1) is lesson
    assert lesson.changed(0, note="New").steps[0].note == "New"
    assert [s.kind for s in lesson.without(1).steps] == ["view", "quiz"]


def broken(**changes) -> str:
    data = json.loads(dumps(LESSON))
    data.update(changes)
    return json.dumps(data)


def step_with(which: int, **data) -> str:
    whole = json.loads(dumps(LESSON))
    whole["steps"][which]["data"].update(data)
    return json.dumps(whole)


@pytest.mark.parametrize("text", [
    "", "not json", "[]", '{"format": 1}', broken(mnemosyn="experiment"), broken(format="1"),
    broken(format=True), broken(title=5), broken(steps="none"),
    broken(steps=[{"kind": "movie"}]), broken(steps=[5]), broken(title="x" * 201),
    broken(steps=[{"kind": "view"}] * (MAX_STEPS + 1)),
    step_with(0, workspace="Lab"), step_with(0, selected="one"), step_with(0, hidden=[1.5]),
    step_with(0, camera=[[1, 2, 3]]), step_with(0, camera=[[1, 2, "x"], [0, 0, 0], [0, 0, 1]]),
    step_with(0, mm=float("nan")), step_with(0, axis="oblique"),
    step_with(1, side="both"), step_with(1, index=-1), step_with(1, key=None),
    step_with(2, playhead=-1), step_with(2, experiment=5),
    step_with(3, level="cells"), step_with(3, mode="flashcard"), step_with(3, scope=[1]),
])
def test_a_damaged_or_foreign_file_is_refused_with_a_plain_message(text):
    with pytest.raises(LessonError) as caught:
        loads(text)
    assert str(caught.value).startswith(NOT_A_LESSON)


def test_a_lesson_from_a_newer_version_says_so():
    with pytest.raises(LessonError, match=NEWER):
        loads(broken(format=FORMAT + 1))


def test_reading_refuses_missing_huge_and_binary_files(tmp_path):
    with pytest.raises(LessonError):
        read(tmp_path / "missing.mnemolesson")
    huge = tmp_path / "huge.mnemolesson"
    huge.write_text(" " * 2_000_001)
    with pytest.raises(LessonError, match="too large"):
        read(huge)
    binary = tmp_path / "binary.mnemolesson"
    binary.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(LessonError):
        read(binary)


def test_unknown_extra_fields_are_dropped_not_kept():
    text = step_with(0, script="rm -rf", workspace="Slices")
    step = loads(text).steps[0]
    assert "script" not in step.data and step.data["workspace"] == "Slices"


LESION = {"masks": {"brain": {"shape": [4, 5, 6], "bits": "eJxjYAAAAAEAAQ=="}}, "camera": None}


def test_a_lesion_step_is_kept_and_its_images_are_checked():
    lesson = Lesson("Case", steps=(Step("lesion", "Lesion", "Find it.", LESION),))
    assert loads(dumps(lesson)) == lesson
    for bad in ({"masks": {}}, {"masks": {"brain": {"shape": [4, 5], "bits": ""}}},
                {"masks": {"brain": {"shape": [4000, 5, 6], "bits": ""}}},
                {"masks": {"brain": {"shape": [2000, 2000, 2000], "bits": ""}}},
                {"masks": {"brain": {"shape": [4, 5, 6], "bits": 7}}},
                {"masks": {"brain": "all of it"}}):
        text = json.dumps({"mnemosyn": "lesson", "format": FORMAT,
                           "steps": [{"kind": "lesion", "data": bad}]})
        with pytest.raises(LessonError):
            loads(text)


def test_a_packed_mask_unpacks_to_itself_and_a_swollen_one_is_refused():
    import base64
    import zlib

    import numpy as np

    from cns_atlas.lesions import pack_mask, unpack_mask

    mask = np.zeros((7, 5, 3), dtype=bool)
    mask[1, 2, 0] = mask[6, 4, 2] = True
    packed = pack_mask(mask)
    assert packed["shape"] == [7, 5, 3] and np.array_equal(unpack_mask(packed), mask)
    bomb = base64.b64encode(zlib.compress(bytes(10_000_000))).decode()
    for bits in (bomb, "not base64 !", base64.b64encode(b"plain").decode()):
        with pytest.raises(ValueError):
            unpack_mask({"shape": [7, 5, 3], "bits": bits})
