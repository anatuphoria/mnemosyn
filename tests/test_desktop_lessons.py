import numpy as np
import pytest
from PySide6.QtWidgets import QMessageBox

from cns_atlas.lesions import Lesion, pack_mask

from cns_desktop.app import open_file
from cns_desktop.window_lessons import (KEPT, NO_ROUTE, NOT_HERE, NOTHING_TO_ASK,
                                        OTHER_IMAGES)
from cns_study.lessons import Lesson, Step, read, write
from pathway_helpers import open_window

pytestmark = pytest.mark.usefixtures("themed")
Button = QMessageBox.StandardButton


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    w.told = []
    w.inform = lambda title, text: w.told.append((title, text))
    w.ask = lambda *_args: Button.Discard
    yield w
    if w.lesson_window is not None:
        w.lesson_window.saved = w.lesson_window.lesson
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def a_route(window):
    return next(p for p in window.state.atlas.pathways if len(p.steps) >= 3)


def test_a_view_step_brings_back_the_selection_the_hidden_parts_and_the_slice(window):
    state = window.state
    first, second = state.geometry_ids[0], state.geometry_ids[1]
    state.select(first)
    state.set_hidden([second], True)
    state.set_slice("coronal", 3.0)
    placed = state.slice_mm
    camera = window.view.camera_position.to_list()
    step = window.capture_step()
    assert step.kind == "view" and step.title == state.atlas.get(first).name
    state.show_all()
    state.select(None)
    state.set_slice("axial", 0.0)
    window.view.camera.azimuth += 40
    assert window.show_step(step) == []
    assert state.selected == first and state.is_hidden(second)
    assert (state.slice_axis, state.slice_mm) == ("coronal", placed)
    restored = window.view.camera_position.to_list()
    assert restored[0] == pytest.approx(camera[0]) and restored[2] == pytest.approx(camera[2])


def test_a_route_step_reopens_the_route_at_its_station(window):
    pathway = a_route(window)
    window.workspaces.switch("Pathways")
    window.pathways.open(pathway.key, "right")
    window.pathways.go(2)
    step = window.capture_step()
    assert step.kind == "route" and step.data == {"key": pathway.key, "side": "right", "index": 2}
    window.pathways.leave()
    window.workspaces.switch("Explore")
    assert window.show_step(step) == []
    assert window.pathway_active and window.workspaces.current == "Pathways"
    panel = window.pathways
    assert (panel.pathway.key, panel.side, panel.index) == (pathway.key, "right", 2)


def test_a_lab_step_rebuilds_the_experiment_at_its_moment(window):
    window.workspaces.switch("Lab")
    document = window.lab.document
    document.add_block("stress", 120.0)
    document.set_playhead(300.0)
    step = window.capture_step()
    assert step.kind == "lab" and step.title == document.model.name
    document.new()
    window.workspaces.switch("Explore")
    assert window.show_step(step) == []
    assert window.workspaces.current == "Lab" and document.playhead == 300.0
    assert [(b.experiment, b.start) for b in document.experiment.blocks] == [("stress", 120.0)]


def test_a_lab_step_does_not_throw_away_an_unsaved_experiment(window):
    window.workspaces.switch("Lab")
    step = window.capture_step()
    window.lab.document.add_block("remove_b", 60.0)
    window.ask = lambda *_args: Button.Cancel
    assert window.show_step(step) == [KEPT]
    assert len(window.lab.document.experiment.blocks) == 1


def test_a_question_step_starts_a_practice_round_and_the_next_step_ends_it(window):
    quiz = Step("quiz", data={"level": "structures", "mode": "name-choice", "scope": None})
    assert window.show_step(quiz) == []
    assert window.quiz_active and window.quiz.session.practice
    view = Step("view", data={"workspace": "Slices", "selected": None, "hidden": [],
                              "camera": None, "axis": "axial", "mm": 0.0, "volume": ""})
    assert window.show_step(view) == []
    assert not window.quiz_active and window.workspaces.current == "Slices"


def test_steps_made_on_a_fuller_atlas_say_what_is_missing(window):
    known = window.state.geometry_ids[0]
    view = Step("view", data={"workspace": "Explore", "selected": 987654, "hidden": [known, 987655],
                              "camera": None, "axis": "axial", "mm": 0.0, "volume": "nowhere"})
    assert window.show_step(view) == ["2 structures of this step are not in this atlas."]
    assert window.state.selected is None and window.state.is_hidden(known)
    route = Step("route", data={"key": "no-such-route", "side": "left", "index": 0})
    assert window.show_step(route) == [NO_ROUTE]
    lab = Step("lab", data={"experiment": "format = 1\nsystem = \"nothing\"\n", "playhead": 0.0})
    assert window.show_step(lab) and window.workspaces.current != "Lab"
    quiz = Step("quiz", data={"level": "lab", "mode": "lab-predict", "scope": "no-such-system"})
    assert window.show_step(quiz) == [NOTHING_TO_ASK] and not window.quiz_active


def test_a_teacher_builds_edits_and_saves_a_lesson(window, tmp_path, qapp):
    lesson = window.new_lesson()
    assert lesson.editing and lesson.isVisible() and not lesson.isModal()
    assert not lesson.modified() and lesson.steps.count() == 0
    window.state.select(window.state.geometry_ids[0])
    lesson.add_view.click()
    window.workspaces.switch("Lab")
    lesson.add_view.click()
    assert [s.kind for s in lesson.lesson.steps] == ["view", "lab"] and lesson.index == 1
    lesson.step_title.setText("The Lab part")
    lesson.step_title.textEdited.emit("The Lab part")
    lesson.note.setPlainText("Watch the curve.")
    assert lesson.lesson.steps[1].title == "The Lab part"
    assert lesson.lesson.steps[1].note == "Watch the curve."
    assert "The Lab part" in lesson.steps.item(1).text()
    lesson.up.click()
    assert [s.kind for s in lesson.lesson.steps] == ["lab", "view"] and lesson.index == 0
    lesson.title.setText("My lesson")
    lesson.title.textEdited.emit("My lesson")
    assert lesson.modified() and "(changed)" in lesson.windowTitle()
    target = tmp_path / "mine"
    window.pick_lesson_save = lambda: str(target)
    lesson.save_button.click()
    saved = read(target.with_suffix(".mnemolesson"))
    assert saved == lesson.lesson and saved.title == "My lesson" and not lesson.modified()
    lesson.delete.click()
    assert [s.kind for s in lesson.lesson.steps] == ["view"]


def test_a_place_that_cannot_be_a_step_says_where_to_go(window):
    lesson = window.new_lesson()
    window.workspaces.switch("Lesion")
    lesson.add_view.click()
    assert lesson.report.text() == NOT_HERE and lesson.lesson.steps == ()


def a_lesion(window):
    atlas = window.state.atlas
    lesion = Lesion.empty(atlas)
    name, mask = next(iter(lesion.masks.items()))
    mask = mask.copy()
    mask[tuple(n // 2 for n in mask.shape)] = True
    mask[0, 0, 0] = True
    return lesion.with_mask(name, mask)


def test_a_lesion_step_brings_back_the_lesion_and_can_be_undone(window, tmp_path):
    window.workspaces.switch("Lesion")
    made = a_lesion(window)
    document = window.lesion.document
    document.set_lesion(made, "Brush")
    step = window.capture_step()
    assert step.kind == "lesion" and step.title.startswith("Lesion")
    path = tmp_path / "case.mnemolesson"
    write(path, Lesson("Case", steps=(step,)))
    step = read(path).steps[0]
    document.clear()
    window.workspaces.switch("Explore")
    assert window.show_step(step) == []
    assert window.workspaces.current == "Lesion"
    for name, mask in made.masks.items():
        assert np.array_equal(document.lesion.masks[name], mask), name
    document.undo.undo()
    assert document.lesion.is_empty


def test_a_lesion_made_on_other_images_is_reported_and_not_shown(window):
    window.workspaces.switch("Lesion")
    window.lesion.document.set_lesion(a_lesion(window), "Brush")
    step = window.capture_step()
    name = next(iter(step.data["masks"]))
    other = {**step.data, "masks": {name: pack_mask(np.ones((2, 2, 2), dtype=bool))}}
    window.lesion.document.clear()
    assert window.show_step(Step("lesion", "Lesion", data=other)) == [OTHER_IMAGES]
    damaged = {**step.data, "masks": {name: {**step.data["masks"][name], "bits": "AAAA"}}}
    assert window.show_step(Step("lesion", "Lesion", data=damaged)) == [OTHER_IMAGES]
    assert window.lesion.document.lesion.is_empty


def test_questions_are_added_from_the_quiz_setup(window):
    lesson = window.new_lesson()
    setup_holder = {}
    original = window.open_quiz_setup

    def opened():
        setup_holder["setup"] = original()
        return setup_holder["setup"]

    window.open_quiz_setup = opened
    lesson.add_quiz.click()
    setup = setup_holder["setup"]
    setup.level.setCurrentIndex(3)
    setup.accept()
    step = lesson.lesson.steps[0]
    assert step.kind == "quiz" and step.data["level"] == "routes"
    assert step.data["mode"] == "route-next" and step.title == "Questions on routes"


def test_a_student_opens_a_lesson_and_walks_it(window, tmp_path):
    pathway = a_route(window)
    made = Lesson("Movement", "A. Teacher", "toy", (
        Step("view", "Start", "Look here.", {"workspace": "Slices", "selected": None, "hidden": [],
                                             "camera": None, "axis": "sagittal", "mm": 1.0,
                                             "volume": ""}),
        Step("route", "The route", "", {"key": pathway.key, "side": "left", "index": 1})))
    path = write(tmp_path / "movement", made)
    assert open_file(window, path)
    lesson = window.lesson_window
    assert not lesson.editing and lesson.index == 0 and window.workspaces.current == "Slices"
    assert lesson.shown_note.text() == "Look here." and not lesson.note.isVisible()
    assert not lesson.add_view.isVisible() and lesson.title.isReadOnly()
    assert not lesson.back.isEnabled() and lesson.forward.isEnabled()
    lesson.forward.click()
    assert window.pathway_active and window.pathways.index == 1
    assert lesson.shown_note.text() == "No note for this step." and not lesson.forward.isEnabled()
    window.pathways.go(0)
    lesson.again.click()
    assert window.pathways.index == 1
    lesson.edit_button.click()
    assert lesson.editing and lesson.add_view.isVisible()


def test_a_bad_lesson_file_is_refused_politely(window, tmp_path):
    bad = tmp_path / "bad.mnemolesson"
    bad.write_text("{not a lesson")
    assert not open_file(window, bad)
    assert window.lesson_window is None
    assert window.told and window.told[0][0] == "Cannot open the lesson"


def test_closing_asks_about_unsaved_changes(window):
    lesson = window.new_lesson()
    lesson.add_view.click()
    window.ask = lambda *_args: Button.Cancel
    assert not lesson.close() and window.lesson_window is lesson
    assert window.new_lesson() is None
    window.ask = lambda *_args: Button.Discard
    assert lesson.close() and window.lesson_window is None
    assert [a.text() for a in window.topbar.menu("File").actions() if "esson" in a.text()] == [
        "New lesson", "Open lesson…"]


def three_steps():
    view = {"workspace": "Slices", "selected": None, "hidden": [], "camera": None,
            "axis": "sagittal", "mm": 1.0, "volume": ""}
    return Lesson("Movement", "", "toy", tuple(Step("view", f"Step {n}", "", dict(view))
                                              for n in (1, 2, 3)))


def test_the_lesson_window_names_its_mode_its_step_and_where_you_are(window, tmp_path):
    from PySide6.QtWidgets import QToolButton

    assert open_file(window, write(tmp_path / "three", three_steps()))
    lesson = window.lesson_window
    assert lesson.tag.text() == "Playing"
    assert lesson.shown_title.text() == "Movement" and lesson.shown_title.isVisible()
    assert not lesson.title.isVisible()
    lesson.forward.click()
    assert lesson.step_heading.text() == "STEP 2 OF 3" and lesson.position.text() == "2 / 3"
    assert lesson.shown_step.text() == "Step 2"
    assert all(isinstance(b, QToolButton) for b in (lesson.up, lesson.down, lesson.delete,
                                                     lesson.back, lesson.forward))
    assert lesson.again.text() == "Show again"
    lesson.set_editing(True)
    assert lesson.tag.text() == "Editing" and lesson.title.isVisible()
    assert not lesson.shown_title.isVisible() and lesson.up.isVisible()


def test_an_empty_lesson_says_step_and_none_of_none(window):
    lesson = window.new_lesson()
    assert lesson.tag.text() == "Editing"
    assert lesson.step_heading.text() == "STEP" and lesson.position.text() == "0 / 0"
    assert not lesson.back.isEnabled() and not lesson.forward.isEnabled()
