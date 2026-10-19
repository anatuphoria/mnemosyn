import random

import numpy as np
import pytest
import pyvista as pv
from PySide6.QtWidgets import QApplication, QDockWidget

from atlas_package import write_package
from cns_atlas import Atlas
from cns_atlas.meshes import MeshData
from cns_atlas.model import Structure
from cns_desktop.main_window import MainWindow
from cns_desktop.views.brain_view import FAINT, SHELL_OPACITY
from cns_study.session import QuizChoice

UPPER, LOWER, HORN, TRACT, OUTER = 401, 402, 300, 310, 110
GREY = (170, 170, 180)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def mesh_data(mesh: pv.PolyData) -> MeshData:
    mesh = mesh.triangulate().compute_normals(cell_normals=False, auto_orient_normals=True)
    return MeshData(np.asarray(mesh.points, dtype=np.float32),
                    np.asarray(mesh.point_data["Normals"], dtype=np.float16),
                    mesh.faces.reshape(-1, 4)[:, 1:].astype(np.uint32))


def tube(radius, z0, z1, centre=(0.0, 0.0), capped=True):
    return mesh_data(pv.Cylinder(center=(*centre, (z0 + z1) / 2), direction=(0, 0, 1),
                                 radius=radius, height=z1 - z0, resolution=60, capping=capped))


@pytest.fixture
def window(qapp, tmp_path):
    structures = [
        Structure(1, "CNS", "Central nervous system", (1,), GREY, kind="group"),
        Structure(2, "Br", "Brain", (1, 2), GREY, kind="group"),
        Structure(OUTER, "OUT", "Outer nucleus", (1, 2, OUTER), (90, 140, 230),
                  kind="nucleus", side="midline"),
        Structure(3, "SpC", "Spinal cord", (1, 3), GREY, kind="group"),
        Structure(4, "SpSeg", "Segments", (1, 3, 4), GREY, kind="group"),
        Structure(UPPER, "UP", "Upper segment", (1, 3, 4, UPPER), (70, 170, 160),
                  kind="cover", side="midline"),
        Structure(LOWER, "LO", "Lower segment", (1, 3, 4, LOWER), (215, 170, 90),
                  kind="cover", side="midline"),
        Structure(HORN, "HN", "Horn", (1, 3, HORN), (230, 150, 130), kind="nucleus",
                  side="midline"),
        Structure(TRACT, "TR", "Tract", (1, 3, TRACT), (70, 120, 230), kind="tract",
                  side="midline"),
    ]
    meshes = {UPPER: tube(10.0, 0.0, 20.0, capped=False),
              LOWER: tube(10.0, -20.0, 0.0, capped=False),
              HORN: tube(3.0, -15.0, 15.0), TRACT: tube(2.0, -15.0, 15.0, (0.0, -6.0)),
              OUTER: mesh_data(pv.Sphere(radius=3.0, center=(-30.0, 6.0, 5.0)))}
    root = write_package(tmp_path / "atlas", structures, meshes=meshes)
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1000, 800)
    w.show()
    for dock in w.findChildren(QDockWidget):
        dock.hide()
    qapp.processEvents()
    view = w.view
    view.camera_position = [(300.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
    view.renderer.ResetCameraClippingRange()
    view.render()
    yield w
    w.close()


def pixel_of(view, point):
    view.renderer.SetWorldPoint(*point, 1.0)
    view.renderer.WorldToDisplay()
    x, y, _ = view.renderer.GetDisplayPoint()
    return round(x), round(y)


def opacities(view):
    return {view.shell_actors[i].GetProperty().GetOpacity() for i in (UPPER, LOWER)}


def test_covers_are_solid_by_default(window):
    view = window.view
    assert view.cover_ids == {UPPER, LOWER} and opacities(view) == {1.0}
    assert view.inside_ids == {HORN, TRACT} and not view.looking_inside()


def test_selecting_an_inner_part_fades_the_covers(window):
    view = window.view
    window.state.select(HORN)
    assert opacities(view) == {SHELL_OPACITY}
    window.state.select(UPPER)
    assert opacities(view) == {1.0}


def test_tracts_shown_with_t_fade_the_covers(window):
    window.state.toggle_tracts()
    assert opacities(window.view) == {SHELL_OPACITY}
    window.state.toggle_tracts()
    assert opacities(window.view) == {1.0}


def test_a_find_quiz_on_an_inner_part_fades_the_covers(window):
    window._prefer_in_slices({HORN})
    assert opacities(window.view) == {SHELL_OPACITY}
    window._prefer_in_slices(())
    assert opacities(window.view) == {1.0}


def test_a_solid_cover_takes_the_click(window):
    view = window.view
    assert view.structure_at(*pixel_of(view, (10.0, 0.0, 5.0))) == UPPER
    assert view.structure_at(*pixel_of(view, (10.0, 0.0, -5.0))) == LOWER


def test_a_faded_cover_passes_the_click_inward(window):
    view = window.view
    window.state.toggle_tracts()
    assert view.structure_at(*pixel_of(view, (10.0, -6.0, 5.0))) == TRACT
    assert view.structure_at(*pixel_of(view, (10.0, 0.0, 5.0))) == HORN


def test_a_faded_cover_keeps_a_click_on_something_outside(window):
    view = window.view
    window.state.select(HORN)
    assert view.structure_at(*pixel_of(view, (10.0, 6.0, 5.0))) == UPPER


def test_covers_hidden_or_out_of_focus_follow_the_usual_rules(window):
    view = window.view
    window.state.set_focus({OUTER})
    assert opacities(view) == {FAINT}
    window.state.set_focus(None)
    window.state.set_hidden([UPPER], True)
    assert not view.shell_actors[UPPER].GetVisibility() and not view.is_drawn(UPPER)


def test_the_cord_is_solid_again_on_the_find_summary(window):
    window.start_quiz(QuizChoice("find", "structures", HORN, False), rng=random.Random(1))
    quiz = window.quiz
    assert quiz.item.id == HORN and opacities(window.view) == {SHELL_OPACITY}
    while quiz.item is not None:
        window.state.select(next(iter(quiz.item.geometry)))
        quiz.go_on()
    assert quiz.phase == "summary" and opacities(window.view) == {1.0}
    quiz.stop()
