import numpy as np
import pytest
import pyvista as pv
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.views.outline import OutlineLayer


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, root, tmp_path):
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


def test_the_outline_layer_draws_through_other_shapes():
    p = pv.Plotter(off_screen=True, window_size=(200, 200))
    p.set_background("black")
    p.add_mesh(pv.Sphere(radius=10.0), color="grey")
    small = pv.Sphere(radius=3.0, center=(4.0, 0.0, 0.0))
    layer = OutlineLayer(p.ren_win, p.renderer)
    layer.add_blocks([1], [small])
    p.camera_position = [(0.0, 0.0, 60.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    layer.show([])
    p.ren_win.Render()
    before = np.asarray(p.screenshot(return_img=True)).astype(int)
    layer.show([1])
    p.ren_win.Render()
    after = np.asarray(p.screenshot(return_img=True)).astype(int)
    assert layer.shown == frozenset({1})
    assert np.abs(after - before).sum() > 0
    p.close()


def actor_counts(view):
    return (view.renderer.GetActors().GetNumberOfItems(),
            view.outline.renderer.GetActors().GetNumberOfItems())


def test_selection_adds_no_geometry(qapp, toy_atlas, tmp_path):
    w = open_window(qapp, toy_atlas, tmp_path)
    before = actor_counts(w.view)
    for structure_id in (2, 1, 101):
        w.state.select(structure_id)
        assert actor_counts(w.view) == before
        visible = [i for i in w.state.highlighted_ids() if not w.state.is_hidden(i)]
        assert w.view.overlay_ids == visible
        assert w.view.outline.shown == frozenset(visible)
    w.close()


def test_a_first_tract_selection_is_outlined(qapp, toy_tract_atlas, tmp_path):
    w = open_window(qapp, toy_tract_atlas, tmp_path)
    assert w.view.tract_actors == {}
    w.state.select(151)
    assert 151 in w.view.overlay_ids and 151 in w.view.outline.shown
    w.close()
