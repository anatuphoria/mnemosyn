import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolButton

from cns_atlas import Atlas
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import COLOURS, SIZE
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def open_window(qapp, atlas, tmp_path, size=(1400, 900)):
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(*size)
    w.show()
    qapp.processEvents()
    return w


def resize_to(window, qapp, width, height):
    for _ in range(3):
        window.resize(width, height)
        qapp.processEvents()


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def tool_tips(window):
    return [b.toolTip() for b in window.viewport.tools.findChildren(QToolButton)]


def test_the_view_bar_has_the_view_tools_in_every_workspace(window, qapp):
    for name in ("Explore", "Slices", "Pathways", "Lab"):
        window.workspaces.switch(name)
        qapp.processEvents()
        bar = window.viewport.top_bar
        assert bar.isVisible() and bar.height() == SIZE["header"], name
        assert tool_tips(window) == ["Frame selection  F", "Reset view  R", "Tracts  T"], name
        assert window.viewport.tools.isVisible()
    assert window.viewport.view_switch.isVisible()
    window.workspaces.switch("Explore")
    assert not window.viewport.view_switch.isVisible()


def test_the_brain_and_circuit_switch_is_a_segmented_control(window, qapp):
    window.workspaces.switch("Lab")
    switch = window.viewport.view_switch
    assert switch.keys() == ["brain", "circuit"]
    switch.set_current("circuit")
    assert window.viewport.showing_circuit
    window.lab.show_circuit(False)
    assert switch.current() == "brain" and not window.viewport.showing_circuit


def test_the_central_view_keeps_its_minimum_width(window, qapp):
    viewport = window.viewport
    assert viewport.minimum_width("Explore", 1400) == SIZE["central_min"]
    assert viewport.minimum_width("Slices", 1400) == SIZE["central_min_slices"]
    assert viewport.minimum_width("Slices", 1000) == 0
    assert viewport.minimumWidth() == SIZE["central_min"]
    window.workspaces.switch("Slices")
    assert viewport.minimumWidth() == SIZE["central_min_slices"]
    window.workspaces.switch("Explore")
    window.resizeDocks([window.structures_group], [1200], Qt.Orientation.Horizontal)
    qapp.processEvents()
    assert viewport.width() >= SIZE["central_min"]


def test_the_strip_shows_cards_not_loose_text(window, qapp):
    window.workspaces.switch("Lab")
    qapp.processEvents()
    brain = window.lab.brain
    keys = brain.strip_keys()
    assert keys
    strip = window.viewport.strip
    assert strip.isVisible() and strip.width() == 200
    assert strip.heading.text() == "OUTSIDE THE BRAIN"
    for key in keys:
        card = brain.strip_button(key)
        assert card.property("card") == "true" and card.width() <= 200


def test_the_3d_background_is_black(window):
    channels = [round(c * 255) for c in window.view.renderer.GetBackground()]
    assert "#" + "".join(f"{c:02x}" for c in channels) == COLOURS["s0"]


def test_the_slice_controls_fit_a_narrow_panel(window, qapp):
    panel = window.slices
    assert panel.minimumSizeHint().width() <= SIZE["panel_left"]
    assert panel.axis_control.keys() == ["axial", "coronal", "sagittal"]
    assert panel.centre_button.toolTip() == "Centre on selection  C"
    panel.buttons["coronal"].click()
    assert window.state.slice_axis == "coronal"
    assert panel.axis_control.current() == "coronal"
    window.state.set_slice("sagittal", 0.0)
    assert panel.axis_control.current() == "sagittal"


def test_every_workspace_fits_850_px(window, qapp):
    resize_to(window, qapp, 850, 700)
    assert window.width() == 850
    for name in ("Explore", "Slices", "Pathways", "Lab"):
        window.workspaces.switch(name)
        qapp.processEvents()
        assert window.minimumSizeHint().width() <= 850, name
