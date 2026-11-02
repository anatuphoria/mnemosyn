import pytest
from PySide6.QtWidgets import QApplication

from cns_desktop.design.tokens import rgb
from pathway_helpers import open_window, projected_height

ACCENT = tuple(c / 255 for c in rgb("accent"))


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


def own_colour(window, structure_id):
    return tuple(c / 255 for c in window.state.atlas.get(structure_id).rgb_triplet)


def test_a_route_hides_the_plane_and_frames_itself(window, qapp):
    window.pathways.open("loop")
    qapp.processEvents()
    assert not window.view.plane.GetVisibility()
    window.state.set_slice(window.state.slice_axis, window.state.slice_mm + 1.0)
    assert not window.view.plane.GetVisibility()
    assert projected_height(window.view, window.route_bounds()) >= 0.5 * window.view.height()


def test_passed_steps_take_the_accent_and_later_steps_dim(window):
    panel = window.pathways
    panel.open("loop")
    panel.go(2)
    colours = window.view.chunks.colors()
    meshes = [[i for i in ids if window.view.chunks.has(i)] for ids in panel.lights]
    assert any(meshes[:2]) and any(meshes[3:])
    for n, ids in enumerate(meshes):
        for i in ids:
            if n < 2:
                assert colours[i] == pytest.approx(ACCENT)
            elif n == 2:
                assert colours.get(i) is None
            else:
                assert colours[i] != pytest.approx(own_colour(window, i))
                assert sum(colours[i]) < sum(own_colour(window, i))


def test_closing_a_route_gives_back_camera_plane_and_colours(window, qapp):
    window.view.camera.Zoom(0.5)
    before = window.view.camera_position.to_list()
    angle = window.view.renderer.GetActiveCamera().GetViewAngle()
    shown = window.view.plane.GetVisibility()
    window.pathways.open("loop")
    window.pathways.go(3)
    window.pathways.leave()
    qapp.processEvents()
    after = window.view.camera_position.to_list()
    assert [list(p) for p in after] == [pytest.approx(list(p)) for p in before]
    assert window.view.renderer.GetActiveCamera().GetViewAngle() == pytest.approx(angle)
    assert window.view.plane.GetVisibility() == shown
    assert window.view.chunks.colors() == {}
