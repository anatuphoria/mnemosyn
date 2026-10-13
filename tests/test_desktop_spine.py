import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop import slices
from cns_desktop.main_window import MainWindow
from cns_desktop.state import AppState


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def spine_atlas(toy_spine_atlas):
    return Atlas.open(toy_spine_atlas)


@pytest.fixture
def window(qapp, spine_atlas, tmp_path):
    w = MainWindow(spine_atlas, progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def test_each_volume_has_its_template(spine_atlas):
    assert set(spine_atlas.templates) == {"brain", "spine"}
    assert spine_atlas.template is spine_atlas.templates["brain"]


def test_the_slice_volume_is_validated_and_signalled(spine_atlas):
    state = AppState(spine_atlas)
    seen = []
    state.slice_volume_changed.connect(seen.append)
    assert state.slice_volume == "brain"
    state.set_slice_volume("spine")
    state.set_slice_volume("spine")
    assert seen == ["spine"]
    with pytest.raises(ValueError):
        state.set_slice_volume("tail")


def test_volume_buttons_switch_the_slices(window):
    panel = window.slices
    assert {n: b.text() for n, b in panel.volume_buttons.items()} == {
        "brain": "Brain", "spine": "Spinal cord"}
    panel.volume_buttons["spine"].click()
    spine = window.state.atlas.volumes[1]
    assert window.state.slice_volume == "spine" and panel.labels is spine
    assert panel.template is window.state.atlas.templates["spine"]
    assert panel.slider.maximum() == slices.slice_count(spine.shape, "axial") - 1
    assert -230.0 < window.state.slice_mm < -160.0


def test_switching_volumes_and_back_restores_brain_slices(window):
    panel = window.slices
    brain_max = panel.slider.maximum()
    panel.volume_buttons["spine"].click()
    panel.volume_buttons["brain"].click()
    assert panel.labels is window.state.atlas.volumes[0]
    assert panel.slider.maximum() == brain_max
    assert -60.0 <= window.state.slice_mm <= 80.0


def test_hover_names_spinal_structures(window):
    panel = window.slices
    panel.volume_buttons["spine"].click()
    window.state.set_slice("axial", -180.0)
    found = {panel.structure_at_pixel(r, c) for r in range(panel.image.shape[0])
             for c in range(panel.image.shape[1])}
    assert 200 in found and not (found - {None, 200})


def test_centre_moves_to_the_volume_holding_the_selection(window):
    window.state.select(210)
    window.slices.centre_on_selection()
    assert window.state.slice_volume == "spine"
    assert -220.0 <= window.state.slice_mm <= -196.0


def test_a_quiz_restores_the_slice_volume(window):
    window.state.set_slice_volume("spine")
    window.enter_quiz()
    window.state.set_slice_volume("brain")
    window.leave_quiz()
    assert window.state.slice_volume == "spine"


def test_one_volume_atlases_show_no_volume_buttons(qapp, toy_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_atlas), progress_path=tmp_path / "p.sqlite")
    assert w.slices.volume_buttons == {} and w.state.slice_volume == "brain"
    w.close()
