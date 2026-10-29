import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
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
    w.slices_group.reveal("slices")
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


def focal_z(window):
    return window.view.camera.focal_point[2]


def test_reset_frames_the_brain_not_the_cord(window):
    window.view.reset_view()
    assert focal_z(window) > -60.0


def test_selecting_never_moves_the_camera(window):
    window.view.reset_view()
    before = window.view.camera_position
    for structure_id in (210, 101, 2):
        window.state.select(structure_id)
        assert window.view.camera_position == before


def brain_box(window):
    return window.view.scene_bounds


def test_f_frames_the_selection(window):
    frame = window.shortcuts["Frame selection"]
    assert frame.shortcut().toString() == "F"
    window.state.select(210)
    frame.trigger()
    assert focal_z(window) < -150.0
    window.state.select(101)
    frame.trigger()
    b = brain_box(window)
    point = window.view.camera.focal_point
    assert all(b[2 * a] <= point[a] <= b[2 * a + 1] for a in range(3))
    window.state.select(None)
    frame.trigger()
    centre = [(b[2 * a] + b[2 * a + 1]) / 2 for a in range(3)]
    assert np.allclose(window.view.camera.focal_point, centre, atol=1.0)


def test_the_plane_follows_the_spinal_volume(window):
    window.slices.volume_buttons["spine"].click()
    bounds = window.view.plane.GetBounds()
    assert bounds[4] < -150.0 and bounds[5] < -150.0
    assert bounds[3] - bounds[2] < 100.0


def test_one_volume_selection_keeps_the_camera(qapp, toy_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_atlas), progress_path=tmp_path / "p.sqlite")
    before = w.view.camera_position
    w.state.select(101)
    assert w.view.camera_position == before
    w.close()


def test_hidden_spinal_tracts_show_the_segment_beneath(window):
    panel = window.slices
    panel.volume_buttons["spine"].click()
    window.state.set_slice("axial", -180.0)

    def names():
        return [panel.structure_at_pixel(r, c) for r in range(panel.image.shape[0])
                for c in range(panel.image.shape[1])]

    hidden = names()
    window.state.set_hidden([220], False)
    shown = names()
    assert shown.count(220) > 0 and set(hidden) - {None} == {200}
    assert hidden.count(200) == shown.count(200) + shown.count(220)


def test_centre_on_a_brain_tract_returns_to_the_brain(window):
    window.state.set_slice_volume("spine")
    window.state.select(151)
    window.slices.centre_on_selection()
    assert window.state.slice_volume == "brain"


def test_each_volume_remembers_its_slice(window):
    window.state.set_slice("axial", 20.0)
    brain_mm = window.state.slice_mm
    window.slices.volume_buttons["spine"].click()
    window.slices.volume_buttons["brain"].click()
    assert window.state.slice_mm == brain_mm


def test_selecting_a_group_reads_no_meshes(window, monkeypatch):
    reads = []
    real = window.state.atlas.mesh
    monkeypatch.setattr(window.state.atlas, "mesh",
                        lambda *a, **k: reads.append(a) or real(*a, **k))
    window.state.select(2)
    window.state.select(200)
    assert reads == []


def visible_rows(panel):
    _, (y0, y1) = panel.box.viewRange()
    return y1 - y0


def test_the_wheel_zooms_around_the_pointer_and_right_drag_pans(window, qapp):
    panel = window.slices
    qapp.processEvents()
    whole = visible_rows(panel)
    panel.wheel_zoom(3, 20.0, 15.0)
    assert visible_rows(panel) < whole / 1.4 and panel.zoomed()
    before = panel.box.viewRange()
    panel.pan_by(2.0, 0.0)
    assert panel.box.viewRange() != before


def test_zoom_survives_the_slider_and_selection(window, qapp):
    panel = window.slices
    qapp.processEvents()
    panel.wheel_zoom(3, 10.0, 10.0)
    zoomed = panel.box.viewRange()
    panel.slider.setValue(panel.slider.value() + 1)
    window.state.select(101)
    qapp.processEvents()
    assert panel.box.viewRange() == zoomed


def test_switching_volume_or_axis_fits_the_whole_slice(window, qapp):
    panel = window.slices
    qapp.processEvents()
    panel.wheel_zoom(3, 10.0, 10.0)
    window.state.set_slice_volume("spine")
    qapp.processEvents()
    assert not panel.zoomed()
    window.state.set_slice_volume("brain")
    panel.wheel_zoom(3, 10.0, 10.0)
    panel.set_axis("coronal")
    qapp.processEvents()
    assert not panel.zoomed()


def test_zoom_stops_at_its_limits(window, qapp):
    panel = window.slices
    qapp.processEvents()
    panel.wheel_zoom(2, 10.0, 10.0)
    panel.wheel_zoom(-20, 10.0, 10.0)
    assert not panel.zoomed()
    panel.wheel_zoom(200, 10.0, 10.0)
    assert visible_rows(panel) >= 19


def test_f_over_the_slice_fits_it_and_elsewhere_frames_3d(window, qapp, monkeypatch):
    panel = window.slices
    qapp.processEvents()
    panel.wheel_zoom(3, 10.0, 10.0)
    monkeypatch.setattr(panel.view, "underMouse", lambda: True)
    window.frame()
    assert not panel.zoomed()
    monkeypatch.setattr(panel.view, "underMouse", lambda: False)
    called = []
    monkeypatch.setattr(window.view, "frame_selection", lambda: called.append(1))
    window.frame()
    assert called == [1]


def test_centre_on_selection_brings_it_into_a_zoomed_slice(window, qapp):
    panel = window.slices
    qapp.processEvents()
    window.state.select(111)
    panel.centre_on_selection()
    panel.wheel_zoom(4, 0.0, 0.0)
    panel.centre_on_selection()
    qapp.processEvents()
    (x0, x1), (y0, y1) = panel.box.viewRange()
    rows, cols = np.nonzero(panel.layer[..., 3] == 255)
    assert x0 <= cols.mean() <= x1 and y0 <= rows.mean() <= y1


def test_the_slice_cannot_be_panned_out_of_view(window, qapp):
    panel = window.slices
    qapp.processEvents()
    panel.wheel_zoom(3, 10.0, 10.0)
    panel.pan_by(10_000.0, 10_000.0)
    (x0, x1), (y0, y1) = panel.box.viewRange()
    rows, cols = panel.layer.shape[:2]
    assert 0 <= (x0 + x1) / 2 <= cols and 0 <= (y0 + y1) / 2 <= rows


def test_a_fitted_slice_has_no_margin(window, qapp):
    panel = window.slices
    panel.fit_volume()
    qapp.processEvents()
    (x0, x1), (y0, y1) = panel.box.viewRange()
    rows, cols = panel.layer.shape[:2]
    assert abs((x1 - x0) - cols) < 0.5 or abs((y1 - y0) - rows) < 0.5


class SidewaysWheel:
    def __init__(self, pos):
        self._pos = pos
        self.accepted = False

    def orientation(self):
        return Qt.Orientation.Horizontal

    def delta(self):
        return 120

    def pos(self):
        return self._pos

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def test_a_sideways_swipe_does_not_zoom(window, qapp):
    panel = window.slices
    qapp.processEvents()
    before = panel.box.viewRange()
    panel.box.wheelEvent(SidewaysWheel(QPointF(10.0, 10.0)))
    assert panel.box.viewRange() == before and not panel.zoomed()


def grabbed(panel, qapp):
    qapp.processEvents()
    image = panel.view.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
    width, height = image.width(), image.height()
    data = np.frombuffer(image.constBits(), np.uint8, count=image.sizeInBytes())
    return data.reshape(height, image.bytesPerLine())[:, :width * 3].reshape(height, width, 3)


def test_the_template_is_drawn_smooth_and_the_labels_sharp(window, qapp):
    panel = window.slices
    window.state.select(None)
    for letter in panel.letters:
        letter.hide()
    rows, cols = panel.layer.shape[:2]
    panel.wheel_zoom(6, rows / 2, cols / 2)
    window.state.set_hidden(window.state.geometry_ids, True)
    template = grabbed(panel, qapp)
    middle = template[template.shape[0] // 2]
    (x0, x1), (y0, y1) = panel.box.viewRange()
    row = panel._template_2d[round((y0 + y1) / 2)]
    visible = row[max(int(x0), 0):int(np.ceil(x1)) + 1]
    assert len({tuple(p) for p in middle}) > 2 * len(set(visible.tolist()))
    window.state.set_hidden(window.state.geometry_ids, False)
    panel.template = None
    panel.opacity_slider.setValue(100)
    labels = grabbed(panel, qapp)
    allowed = {(0, 0, 0)} | {tuple(int(v) for v in c) for c in panel.colors}
    assert {tuple(int(v) for v in p) for p in labels.reshape(-1, 3)} <= allowed
