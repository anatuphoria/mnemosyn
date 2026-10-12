import random

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from atlas_package import tetra, tiny_structures, write_package
from cns_atlas import Atlas, Pathway, Station
from cns_desktop.main_window import MainWindow
from cns_desktop.views.brain_view import FAINT
from cns_study.session import QuizChoice

LEFT_ROUTE = {101, 152, 112, 120}
RIGHT_ROUTE = {102, 151, 111, 120}
LABELS = ["1 Alpha gyrus (left)", "2 ✕ Toy crossing", "3 Long tract (right)",
          "4 Beta nucleus (right)", "5 Toy relay (right)", "6 Gamma body (midline)"]


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
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    yield w
    w.close()


def enter(window, key="loop", side="left"):
    window.pathways.open(key, side)
    return window.pathways


def hidden_ids(state) -> set[int]:
    return {i for i in state.geometry_ids if state.is_hidden(i)}


def test_the_dock_lists_the_pathways(window):
    choices = window.pathways.choices
    assert [choices.item(i).text() for i in range(choices.count())] == [
        "Sensory and motor", "Toy loop", "Short path"]
    assert window.pathways.empty.isHidden()


def test_an_atlas_without_pathways_says_so(qapp, toy_tract_atlas, tmp_path):
    w = open_window(qapp, toy_tract_atlas, tmp_path)
    assert w.pathways.choices.count() == 0 and not w.pathways.empty.isHidden()
    w.close()


def test_clicking_a_pathway_in_the_list_enters_it(window):
    window.pathways.choices.itemClicked.emit(window.pathways.choices.item(1))
    assert window.pathway_active and window.pathways.pathway.key == "loop"
    assert window.pathways.pages.currentIndex() == 1


def test_entering_fades_everything_off_the_route_on_the_chosen_side(window):
    enter(window)
    state, view = window.state, window.view
    assert state.focus == LEFT_ROUTE
    assert view.attributes.GetBlockOpacity(view.blocks[102]) == pytest.approx(FAINT)
    assert view.attributes.GetBlockOpacity(view.blocks[101]) == 1.0
    assert not state.is_hidden(152) and state.is_hidden(151) and state.is_hidden(160)
    assert state.selected == 101 and state.emphasis == (101,) and view.overlay_ids == [101]
    for name in ("Hide", "Isolate", "Show all", "Tracts"):
        assert not window.shortcuts[name].isEnabled()
    assert window.shortcuts["Leave pathway"].isEnabled()


def test_steps_are_labelled_with_their_resolved_sides(window):
    panel = enter(window)
    assert [panel.steps.item(i).text() for i in range(panel.steps.count())] == LABELS
    assert panel.start.text() == "Start: left alpha gyrus"
    assert not panel.draft.isHidden()


def test_stepping_lights_the_station_and_moves_the_slice(window):
    panel = enter(window)
    window.state.set_slice("axial", 20.0)
    panel.go(3)
    assert window.state.emphasis == (112,) and window.view.overlay_ids == [112]
    assert window.state.slice_mm == -12.0
    assert "Reaches the right beta nucleus." in panel.details.toPlainText()
    assert panel.steps.currentRow() == 3


def test_crossings_and_relays_light_nothing_and_keep_the_slice(window):
    panel = enter(window)
    panel.go(3)
    for index in (4, 1):
        panel.go(index)
        assert window.state.selected is None and window.state.emphasis == ()
        assert window.view.overlay_ids == [] and window.state.slice_mm == -12.0


def test_next_back_and_the_arrow_keys_stay_inside_the_route(window):
    panel = enter(window)
    panel.back()
    assert panel.index == 0 and not window.chart.back_button.isEnabled()
    QTest.keyClick(panel, Qt.Key.Key_Right)
    QTest.keyClick(panel, Qt.Key.Key_Right)
    assert panel.index == 2
    QTest.keyClick(panel, Qt.Key.Key_Left)
    assert panel.index == 1
    panel.go(99)
    assert panel.index == 5 and not window.chart.next_button.isEnabled()
    panel.next()
    assert panel.index == 5


def test_the_side_switch_moves_the_lights_and_the_texts(window):
    panel = enter(window)
    panel.go(3)
    panel.side_buttons["right"].click()
    assert window.state.focus == RIGHT_ROUTE and panel.index == 3
    assert window.state.emphasis == (111,)
    assert not window.state.is_hidden(151) and window.state.is_hidden(152)
    assert panel.steps.item(0).text() == "1 Alpha gyrus (right)"
    assert "Reaches the left beta nucleus." in panel.details.toPlainText()


def test_clicking_a_step_or_a_route_structure_jumps_to_it(window):
    panel = enter(window)
    panel.steps.setCurrentRow(2)
    assert panel.index == 2 and window.state.emphasis == (152,)
    window.state.select(112)
    assert panel.index == 3 and window.state.emphasis == (112,)
    assert window.state.selected == 112


def test_selecting_off_the_route_keeps_the_step(window):
    panel = enter(window)
    panel.go(3)
    window.state.select(131)
    assert panel.index == 3 and window.state.selected == 131
    assert window.state.emphasis == () and window.view.overlay_ids == [131]


def test_slices_show_only_the_route(window):
    window.state.set_slice("axial", 20.0)
    assert window.slices.structure_at_pixel(19, 28) == 102
    enter(window)
    window.state.set_slice("axial", 20.0)
    assert window.slices.structure_at_pixel(19, 28) is None
    assert window.slices.structure_at_pixel(19, 12) == 101


def test_leaving_restores_visibility_selection_slice_and_opacity(window):
    state, view = window.state, window.view
    state.set_hidden([131, 101], True)
    state.select(132)
    state.set_slice("coronal", 8.0)
    hidden = hidden_ids(state)
    panel = enter(window)
    assert not state.is_hidden(101)
    panel.go(3)
    panel.set_side("right")
    QTest.keyClick(panel, Qt.Key.Key_Escape)
    assert not window.pathway_active and panel.pages.currentIndex() == 0
    assert state.focus is None and state.emphasis == ()
    assert hidden_ids(state) == hidden
    assert state.selected == 132 and (state.slice_axis, state.slice_mm) == ("coronal", 8.0)
    assert not view.attributes.HasBlockOpacities()
    assert window.shortcuts["Hide"].isEnabled()
    assert not window.shortcuts["Leave pathway"].isEnabled()


def test_switching_pathways_keeps_the_first_saved_state(window):
    state = window.state
    state.select(132)
    hidden = hidden_ids(state)
    enter(window, "loop")
    panel = enter(window, "short", "right")
    assert state.focus == {112} and state.emphasis == (112,)
    assert panel.draft.isHidden()
    panel.leave()
    assert state.selected == 132 and state.focus is None and hidden_ids(state) == hidden


def test_a_quiz_leaves_pathway_mode_first(window):
    state = window.state
    state.select(132)
    enter(window)
    window.start_quiz(QuizChoice("name-typed", "structures", None, False),
                      rng=random.Random(1))
    assert not window.pathway_active and state.focus is None and window.quiz_active
    assert not window.pathway_dock.toggleViewAction().isEnabled()
    window.quiz.stop()
    assert state.selected == 132 and window.pathway_dock.toggleViewAction().isEnabled()


def test_the_status_bar_names_the_pathway_and_the_step(window):
    panel = enter(window)
    panel.go(2)
    window._update_status()
    assert "pathway: Toy loop (left)" in window.status.text()
    assert "step 3 of 6" in window.status.text()


def test_a_pathway_without_a_description_still_steps(qapp, tmp_path):
    route = Pathway("bare", "Bare route", "alpha gyrus", (Station((100,)), Station((110,))))
    root = write_package(tmp_path / "pkg", tiny_structures(),
                         meshes={101: tetra(), 102: tetra(20.0), 110: tetra(40.0)},
                         pathways=[route])
    w = open_window(qapp, root, tmp_path)
    w.pathways.open("bare")
    w.pathways.next()
    assert w.state.emphasis == (110,)
    assert "No description yet." in w.pathways.details.toPlainText()
    assert w.pathways.draft.isHidden()
    w.close()


def test_showing_the_dock_prepares_the_slice_centres(window, qapp):
    window.pathway_dock.raise_()
    qapp.processEvents()
    assert window.slices._centres is not None


def test_entering_switching_side_and_stepping_draw_the_3d_view_once(window):
    view, panel = window.view, window.pathways
    before = view.render_count
    enter(window)
    assert view.render_count == before + 1
    before = view.render_count
    panel.set_side("right")
    assert view.render_count == before + 1
    before = view.render_count
    panel.go(3)
    assert view.render_count == before + 1


def test_clicking_the_current_step_brings_its_station_back(window):
    panel = enter(window)
    panel.go(3)
    window.state.select(131)
    panel.steps.itemClicked.emit(panel.steps.item(3))
    assert window.state.emphasis == (112,) and window.state.selected == 112


def test_showing_the_dock_builds_the_tracts_before_the_first_entry(window, qapp):
    assert window.view.tract_builds == 0
    window.pathway_dock.raise_()
    qapp.processEvents()
    assert window.view.tract_builds == 1


def test_enter_on_the_list_opens_a_pathway(window):
    choices = window.pathways.choices
    choices.setCurrentRow(1)
    choices.setFocus()
    QTest.keyClick(choices, Qt.Key.Key_Return)
    assert window.pathway_active and window.pathways.pathway.key == "loop"


def test_leaving_draws_the_3d_view_once(window):
    enter(window)
    before = window.view.render_count
    window.pathways.leave()
    assert window.view.render_count == before + 1



def test_the_pathway_page_keeps_only_the_leave_button(window):
    panel = enter(window)
    assert not hasattr(panel, "back_button") and not hasattr(panel, "next_button")
    assert panel.leave_button.text() == "Leave pathway (Esc)"
    assert window.chart.back_button.isEnabled() is False
    panel.go(2)
    assert window.chart.back_button.isEnabled() and window.chart.next_button.isEnabled()
