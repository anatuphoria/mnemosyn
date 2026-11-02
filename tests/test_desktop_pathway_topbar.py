import pytest
from PySide6.QtWidgets import QApplication

from cns_desktop.design.tokens import SIZE
from pathway_helpers import open_window


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    w.workspaces.switch("Pathways")
    qapp.processEvents()
    yield w
    w.lab.document.undo.setClean()
    w.close()


def test_route_controls_live_in_the_top_bar(window):
    bar = window.topbar.group("Pathways")
    panel = window.pathways
    for widget in (panel.play_button, panel.back_button, panel.next_button, panel.speed_picker,
                   panel.side_control, panel.lab_button):
        assert bar.isAncestorOf(widget)
    assert not panel.play_button.isEnabled() and not panel.speed_picker.isEnabled()
    assert panel.side_control.isHidden()
    panel.open("loop")
    assert panel.play_button.isEnabled() and not panel.side_control.isHidden()
    panel.leave()
    assert not panel.play_button.isEnabled() and panel.side_control.isHidden()


def test_the_steps_page_holds_no_play_controls_and_fits(window, qapp):
    panel = window.pathways
    panel.open("loop")
    page = panel.steps_page
    assert not page.isAncestorOf(panel.play_button) and not page.isAncestorOf(panel.side_control)
    page.resize(SIZE["panel_min"], 700)
    qapp.processEvents()
    assert page.minimumSizeHint().width() <= SIZE["panel_min"]


def test_a_right_side_route_shows_right_side_steps(window):
    panel = window.pathways
    panel.open("loop")
    panel.side_buttons["right"].click()
    assert panel.side_control.current() == "right" and panel.side == "right"
    assert "right" in panel.start.text()
    assert "(right)" in panel.steps.item(0).text()


def test_a_route_survives_a_trip_to_explore(window):
    panel = window.pathways
    panel.open("loop")
    panel.go(1)
    window.workspaces.switch("Explore")
    window.workspaces.switch("Pathways")
    assert panel.pathway is not None and panel.index == 1
    assert window.routes_group.current() == "steps" and panel.play_button.isEnabled()


def test_space_at_the_end_keeps_the_play_icon_in_step(window):
    panel = window.pathways
    panel.open("mood")
    panel.seek(window.state.atlas.timelines["mood"].duration)
    window.shortcuts["Play or pause"].trigger()
    assert (panel.play_button.toolTip() == "Pause  Space") == panel.playing
    window.shortcuts["Play or pause"].trigger()
    assert (panel.play_button.toolTip() == "Pause  Space") == panel.playing


def test_the_lab_button_shows_only_for_routes_with_a_lab_system(window):
    panel = window.pathways
    panel.open("loop")
    assert panel.lab_button.isHidden()
    panel.open("mood")
    assert not panel.lab_button.isHidden()
