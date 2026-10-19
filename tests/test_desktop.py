import json
import random
import shutil
import sqlite3
import time
from datetime import UTC, datetime

import numpy as np
import pytest
from fsrs import Rating, State
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from atlas_package import TOY_SOURCE, tetra, tiny_structures, write_package
from cns_atlas import DISCLAIMER, Atlas, Source
from cns_desktop.app import (disclaimer_due, main, offer_disclaimer, own_memory_mb,
                             peak_memory_mb)
from cns_desktop.main_window import MainWindow, default_progress_path, migrate_progress
from cns_desktop.state import AppState
from cns_desktop.views.about_dialog import AboutDialog, about_text
from cns_desktop.views.quiz_setup import NO_ITEMS, NO_REVIEWED, NOTHING_DUE
from cns_desktop.views.slice_panel import NO_TEMPLATE, NOT_RAS, SlicePanel
from cns_study.progress import day_start
from cns_study.session import QuizChoice


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def atlas(toy_atlas):
    return Atlas.open(toy_atlas)


@pytest.fixture
def window(qapp, atlas, tmp_path):
    w = MainWindow(atlas, progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def find_pixel(view, want=lambda sid: sid is not None, step=6):
    width, height = view.ren_win.GetSize()
    points = [(x, y) for y in range(step, height, step) for x in range(step, width, step)]
    points.sort(key=lambda p: (p[0] - width / 2) ** 2 + (p[1] - height / 2) ** 2)
    for x, y in points:
        sid = view.structure_at(x, y)
        if want(sid):
            return x, y, sid
    raise AssertionError("no matching pixel")


def test_state_select_guards_and_validates(atlas):
    state = AppState(atlas)
    seen = []
    state.selection_changed.connect(seen.append)
    state.select(101)
    state.select(101)
    assert seen == [101]
    with pytest.raises(KeyError):
        state.select(999)


def test_state_isolate_keeps_the_whole_subtree(atlas):
    state = AppState(atlas)
    assert state.geometry_ids == (101, 102, 111, 112, 120)
    state.isolate(100)
    assert not state.is_hidden(101) and not state.is_hidden(102)
    assert all(state.is_hidden(i) for i in (111, 112, 120))


def test_tree_mirrors_the_hierarchy(window):
    assert window.tree.tree.topLevelItem(0).text(0) == "Central nervous system"
    alpha = window.tree.items[100]
    assert [alpha.child(i).text(0) for i in range(alpha.childCount())] == [
        "Alpha gyrus (left)", "Alpha gyrus (right)"]


def test_tree_selection_updates_every_view(window):
    window.tree.tree.setCurrentItem(window.tree.items[111])
    assert window.state.selected == 111
    assert "Beta nucleus (left)" in window.info.toPlainText()
    assert window.view.highlighted == [111]


def test_click_in_3d_selects_structure_under_cursor(window):
    current = window.state.selected
    x, y, sid = find_pixel(window.view, lambda s: s is not None and s != current)
    window.view.pick_at(x, y)
    assert window.state.selected == sid
    assert window.tree.tree.currentItem() is window.tree.items[sid]


def test_click_on_background_keeps_selection(window):
    before = window.state.selected
    window.view.pick_at(1, 1)
    assert window.state.selected == before


def test_unchecking_a_group_hides_its_whole_subtree(window):
    window.tree.items[100].setCheckState(0, Qt.CheckState.Unchecked)
    assert window.state.is_hidden(101) and window.state.is_hidden(102)
    assert not window.view.is_drawn(101)
    assert not window.state.is_hidden(111)
    window.state.show_all()
    assert window.tree.items[100].checkState(0) == Qt.CheckState.Checked
    assert window.view.is_drawn(101)


def test_filter_matches_acronym_and_keeps_ancestors(window):
    window.tree.apply_filter("ben")
    shown = {sid for sid, item in window.tree.items.items() if not item.isHidden()}
    assert {1, 2, 110, 111, 112} <= shown
    assert 100 not in shown and 120 not in shown
    window.tree.apply_filter("")
    assert not any(item.isHidden() for item in window.tree.items.values())


def test_info_panel_shows_draft_references_source_and_disclaimer(window):
    window.state.select(101)
    text = window.info.toPlainText()
    assert "Draft" in text
    assert "Does alpha things [1]" in text
    assert "Author A (2020). A reference." in text
    assert "Toy labelled atlas" in text
    assert DISCLAIMER in text


def test_info_panel_without_entry(window):
    window.state.select(111)
    assert "No description yet." in window.info.toPlainText()


def about_rows(atlas):
    dialog = AboutDialog(atlas)
    return [dialog.sources.item(i).text() for i in range(dialog.sources.count())]


def test_about_text_has_disclaimer_and_sources(atlas):
    assert DISCLAIMER in about_text(atlas)
    assert any(row.startswith("Toy labelled atlas - Test 2024") for row in about_rows(atlas))


def test_about_dialog_fits_and_lists_every_source(window, atlas):
    dialog = AboutDialog(atlas, window)
    assert dialog.width() <= 1366 and dialog.height() <= 768
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["About",
                                                                          "Data sources"]
    assert dialog.sources.count() == len(atlas.sources)
    dialog.sources.setCurrentRow(0)
    first = next(iter(atlas.sources.values()))
    assert first.citation() in dialog.detail.text()


def test_disclaimer_shows_at_every_start_until_its_box_is_ticked(window, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    box = offer_disclaimer(window, settings)
    assert box.checkBox().text() == "Don't show this again" and not box.checkBox().isChecked()
    box.accept()
    assert disclaimer_due(settings)
    box = offer_disclaimer(window, settings)
    box.checkBox().setChecked(True)
    box.accept()
    assert not disclaimer_due(settings)
    assert offer_disclaimer(window, settings) is None


def test_the_old_shown_once_record_no_longer_hides_the_disclaimer(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("disclaimer_shown", True)
    assert disclaimer_due(settings)


def test_main_reports_missing_atlas(tmp_path, capsys):
    assert main(["--atlas", str(tmp_path / "missing")]) == 1
    assert "python -m tools.build_atlas" in capsys.readouterr().err


@pytest.mark.perf
def test_selection_updates_all_panels_under_7ms(window, timing):
    ids = list(window.state.geometry_ids)
    times = []
    for i in range(40):
        target = ids[i % len(ids)]
        if target == window.state.selected:
            continue
        start = time.perf_counter()
        window.state.select(target)
        times.append(time.perf_counter() - start)
    times.sort()
    timing.assert_within({"toy atlas: select a structure": (times[len(times) // 2], 0.007)})


def test_slices_draw_a_smooth_template_under_sharp_labels(window, qapp):
    qapp.processEvents()
    panel = window.slices
    assert panel.template_item.zValue() < panel.label_item.zValue()
    assert panel.template_item.smooth and not panel.label_item.smooth
    assert panel.layer.shape[2] == 4 and panel.image.shape[2] == 4


def test_view_uses_the_packages_stored_normals(window, atlas):
    normals = window.view.blocks[101].GetPointData().GetNormals()
    assert normals is not None
    assert normals.GetNumberOfTuples() == len(atlas.mesh(101).normals)
    assert window.view.chunks.actors[0].GetProperty().GetInterpolationAsString() == "Gouraud"


def test_selecting_a_concept_highlights_all_of_its_geometry(window):
    window.state.select(100)
    assert window.view.highlighted == [101, 102]
    window.state.select(111)
    assert window.view.highlighted == [111]


def test_group_toggle_sends_one_visibility_change(window):
    seen = []
    window.state.visibility_changed.connect(seen.append)
    window.tree.items[1].setCheckState(0, Qt.CheckState.Unchecked)
    assert seen == [frozenset(window.state.geometry_ids)]
    window.tree.items[1].setCheckState(0, Qt.CheckState.Checked)
    assert len(seen) == 2
    assert not any(window.state.is_hidden(i) for i in window.state.geometry_ids)


def test_check_marks_follow_the_state(window):
    window.state.set_hidden([101], True)
    assert window.tree.items[101].checkState(0) == Qt.CheckState.Unchecked
    assert window.tree.items[100].checkState(0) == Qt.CheckState.PartiallyChecked
    assert window.tree.items[1].checkState(0) == Qt.CheckState.PartiallyChecked
    window.state.show_all()
    assert window.tree.items[1].checkState(0) == Qt.CheckState.Checked


def test_slice_state_emits_once_and_validates(atlas):
    state = AppState(atlas)
    assert (state.slice_axis, state.slice_mm) == ("axial", 0.0)
    seen = []
    state.slice_changed.connect(lambda axis, mm: seen.append((axis, mm)))
    state.set_slice("coronal", 12)
    state.set_slice("coronal", 12.0)
    assert seen == [("coronal", 12.0)]
    with pytest.raises(ValueError, match="oblique"):
        state.set_slice("oblique", 0.0)


def test_one_composite_block_per_structure_with_geometry(window):
    assert window.view.chunks.block_count() == len(window.state.geometry_ids) == 5
    assert window.view.lod == 0


def test_hidden_structure_cannot_be_picked(window):
    x, y, sid = find_pixel(window.view)
    window.state.set_hidden([sid], True)
    assert window.view.structure_at(x, y) != sid


def test_nothing_is_picked_when_everything_is_hidden(window):
    x, y, _ = find_pixel(window.view)
    window.state.set_hidden(window.state.geometry_ids, True)
    assert window.view.structure_at(x, y) is None


def test_visibility_change_renders_once(window, qapp):
    before = window.view.render_count
    window.tree.items[100].setCheckState(0, Qt.CheckState.Unchecked)
    qapp.processEvents()
    assert window.view.render_count == before + 1


def test_highlight_overlay_skips_hidden_structures(window):
    window.state.set_hidden([101], True)
    window.state.select(100)
    assert window.view.highlighted == [101, 102]
    assert window.view.overlay_ids == [102]
    assert not window.view.outline.renderer.GetInteractive()
    window.state.set_hidden([101], False)
    assert window.view.overlay_ids == [101, 102]


def test_cutting_plane_follows_the_slice(window):
    window.state.set_slice("coronal", 12.0)
    ymin, ymax = window.view.plane.GetBounds()[2:4]
    assert abs(ymin - 12.0) < 1e-6 and abs(ymax - 12.0) < 1e-6
    window.state.set_slice("axial", -20.0)
    zmin, zmax = window.view.plane.GetBounds()[4:6]
    assert abs(zmin + 20.0) < 1e-6 and abs(zmax + 20.0) < 1e-6


def test_slice_panel_shapes_per_axis(window):
    panel = window.slices
    assert panel.image.shape == (48, 40, 4)
    panel.set_axis("coronal")
    assert window.state.slice_axis == "coronal" and panel.image.shape == (36, 40, 4)
    panel.set_axis("sagittal")
    assert panel.image.shape == (36, 48, 4)


def test_slider_moves_the_slice_and_the_3d_plane(window):
    window.slices.slider.setValue(20)
    assert window.state.slice_mm == -60.0 + 4 * 20
    zmin, zmax = window.view.plane.GetBounds()[4:6]
    assert abs(zmin - 20.0) < 1e-6 and abs(zmax - 20.0) < 1e-6
    assert window.slices.position.text() == "z = +20 mm"


def test_hover_and_click_select_the_structure_under_the_cursor(window):
    window.state.set_slice("axial", 20.0)
    assert window.slices.name_at_pixel(19, 12) == "Alpha gyrus (left)"
    window.slices.click_pixel(19, 12)
    assert window.state.selected == 101


def test_click_on_unlabelled_tissue_keeps_the_selection(window):
    window.state.select(111)
    window.slices.click_pixel(0, 0)
    assert window.state.selected == 111
    assert window.slices.name_at_pixel(0, 0) == ""
    assert window.slices.name_at_pixel(500, 500) == ""


def test_selecting_a_hidden_structure_draws_nothing_new(window, qapp):
    window.state.set_slice("axial", 20.0)
    window.state.set_hidden([101], True)
    qapp.processEvents()
    before = window.slices.image.copy()
    window.state.select(101)
    qapp.processEvents()
    assert (window.slices.image == before).all()
    pixel = window.slices.image[19, 12]
    assert pixel[0] == pixel[1] == pixel[2]


def test_out_of_range_slice_is_clamped(window):
    window.state.set_slice("axial", 500.0)
    assert window.slices.slider.value() == 35
    assert window.state.slice_mm == -60.0 + 4 * 35


def test_centre_on_selection(window):
    window.state.select(120)
    window.slices.centre_on_selection()
    assert window.state.slice_mm == -60.0 + 4 * 8


def test_centre_shortcut_and_hover_status(window):
    shortcuts = {a.shortcut().toString() for a in window.findChildren(QAction)}
    assert "C" in shortcuts
    window.slices.hovered.emit("Alpha gyrus (left)")
    assert window.statusBar().currentMessage() == "Alpha gyrus (left)"


def test_slice_panel_without_template(qapp, tmp_path):
    volume = np.zeros((10, 10, 10), dtype=np.uint16)
    volume[2:4, 2:4, 2:4] = 101
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(0), 102: tetra(5), 110: tetra(9)}, volume=volume)
    panel = SlicePanel(AppState(Atlas.open(root)))
    assert panel.note.text() == NO_TEMPLATE
    assert tuple(panel.image[0, 0]) == (0, 0, 0, 255)


def test_non_ras_volume_disables_slices_instead_of_crashing(qapp, tmp_path):
    volume = np.zeros((10, 10, 10), dtype=np.uint16)
    volume[2:4, 2:4, 2:4] = 101
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(0), 102: tetra(5), 110: tetra(9)}, volume=volume,
                         affine=np.diag([-1.0, 1.0, 1.0, 1.0]))
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    assert window.slices.note.text() == NOT_RAS
    assert not window.slices.isEnabled()
    window.close()


def plane_extent(view):
    xmin, xmax, ymin, ymax, _, _ = view.plane.GetBounds()
    return xmax - xmin, ymax - ymin


def test_plane_keeps_the_volume_extent_when_structures_are_isolated(window):
    full = plane_extent(window.view)
    window.state.isolate(111)
    window.state.set_slice("axial", -8.0)
    assert plane_extent(window.view) == pytest.approx(full)


def test_plane_returns_after_hiding_and_showing_everything(window):
    window.state.set_hidden(window.state.geometry_ids, True)
    window.state.set_slice("axial", -8.0)
    window.state.show_all()
    assert window.view.plane.GetVisibility()
    assert window.view.plane.GetBounds()[4] == pytest.approx(-8.0)


def test_hidden_structures_cannot_be_named_or_selected_in_slices(window):
    window.state.set_slice("axial", 20.0)
    window.state.select(111)
    window.state.set_hidden([101], True)
    assert window.slices.name_at_pixel(19, 12) == ""
    window.slices.click_pixel(19, 12)
    assert window.state.selected == 111


def test_about_text_credits_the_template_source(atlas):
    assert "toy-template" in atlas.sources
    assert any("Toy template" in row for row in about_rows(atlas))


def start_quiz(window, mode, practice=False, level="structures", scope=None):
    window.start_quiz(QuizChoice(mode, level, scope, practice), rng=random.Random(1))
    return window.quiz


@pytest.mark.parametrize("mode", ["name-typed", "name-choice"])
def test_naming_quizzes_fade_all_but_the_asked_structure(window, mode):
    quiz = start_quiz(window, mode)
    assert window.state.focus == frozenset(quiz.item.geometry)
    quiz.stop()
    assert window.state.focus is None


def test_flashcards_fade_all_but_the_asked_structure(reviewed_window):
    quiz = start_quiz(reviewed_window, "flashcard")
    assert reviewed_window.state.focus == frozenset(quiz.item.geometry)
    quiz.stop()
    assert reviewed_window.state.focus is None


def test_find_it_does_not_fade(window):
    quiz = start_quiz(window, "find")
    assert window.state.focus is None
    quiz.stop()


def test_the_summary_screen_ends_the_fade(window):
    quiz = start_quiz(window, "name-typed")
    while quiz.item is not None:
        quiz.submit_text(quiz.item.name)
        quiz.go_on()
    assert quiz.phase == "summary" and window.state.focus is None
    quiz.stop()


def test_quiz_mode_hides_giveaways_and_restores_the_window(window):
    window.state.set_hidden([102], True)
    window.state.select(111)
    window.state.set_slice("axial", 20.0)
    window.enter_quiz()
    assert not window.tree_dock.isVisible() and not window.info_dock.isVisible()
    assert window.quiz_dock.isVisible()
    assert not window.state.is_hidden(102)
    assert not window.shortcuts["Hide"].isEnabled()
    window.slices.hovered.emit("Alpha gyrus (left)")
    assert window.statusBar().currentMessage() == ""
    window.state.select(101)
    window._update_status()
    assert "Alpha" not in window.status.text()
    window.state.set_slice("coronal", 0.0)
    window.leave_quiz()
    assert window.tree_dock.isVisible() and window.info_dock.isVisible()
    assert not window.quiz_dock.isVisible()
    assert window.state.is_hidden(102) and window.state.selected == 111
    assert (window.state.slice_axis, window.state.slice_mm) == ("axial", 20.0)
    assert window.shortcuts["Hide"].isEnabled()


def test_name_it_typed_round_records_progress(window):
    quiz = start_quiz(window, "name-typed")
    assert window.quiz_active and quiz.item.id == 100 and window.state.selected == 100
    assert "Alpha" not in quiz.prompt.text()
    quiz.submit_text("ALPHA GYRUS")
    assert quiz.phase == "feedback" and "Correct" in quiz.feedback.text()
    quiz.go_on()
    assert window.progress_store().card(100, "name-typed") is not None
    assert quiz.item.id == 110
    quiz.submit_text("Gamma body")
    assert "Wrong" in quiz.feedback.text() and "Beta nucleus" in quiz.feedback.text()


def test_a_typo_is_accepted_and_shown(window):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text("alpha gyruss")
    assert "Correct" in quiz.feedback.text() and "You typed" in quiz.feedback.text()


def test_enter_in_the_answer_box_shows_feedback_before_moving_on(window):
    quiz = start_quiz(window, "name-typed")
    QTest.keyClicks(quiz.answer_box, "alpha gyrus")
    QTest.keyClick(quiz.answer_box, Qt.Key.Key_Return)
    assert quiz.phase == "feedback" and quiz.item.id == 100
    QTest.keyClick(quiz, Qt.Key.Key_E)
    assert quiz.item.id == 110
    assert window.progress_store().card(100, "name-typed").state == State.Review


def test_multiple_choice_with_number_keys(window):
    quiz = start_quiz(window, "name-choice")
    assert len([b for b in quiz.choice_buttons if b.isVisible()]) == 3
    right = next(n for n, option in enumerate(quiz.options) if option.id == quiz.item.id)
    keys = [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4]
    QTest.keyClick(quiz, keys[right])
    assert "Correct" in quiz.feedback.text()


def test_clicking_during_name_it_keeps_the_question_highlighted(window, qapp):
    start_quiz(window, "name-typed")
    window.state.select(111)
    qapp.processEvents()
    assert window.state.selected == 100


def test_escape_after_answering_saves_the_answer_and_leaves(window):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text("Alpha gyrus")
    QTest.keyClick(quiz, Qt.Key.Key_Escape)
    assert not window.quiz_active
    assert window.progress_store().review_count("name-typed") == 1


def test_escape_in_the_answer_box_leaves_without_saving(window):
    quiz = start_quiz(window, "name-typed")
    QTest.keyClick(quiz.answer_box, Qt.Key.Key_Escape)
    assert not window.quiz_active
    assert window.progress_store().review_count("name-typed") == 0


def test_finishing_shows_a_summary_and_closes(window):
    quiz = start_quiz(window, "name-typed")
    while quiz.phase == "asking":
        quiz.submit_text(quiz.item.name)
        quiz.go_on(Rating.Easy)
    assert quiz.phase == "summary"
    assert "3 answered, 100% correct" in quiz.prompt.text()
    assert window.state.selected is None
    QTest.keyClick(quiz, Qt.Key.Key_Return)
    assert not window.quiz_active and window.tree_dock.isVisible()


def test_practice_saves_nothing(window):
    quiz = start_quiz(window, "name-typed", practice=True)
    quiz.submit_text(quiz.item.name)
    quiz.go_on()
    assert window.progress_store().review_count("name-typed") == 0


def test_a_damaged_progress_file_is_reported(window):
    window.progress_path.write_bytes(b"garbage" * 200)
    window.progress_store()
    assert ".broken-" in window.recovery_box.text()


def find_slice_pixel(panel, wanted):
    rows, cols = panel.image.shape[:2]
    for row in range(rows):
        for col in range(cols):
            if panel.structure_at_pixel(row, col) in wanted:
                return row, col
    raise AssertionError("no matching slice pixel")


@pytest.fixture
def reviewed_window(qapp, toy_atlas, tmp_path):
    root = shutil.copytree(toy_atlas, tmp_path / "atlas")
    path = root / "knowledge" / "en" / "100.md"
    path.write_text(path.read_text().replace('status = "draft"', 'status = "reviewed"'))
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def test_find_it_by_clicking_in_3d(window, qapp):
    quiz = start_quiz(window, "find")
    assert quiz.item.id == 100 and window.state.selected is None
    assert "Alpha gyrus" in quiz.prompt.text()
    x, y, _ = find_pixel(window.view, lambda sid: sid in (101, 102))
    window.view.pick_at(x, y)
    qapp.processEvents()
    assert quiz.phase == "feedback" and "Correct" in quiz.feedback.text()
    assert window.state.selected == 100


def test_find_it_wrong_click_in_the_slice_names_what_was_clicked(window, qapp):
    quiz = start_quiz(window, "find")
    window.state.set_slice("axial", -12.0)
    row, col = find_slice_pixel(window.slices, {111, 112})
    window.slices.click_pixel(row, col)
    qapp.processEvents()
    assert "Wrong" in quiz.feedback.text() and "You clicked: Beta nucleus." in quiz.feedback.text()
    assert window.state.selected == 100


def test_flashcards_use_reviewed_descriptions(reviewed_window):
    window = reviewed_window
    quiz = start_quiz(window, "flashcard")
    assert quiz.item.id == 100 and quiz.session.remaining() == 0
    assert "Alpha gyrus" in quiz.prompt.text() and not quiz.back.isVisible()
    QTest.keyClick(quiz, Qt.Key.Key_Space)
    assert quiz.phase == "revealed" and "Does alpha things" in quiz.back.toPlainText()
    QTest.keyClick(quiz, Qt.Key.Key_4)
    assert quiz.phase == "summary"
    assert window.progress_store().card(100, "flashcard").state == State.Review


def ok_button(dialog):
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def test_setup_starts_a_typed_quiz_by_default(window):
    dialog = window.open_quiz_setup()
    assert dialog.note.text() == "0 due, 3 new" and ok_button(dialog).isEnabled()
    dialog.accept()
    assert window.quiz_active and window.quiz.mode == "name-typed"


def test_setup_explains_when_there_is_nothing_to_ask(window):
    dialog = window.open_quiz_setup()
    dialog.level.setCurrentIndex(1)
    assert dialog.note.text() == NO_ITEMS and not ok_button(dialog).isEnabled()
    dialog.level.setCurrentIndex(0)
    dialog.mode.setCurrentIndex(2)
    assert dialog.note.text() == NO_REVIEWED and not ok_button(dialog).isEnabled()
    dialog.mode.setCurrentIndex(1)
    assert not dialog.answer_style.isEnabled()
    dialog.reject()


def test_setup_offers_practice_when_nothing_is_due(window):
    quiz = start_quiz(window, "name-typed")
    while quiz.phase == "asking":
        quiz.submit_text(quiz.item.name)
        quiz.go_on(Rating.Easy)
    quiz.stop()
    dialog = window.open_quiz_setup()
    assert dialog.note.text() == NOTHING_DUE and not ok_button(dialog).isEnabled()
    dialog.session.setCurrentIndex(1)
    assert ok_button(dialog).isEnabled()
    dialog.reject()


def test_start_quiz_is_disabled_during_a_quiz(window):
    assert window.shortcuts["Start quiz"].isEnabled()
    start_quiz(window, "name-typed")
    assert not window.shortcuts["Start quiz"].isEnabled()
    window.quiz.stop()
    assert window.shortcuts["Start quiz"].isEnabled()


def test_progress_window_counts_reviews(window):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text(quiz.item.name)
    quiz.go_on(Rating.Easy)
    quiz.stop()
    dialog = window.show_progress()
    cells = [dialog.table.item(0, column).text() for column in range(7)]
    due = window.progress_store().card(100, "name-typed").due
    week_end = day_start(datetime.now(UTC), 7)
    in_week = "1" if due < week_end else "0"
    assert cells == ["Name it (typed)", "Structures", "2", "0", "1", "0", in_week]
    assert dialog.weakest.count() == 1 and "Alpha gyrus" in dialog.weakest.item(0).text()
    dialog.reject()


def test_the_activity_chart_stays_hidden_through_a_quiz_without_a_route(window):
    assert not window.chart_dock.isVisible()
    start_quiz(window, "name-typed")
    assert not window.chart_dock.isVisible()
    window.quiz.stop()
    assert not window.chart_dock.isVisible()


def test_quiz_keys_still_work_after_clicking_the_3d_view_and_the_slice(window, qapp):
    policy = window.view.focusPolicy()
    quiz = start_quiz(window, "name-typed")
    QTest.mouseClick(window.view, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.keyClicks(qapp.focusWidget(), "alpha gyrus")
    QTest.keyClick(qapp.focusWidget(), Qt.Key.Key_Return)
    assert quiz.phase == "feedback"
    QTest.mouseClick(window.slices.view, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.keyClick(qapp.focusWidget(), Qt.Key.Key_Escape)
    assert not window.quiz_active
    assert window.view.focusPolicy() == policy


def test_set_slice_rejects_positions_that_are_not_finite(atlas):
    state = AppState(atlas)
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            state.set_slice("axial", bad)


def test_centre_on_selection_moves_the_slice_once(qapp, tmp_path):
    volume = np.zeros((6, 6, 6), dtype=np.uint16)
    volume[1:3, 2, 2] = 101
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(0), 102: tetra(5), 110: tetra(9)}, volume=volume)
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    window.state.set_slice("sagittal", 5.0)
    window.state.select(101)
    seen = []
    window.state.slice_changed.connect(lambda axis, mm: seen.append(mm))
    window.slices.centre_on_selection()
    assert len(seen) == 1 and seen[0] in (1.0, 2.0)
    window.close()


def test_a_tree_check_refreshes_the_marks_once(window, monkeypatch):
    calls = []
    original = window.tree._sync_checks
    monkeypatch.setattr(window.tree, "_sync_checks", lambda *a: (calls.append(1), original(*a)))
    window.tree.items[100].setCheckState(0, Qt.CheckState.Unchecked)
    assert len(calls) == 1
    assert window.state.is_hidden(101)


def test_clicking_the_current_axis_keeps_the_position(window):
    window.state.set_slice("axial", 20.0)
    window.slices.set_axis("axial")
    assert window.state.slice_mm == 20.0


def test_no_cutting_plane_without_a_labelled_volume(qapp, tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(0), 102: tetra(5), 110: tetra(9)})
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    assert not window.view.plane.GetVisibility()
    window.state.set_slice("coronal", 3.0)
    assert not window.view.plane.GetVisibility()
    window.close()


def test_the_dock_menu_cannot_reveal_answers_during_a_quiz(window):
    docks = (window.tree_dock, window.info_dock)
    start_quiz(window, "name-typed")
    assert not any(dock.toggleViewAction().isEnabled() for dock in docks)
    assert not window.chart_dock.toggleViewAction().isEnabled()
    window.quiz.stop()
    assert all(dock.toggleViewAction().isEnabled() for dock in docks)
    assert not window.chart_dock.toggleViewAction().isEnabled()


def test_the_highlight_stays_on_the_answer_during_feedback(window, qapp):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text("Alpha gyrus")
    window.state.select(111)
    qapp.processEvents()
    assert window.state.selected == 100


def test_the_question_highlight_reaches_late_listeners_last(window, qapp):
    start_quiz(window, "name-typed")
    seen = []
    window.state.selection_changed.connect(seen.append)
    window.state.select(111)
    qapp.processEvents()
    assert seen[-1] == 100 and window.state.selected == 100


def test_every_step_works_with_the_mouse(reviewed_window):
    window = reviewed_window
    quiz = start_quiz(window, "flashcard")
    assert quiz.reveal_button.isVisible()
    quiz.reveal_button.click()
    assert quiz.phase == "revealed" and all(b.isVisible() for b in quiz.rate_buttons)
    quiz.rate_buttons[3].click()
    assert quiz.phase == "summary" and quiz.next_button.text() == "Close"
    quiz.next_button.click()
    assert not window.quiz_active


def test_next_button_moves_on_after_feedback(window):
    quiz = start_quiz(window, "name-choice")
    assert not quiz.next_button.isVisible()
    quiz.choice_buttons[0].click()
    assert quiz.phase == "feedback" and quiz.next_button.isVisible()
    quiz.next_button.click()
    assert quiz.phase == "asking" and quiz.item.id == 110


def test_a_progress_file_from_a_newer_version_is_named_as_such(window):
    db = sqlite3.connect(window.progress_path)
    db.execute("PRAGMA user_version = 2")
    db.close()
    window.progress_store()
    assert "newer version" in window.recovery_box.text()


def test_a_failed_save_keeps_the_answer_on_screen(window, monkeypatch):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text("Alpha gyrus")

    def broken(*args):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(window.progress_store(), "record", broken)
    quiz.go_on()
    assert quiz.phase == "feedback" and "Could not save" in quiz.hint.text()
    monkeypatch.undo()
    quiz.go_on()
    assert quiz.item.id == 110


def test_the_app_is_called_mnemosyn(window, atlas):
    assert window.windowTitle().startswith("Mnemosyn - ")
    assert "<h3>Mnemosyn</h3>" in about_text(atlas)


def test_progress_moves_from_the_old_folder(tmp_path):
    old = tmp_path / "cns-atlas"
    old.mkdir()
    (old / "progress.sqlite").write_bytes(b"cards")
    (old / "progress.sqlite-wal").write_bytes(b"log")
    migrate_progress(tmp_path)
    path = default_progress_path(tmp_path)
    assert path.read_bytes() == b"cards"
    assert (tmp_path / "mnemosyn" / "progress.sqlite-wal").read_bytes() == b"log"
    assert not (old / "progress.sqlite").exists()


def test_progress_is_never_moved_over_an_existing_file(tmp_path):
    for folder, payload in (("cns-atlas", b"old"), ("mnemosyn", b"new")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "progress.sqlite").write_bytes(payload)
    migrate_progress(tmp_path)
    assert default_progress_path(tmp_path).read_bytes() == b"new"
    assert (tmp_path / "cns-atlas" / "progress.sqlite").read_bytes() == b"old"


def test_finding_the_progress_path_moves_nothing(tmp_path):
    (tmp_path / "cns-atlas").mkdir()
    (tmp_path / "cns-atlas" / "progress.sqlite").write_bytes(b"cards")
    assert default_progress_path(tmp_path) == tmp_path / "mnemosyn" / "progress.sqlite"
    assert (tmp_path / "cns-atlas" / "progress.sqlite").exists()


def test_a_failed_progress_move_does_not_stop_the_app(tmp_path):
    (tmp_path / "cns-atlas").mkdir()
    (tmp_path / "cns-atlas" / "progress.sqlite").write_bytes(b"cards")
    (tmp_path / "mnemosyn").write_bytes(b"a file where the folder should be")
    migrate_progress(tmp_path)
    assert (tmp_path / "cns-atlas" / "progress.sqlite").read_bytes() == b"cards"


def test_find_it_moves_the_slice_to_the_answer_after_a_wrong_click(window, qapp):
    start_quiz(window, "find")
    window.state.set_slice("axial", -12.0)
    row, col = find_slice_pixel(window.slices, {111, 112})
    window.slices.click_pixel(row, col)
    qapp.processEvents()
    assert window.state.selected == 100 and window.state.slice_mm == 20.0


def test_a_failed_save_when_leaving_keeps_the_quiz_open(window, monkeypatch):
    quiz = start_quiz(window, "name-typed")
    quiz.submit_text("Alpha gyrus")

    def broken(*args):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(window.progress_store(), "record", broken)
    QTest.keyClick(quiz, Qt.Key.Key_Escape)
    assert window.quiz_active and "Could not save" in quiz.hint.text()
    monkeypatch.undo()
    QTest.keyClick(quiz, Qt.Key.Key_Escape)
    assert not window.quiz_active
    assert window.progress_store().review_count("name-typed") == 1


def test_a_failed_flashcard_save_asks_to_rate_again(reviewed_window, monkeypatch):
    quiz = start_quiz(reviewed_window, "flashcard")
    quiz.reveal()

    def broken(*args):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(reviewed_window.progress_store(), "record", broken)
    quiz.rate(3)
    assert quiz.phase == "revealed" and "rate it again" in quiz.hint.text()


def test_own_memory_leaves_out_shared_library_pages():
    own, peak = own_memory_mb(), peak_memory_mb()
    assert own is not None and peak is not None
    assert 0 < own < peak


LOCAL_SOURCE = Source("toylocal", "Toy gland", "Test E", 2024, "1", "No licence stated", False)


def local_atlas(tmp_path):
    root = write_package(tmp_path / "local", tiny_structures(), meshes={101: tetra()},
                         sources=[TOY_SOURCE, LOCAL_SOURCE])
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["local_only"] = ["toylocal"]
    (root / "metadata.json").write_text(json.dumps(metadata))
    return Atlas.open(root)


def test_a_local_build_says_it_is_not_for_sharing(qapp, tmp_path):
    atlas = local_atlas(tmp_path)
    assert "may not be shared yet" in about_text(atlas)
    assert any(" - local only - " in row for row in about_rows(atlas))
    w = MainWindow(atlas, progress_path=tmp_path / "progress.sqlite")
    assert w.windowTitle().endswith("(local build, not for sharing)")
    w.close()


def test_a_shareable_build_has_no_local_notice(window, atlas):
    assert "not for sharing" not in window.windowTitle()
    assert "may not be shared" not in about_text(atlas)


def test_the_about_box_lists_local_sources_without_a_citation(tmp_path):
    root = write_package(tmp_path / "ghost", tiny_structures())
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["local_only"] = ["ghost-source"]
    (root / "metadata.json").write_text(json.dumps(metadata))
    assert "ghost-source" in about_text(Atlas.open(root))


def test_the_activity_chart_keeps_its_axes_between_selections(window):
    box = window.chart.plot.getViewBox()
    window.state.select(101)
    QApplication.processEvents()
    before = box.viewRange()
    window.state.select(110)
    QApplication.processEvents()
    assert box.viewRange() == before


def test_hiding_one_structure_updates_only_its_branch_of_the_tree(window, monkeypatch):
    state = window.state
    calls = []
    real = state.geometry_in
    monkeypatch.setattr(state, "geometry_in", lambda i: calls.append(i) or real(i))
    state.set_hidden([101], True)
    assert set(calls) <= set(state.atlas.ancestors(101)) | {101}
    assert window.tree.items[101].checkState(0) == Qt.CheckState.Unchecked
    assert window.tree.items[100].checkState(0) == Qt.CheckState.PartiallyChecked


def test_about_rows_keep_full_surnames_and_show_local_tags_early():
    from cns_atlas.model import Source
    from cns_desktop.views.about_dialog import source_row

    source = Source("pam50", "PAM50", "De Leener B, Fonov VS", 2018, "1",
                    "No licence stated; local use only until the authors allow sharing",
                    False, provides="Spinal cord segments")
    assert source_row(source, True).startswith("Spinal cord segments - De Leener et al. 2018"
                                               " - local only - ")


def test_the_about_tab_shows_the_app_version(atlas):
    from cns_desktop.views.about_dialog import app_version

    assert f"Version {app_version()}" in about_text(atlas)


def test_the_status_bar_shows_the_selection_and_the_right_hint_only(window):
    window.state.select(101)
    window._update_status()
    text = window.status.text()
    assert "Alpha gyrus (left)" in text and "right-drag pans" in text and "wheel zooms" in text
    assert "F frames" in text
    assert not any(word in text for word in ("frame:", "visible", "GPU", "zoom ·"))
    labels = [w.text() for w in window.statusBar().findChildren(QLabel)]
    assert not any(t.startswith("GPU") for t in labels)


def test_the_info_panel_names_the_side_but_not_the_drawing_kind(window):
    kind = window.state.atlas.get(101).kind
    line = window.info.html_for(101).split("</h2>")[1].split("</p>")[0]
    assert "left" in line and kind not in line
    assert "midline" not in window.info.html_for(120).split("</h2>")[1].split("</p>")[0]


def test_the_structures_panel_opens_wide_enough_for_common_names(window, qapp):
    qapp.processEvents()
    assert window.tree_dock.width() >= 310 and window.view.width() >= 400


def test_tree_items_show_their_full_name_on_hover(window):
    item = window.tree.items[101]
    assert item.toolTip(0) == window.state.atlas.get(101).name
    assert window.tree.tree.indentation() <= 12


def test_f_frames_3d_when_there_are_no_slices(qapp, tmp_path, monkeypatch):
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(0), 102: tetra(5), 110: tetra(9)})
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    monkeypatch.setattr(window.slices.view, "underMouse", lambda: True)
    called = []
    monkeypatch.setattr(window.view, "frame_selection", lambda: called.append(1))
    window.frame()
    assert called == [1]
    window.close()


def test_the_colour_swatch_sits_beside_the_name(window):
    for structure_id in (101, 120):
        heading, rest = window.info.html_for(structure_id).split("</h2>", 1)
        assert "&#9632;" in heading and "&#9632;" not in rest
    assert window.info.html_for(101).split("</h2>", 1)[1].startswith("<p>left</p>")
    assert not window.info.html_for(120).split("</h2>", 1)[1].startswith("<p></p>")
