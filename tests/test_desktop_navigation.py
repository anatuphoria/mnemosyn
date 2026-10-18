import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def structure_pixel(view):
    width, height = view.ren_win.GetSize()
    points = [(x, y) for y in range(6, height, 6) for x in range(6, width, 6)]
    points.sort(key=lambda p: (p[0] - width / 2) ** 2 + (p[1] - height / 2) ** 2)
    for x, y in points:
        if view.structure_at(x, y) is not None:
            return x, y
    raise AssertionError("no structure pixel")


def camera(view):
    cam = view.camera
    return np.array(cam.position), np.array(cam.focal_point), np.array(cam.direction)


def mouse(view, event, x, y):
    view.iren.interactor.SetEventInformation(x, y)
    view.iren.interactor.InvokeEvent(event)


def test_wheel_zooms_toward_the_point_under_the_mouse(window):
    view = window.view
    x, y = structure_pixel(view)
    view.structure_at(x, y)
    point = np.array(view._picker.GetPickPosition())
    position, focal, direction = camera(view)
    view.zoom_at(x, y, 2.0)
    new_position, new_focal, new_direction = camera(view)
    assert np.allclose(new_focal - point, (focal - point) / 2, atol=1e-3)
    assert np.allclose(new_position - point, (position - point) / 2, atol=1e-3)
    assert np.allclose(new_direction, direction, atol=1e-6)


def test_wheel_over_background_zooms_to_the_centre(window):
    view = window.view
    assert view.structure_at(1, 1) is None
    position, focal, _ = camera(view)
    view.zoom_at(1, 1, 2.0)
    new_position, new_focal, _ = camera(view)
    assert np.allclose(new_focal, focal, atol=1e-6)
    assert np.isclose(np.linalg.norm(new_position - new_focal),
                      np.linalg.norm(position - focal) / 2, atol=1e-3)


def test_wheel_events_zoom(window):
    view = window.view
    position, focal, _ = camera(view)
    width, height = view.ren_win.GetSize()
    mouse(view, "MouseWheelForwardEvent", 1, 1)
    assert np.linalg.norm(camera(view)[0] - camera(view)[1]) < np.linalg.norm(position - focal)


def test_right_drag_pans(window):
    view = window.view
    position, focal, direction = camera(view)
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    mouse(view, "RightButtonPressEvent", x, y)
    mouse(view, "MouseMoveEvent", x + 20, y)
    mouse(view, "MouseMoveEvent", x + 40, y)
    mouse(view, "RightButtonReleaseEvent", x + 40, y)
    new_position, new_focal, new_direction = camera(view)
    moved = new_focal - focal
    assert np.linalg.norm(moved) > 1e-3
    assert np.allclose(new_position - position, moved, atol=1e-6)
    assert np.allclose(new_direction, direction, atol=1e-6)


def test_right_click_does_not_select(window):
    view = window.view
    window.state.select(None)
    x, y = structure_pixel(view)
    mouse(view, "RightButtonPressEvent", x, y)
    mouse(view, "RightButtonReleaseEvent", x, y)
    assert window.state.selected is None


def test_left_drag_still_rotates_and_a_left_click_still_selects(window):
    view = window.view
    _, _, direction = camera(view)
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    mouse(view, "LeftButtonPressEvent", x, y)
    mouse(view, "MouseMoveEvent", x + 30, y)
    mouse(view, "MouseMoveEvent", x + 60, y)
    mouse(view, "LeftButtonReleaseEvent", x + 60, y)
    assert not np.allclose(camera(view)[2], direction, atol=1e-4)
    window.state.select(None)
    x, y = structure_pixel(view)
    mouse(view, "LeftButtonPressEvent", x, y)
    mouse(view, "LeftButtonReleaseEvent", x, y)
    assert window.state.selected == view.structure_at(x, y)


def test_route_steps_and_quiz_answers_leave_the_camera(qapp, toy_pathway_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_pathway_atlas), progress_path=tmp_path / "p.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    before = w.view.camera_position
    w.pathway_dock.raise_()
    w.pathways.open("loop")
    for index in range(len(w.pathways.lights)):
        w.pathways.go(index)
        qapp.processEvents()
        assert w.view.camera_position == before
    w.close()



def drag(view, button, x, y, dx, dy, steps=4):
    mouse(view, f"{button}ButtonPressEvent", x, y)
    for k in range(1, steps + 1):
        mouse(view, "MouseMoveEvent", x + dx * k // steps, y + dy * k // steps)
    mouse(view, f"{button}ButtonReleaseEvent", x + dx, y + dy)


def elevation(view):
    direction = np.array(view.camera.direction)
    return float(np.degrees(np.arcsin(-direction[2] / np.linalg.norm(direction))))


def test_a_sideways_drag_only_turns_sideways(window):
    view = window.view
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    drag(view, "Left", x, y, 0, 60)
    before = elevation(view)
    for _ in range(3):
        drag(view, "Left", x, y, 80, 0)
        assert abs(elevation(view) - before) < 1e-6
        assert np.allclose(view.camera.up, (0.0, 0.0, 1.0), atol=1e-6)


def test_tilting_stops_short_of_the_poles_and_never_rolls(window):
    view = window.view
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    for _ in range(6):
        drag(view, "Left", x, y, 37, 400)
    assert elevation(view) < 89.0
    assert np.allclose(view.camera.up, (0.0, 0.0, 1.0), atol=1e-6)
    for _ in range(12):
        drag(view, "Left", x, y, -25, -400)
    assert elevation(view) > -89.0
    assert np.allclose(view.camera.up, (0.0, 0.0, 1.0), atol=1e-6)


def test_panning_still_works_after_rotating(window):
    view = window.view
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    drag(view, "Left", x, y, 50, 30)
    focal = np.array(view.camera.focal_point)
    drag(view, "Right", x, y, 40, 0)
    assert np.linalg.norm(np.array(view.camera.focal_point) - focal) > 1e-3


def test_dragging_up_tilts_the_model_like_grabbing_it(window):
    view = window.view
    width, height = view.ren_win.GetSize()
    x, y = width // 2, height // 2
    before = elevation(view)
    drag(view, "Left", x, y, 0, 50)
    assert elevation(view) == pytest.approx(before - 50 * 0.4, abs=1e-3)
    drag(view, "Left", x, y, 0, -50)
    assert elevation(view) == pytest.approx(before, abs=1e-3)
