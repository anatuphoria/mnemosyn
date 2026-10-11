import random

import numpy as np
import pytest
from fsrs import Rating
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_study.session import QuizChoice

TRACT_LEAVES = (151, 152, 160)
GREY = (101, 102, 111, 112, 120, 131, 132, 140)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, root, tmp_path):
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    return w


@pytest.fixture
def window(qapp, toy_tract_atlas, tmp_path):
    w = open_window(qapp, toy_tract_atlas, tmp_path)
    yield w
    w.close()


def find_pixel(view, want, step=6):
    width, height = view.ren_win.GetSize()
    points = [(x, y) for y in range(step, height, step) for x in range(step, width, step)]
    points.sort(key=lambda p: (p[0] - width / 2) ** 2 + (p[1] - height / 2) ** 2)
    for x, y in points:
        sid = view.structure_at(x, y)
        if want(sid):
            return x, y, sid
    raise AssertionError("no matching pixel")


def test_tracts_start_hidden_and_unbuilt(window):
    assert window.state.tract_ids == TRACT_LEAVES
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert not any(window.state.is_hidden(i) for i in GREY)
    assert window.view.tract_actor is None and window.view.tract_builds == 0
    assert window.tree.items[150].checkState(0) == Qt.CheckState.Unchecked
    assert window.tree.items[2].checkState(0) == Qt.CheckState.PartiallyChecked


def test_grey_matter_keeps_its_own_composite(window):
    assert tuple(window.view.ids) == GREY
    data = window.view.composite_mapper.GetInputDataObject(0, 0)
    assert data.GetNumberOfBlocks() == len(GREY)


def test_the_tracts_action_shows_and_hides_every_tract(window):
    action = window.shortcuts["Tracts"]
    action.trigger()
    assert not any(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert window.view.is_drawn(151) and window.view.tract_builds == 1
    action.trigger()
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert not window.view.is_drawn(151)
    action.trigger()
    assert window.view.is_drawn(160) and window.view.tract_builds == 1


def test_selecting_a_tract_shows_builds_and_highlights_it(window):
    window.state.select(160)
    assert not window.state.is_hidden(160) and window.state.is_hidden(151)
    assert window.view.tract_builds == 1 and window.view.is_drawn(160)
    assert window.view.overlay_ids == [160]


def test_selecting_a_concept_shows_both_sides(window):
    window.state.select(150)
    assert not window.state.is_hidden(151) and not window.state.is_hidden(152)


def test_selecting_a_mixed_group_does_not_show_tracts(window):
    window.state.select(2)
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)


def test_a_shown_tract_can_be_picked_in_3d(window):
    window.shortcuts["Tracts"].trigger()
    window.state.set_hidden(GREY, True)
    window.view.render()
    x, y, structure_id = find_pixel(window.view, lambda s: s in TRACT_LEAVES)
    window.view.pick_at(x, y)
    assert window.state.selected == structure_id


def test_the_tracts_action_is_harmless_without_a_tract_layer(qapp, toy_atlas, tmp_path):
    w = open_window(qapp, toy_atlas, tmp_path)
    w.shortcuts["Tracts"].trigger()
    assert w.state.tract_ids == () and w.view.tract_actor is None
    w.close()


def test_slices_outline_visible_tracts_only(window):
    window.state.set_slice("axial", -4.0)
    before = window.slices.image.copy()
    window.shortcuts["Tracts"].trigger()
    assert window.slices.image[35, 10, :3].tolist() == window.slices.colors[151].tolist()
    window.state.set_hidden(window.state.tract_ids, True)
    assert window.slices.image[35, 10, :3].tolist() == before[35, 10, :3].tolist()


def test_a_selected_tract_is_filled_in_slices(window):
    window.shortcuts["Tracts"].trigger()
    window.state.set_slice("axial", 4.0)
    plain = window.slices.image[34, 9, :3].copy()
    window.state.select(150)
    assert window.slices.image[34, 9, :3].tolist() != plain.tolist()


def test_slice_clicks_pick_the_smallest_visible_tract_else_the_label(window):
    window.state.set_slice("axial", -4.0)
    window.shortcuts["Tracts"].trigger()
    assert window.slices.structure_at_pixel(34, 8) == 160
    window.state.set_hidden([160], True)
    assert window.slices.structure_at_pixel(34, 8) == 151
    window.state.set_hidden(window.state.tract_ids, True)
    assert window.slices.structure_at_pixel(34, 8) not in TRACT_LEAVES


def start_quiz(window, mode, level):
    window.start_quiz(QuizChoice(mode, level, None, False), rng=random.Random(1))
    return window.quiz


def test_name_it_on_tracts_shows_only_the_asked_tract(window):
    quiz = start_quiz(window, "name-typed", "tracts")
    assert quiz.item.id == 150 and "tract" in quiz.prompt.text()
    assert not window.state.is_hidden(151) and window.state.is_hidden(160)
    quiz.submit_text("long tract")
    assert "Correct" in quiz.feedback.text()
    quiz.go_on(Rating.Easy)
    assert quiz.item.id == 160
    assert not window.state.is_hidden(160) and window.state.is_hidden(151)


def test_find_it_on_tracts_shows_every_tract(window):
    start_quiz(window, "find", "tracts")
    assert not any(window.state.is_hidden(i) for i in TRACT_LEAVES)


def test_other_levels_hide_tracts_and_leaving_restores_them(window):
    window.shortcuts["Tracts"].trigger()
    quiz = start_quiz(window, "name-typed", "structures")
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert not window.shortcuts["Tracts"].isEnabled()
    quiz.stop()
    assert not any(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert window.shortcuts["Tracts"].isEnabled()


def test_the_setup_dialog_offers_the_tracts_level(window):
    dialog = window.open_quiz_setup()
    assert dialog.level.count() == 3
    dialog.level.setCurrentIndex(2)
    assert dialog.note.text() == "0 due, 2 new"
    dialog.reject()


def test_a_grey_matter_quiz_never_builds_the_tracts(window):
    quiz = start_quiz(window, "name-typed", "structures")
    assert window.view.tract_builds == 0
    quiz.stop()
    assert window.view.tract_builds == 0
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)


def test_find_it_accepts_a_click_inside_the_asked_tract_under_a_smaller_one(window, qapp):
    quiz = start_quiz(window, "find", "tracts")
    assert quiz.item.id == 150
    window.state.set_slice("axial", -4.0)
    window.slices.click_pixel(34, 8)
    qapp.processEvents()
    assert "Correct" in quiz.feedback.text()
    quiz.stop()
    window.shortcuts["Tracts"].trigger()
    window.state.set_slice("axial", -4.0)
    assert window.slices.structure_at_pixel(34, 8) == 160


def test_centring_on_a_tract_moves_the_slice_to_it(window):
    window.state.select(160)
    window.state.set_slice("axial", -56.0)
    window.slices.centre_on_selection()
    assert -4.0 <= window.state.slice_mm <= 4.0


def test_leaving_a_quiz_keeps_a_hidden_selected_tract_hidden(window):
    window.state.select(160)
    window.state.set_hidden([160], True)
    start_quiz(window, "name-typed", "structures").stop()
    assert window.state.selected == 160 and window.state.is_hidden(160)


def test_show_all_restores_grey_matter_but_leaves_tracts_to_t(window):
    window.state.set_hidden([101], True)
    window.state.show_all()
    assert not window.state.is_hidden(101)
    assert all(window.state.is_hidden(i) for i in TRACT_LEAVES)
    assert window.view.tract_builds == 0


def test_grey_matter_is_dimmed_only_while_a_tract_is_named(window):
    opacity = window.view.actor.GetProperty().GetOpacity
    quiz = start_quiz(window, "name-typed", "tracts")
    assert opacity() == pytest.approx(0.15)
    quiz.stop()
    assert opacity() == pytest.approx(1.0)
    start_quiz(window, "find", "tracts").stop()
    start_quiz(window, "name-typed", "structures")
    assert opacity() == pytest.approx(1.0)


def test_a_hidden_tract_over_a_label_gives_the_label(window):
    window.state.set_slice("axial", -32.0)
    assert window.slices.structure_at_pixel(35, 22) == 120
    window.shortcuts["Tracts"].trigger()
    assert window.slices.structure_at_pixel(35, 22) == 152


def test_slices_ignore_a_tract_layer_on_another_grid(window):
    window.shortcuts["Tracts"].trigger()
    window.state.set_slice("axial", -4.0)
    layer = window.slices.tracts
    layer.affine = np.asarray(layer.affine, dtype=float).copy()
    layer.affine[0, 3] += 4.0
    assert window.slices.structure_at_pixel(34, 8) not in TRACT_LEAVES


def test_the_summary_is_not_dimmed(window):
    quiz = start_quiz(window, "name-typed", "tracts")
    while quiz.phase == "asking":
        quiz.submit_text(quiz.item.name)
        quiz.go_on(Rating.Easy)
    assert quiz.phase == "summary"
    assert window.view.actor.GetProperty().GetOpacity() == pytest.approx(1.0)
