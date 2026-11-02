import pytest
from PySide6.QtWidgets import QApplication

from pathway_helpers import open_window


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    w.workspaces.switch("Pathways")
    qapp.processEvents()
    yield w
    w.close()


def test_the_step_tab_explains_the_current_step(window):
    panel = window.pathways
    panel.open("loop")
    panel.go(1)
    step = window.step_panel
    assert window.step_group.current() == "step"
    assert step.heading.text() == f"STEP 2 OF {len(panel.pathway.steps)}"
    assert step.name.text() == "✕ Toy crossing"
    text = step.details.toPlainText()
    assert "Role" in text and text.count("personal study project") == 1


def test_without_a_route_the_step_tab_says_how_to_start(window):
    assert "Pick a route" in window.step_panel.details.toPlainText()
    window.pathways.open("loop")
    window.pathways.leave()
    assert "Pick a route" in window.step_panel.details.toPlainText()


def test_info_and_slices_join_the_step_group(window):
    assert window.step_group.keys() == ["step", "info", "slices"]
    window.workspaces.switch("Explore")
    assert not window.step_group.isVisible()


def test_clicking_a_structure_off_the_route_keeps_the_step_tab(window):
    window.pathways.open("loop")
    off = next(i for i in window.state.geometry_ids if i not in window.pathways.route)
    window.state.select(off)
    assert window.pathways.pathway is not None and window.step_group.current() == "step"


def test_a_second_route_replaces_the_first_and_closing_restores_the_start(window):
    state = window.state
    hidden = sorted(i for i in state.geometry_ids if state.is_hidden(i))
    window.pathways.open("loop")
    window.pathways.go(1)
    window.pathways.open("short")
    assert window.step_panel.heading.text() == "STEP 1 OF 1"
    assert window.pathways.badge_state(0) == "current"
    window.pathways.leave()
    assert sorted(i for i in state.geometry_ids if state.is_hidden(i)) == hidden


def test_the_step_text_has_no_literal_colour(window):
    window.pathways.open("loop")
    assert "#c55" not in window.step_panel.details.toHtml()


def test_the_narrow_steps_tab_carries_the_step_text(qapp, toy_pathway_atlas, tmp_path):
    window = open_window(qapp, toy_pathway_atlas, tmp_path, size=(1000, 760))
    window.workspaces.switch("Pathways")
    window.pathways.open("loop")
    qapp.processEvents()
    page = window.pathways.steps_page
    assert not window.step_group.isVisible()
    assert window.routes_group.keys() == ["routes", "steps", "info", "slices"]
    assert page.narrow_details.isVisible() and "Role" in page.narrow_details.toPlainText()
    window.close()


def test_the_wide_steps_tab_does_not_repeat_the_step_text(window, qapp):
    window.pathways.open("loop")
    qapp.processEvents()
    assert not window.pathways.steps_page.narrow_details.isVisible()
