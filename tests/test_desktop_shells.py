import random

import numpy as np
import pytest
import pyvista as pv
from PySide6.QtWidgets import QApplication

from atlas_package import write_package
from cns_atlas import Atlas
from cns_atlas.meshes import MeshData
from cns_atlas.model import Structure
from cns_desktop.main_window import MainWindow
from cns_desktop.views.brain_view import FAINT, SHELL_OPACITY
from cns_study.session import QuizChoice

SHELL, INNER, OUTER = 230, 231, 110
GREY = (170, 170, 180)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def sphere(radius, centre=(0.0, 0.0, 0.0)) -> MeshData:
    mesh = pv.Sphere(radius=radius, center=centre, theta_resolution=40, phi_resolution=40)
    mesh = mesh.compute_normals(cell_normals=False, auto_orient_normals=True)
    return MeshData(np.asarray(mesh.points, dtype=np.float32),
                    np.asarray(mesh.point_data["Normals"], dtype=np.float16),
                    mesh.faces.reshape(-1, 4)[:, 1:].astype(np.uint32))


@pytest.fixture
def window(qapp, tmp_path):
    structures = [
        Structure(1, "CNS", "Central nervous system", (1,), GREY, kind="group"),
        Structure(2, "Br", "Brain", (1, 2), GREY, kind="group"),
        Structure(6, "ST", "Stem", (1, 2, 6), GREY, kind="group"),
        Structure(SHELL, "SH", "Stem body", (1, 2, 6, SHELL), GREY, kind="shell",
                  side="midline"),
        Structure(INNER, "IN", "Inner nucleus", (1, 2, 6, INNER), (230, 120, 120),
                  kind="nucleus", side="midline"),
        Structure(OUTER, "OUT", "Outer nucleus", (1, 2, OUTER), (90, 140, 230),
                  kind="nucleus", side="midline"),
    ]
    meshes = {SHELL: sphere(30.0), INNER: sphere(5.0), OUTER: sphere(6.0, (-50.0, 0.0, 18.0))}
    root = write_package(tmp_path / "atlas", structures, meshes=meshes)
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1000, 800)
    w.show()
    qapp.processEvents()
    look_from_the_side(w.view)
    yield w
    w.close()


def look_from_the_side(view):
    view.camera_position = [(300.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
    view.renderer.ResetCameraClippingRange()
    view.render()


def pixel_of(view, point):
    view.renderer.SetWorldPoint(*point, 1.0)
    view.renderer.WorldToDisplay()
    x, y, _ = view.renderer.GetDisplayPoint()
    return round(x), round(y)


def test_shells_are_drawn_see_through(window):
    view = window.view
    actor = view.shell_actors[SHELL]
    assert actor.GetVisibility() and actor.GetProperty().GetOpacity() == SHELL_OPACITY
    assert INNER in view.ids and SHELL not in view.ids and view.is_drawn(SHELL)


def test_clicks_pass_through_a_shell_to_the_nucleus(window):
    view = window.view
    assert view.structure_at(*pixel_of(view, (0.0, 0.0, 0.0))) == INNER
    assert view.structure_at(*pixel_of(view, (0.0, 0.0, -20.0))) == SHELL


def test_a_click_on_a_shell_does_not_reach_shapes_behind_it(window):
    view = window.view
    x, y = pixel_of(view, (-50.0, 0.0, 18.0))
    assert view.structure_at(x, y) == SHELL
    view.state.set_hidden([SHELL], True)
    view.render()
    assert view.structure_at(x, y) == OUTER


def test_find_quiz_accepts_a_nucleus_behind_a_shell(window, qapp):
    window.start_quiz(QuizChoice("find", "structures", INNER, False), rng=random.Random(1))
    quiz = window.quiz
    assert quiz.item.id == INNER
    look_from_the_side(window.view)
    window.view.pick_at(*pixel_of(window.view, (0.0, 0.0, 0.0)))
    qapp.processEvents()
    assert quiz.phase == "feedback" and "Correct" in quiz.feedback.text()


def test_shells_hide_isolate_and_fade_like_any_structure(window):
    view, state = window.view, window.state
    actor = view.shell_actors[SHELL]
    state.set_hidden([SHELL], True)
    assert not actor.GetVisibility() and not view.is_drawn(SHELL)
    state.show_all()
    assert actor.GetVisibility()
    state.isolate(OUTER)
    assert not actor.GetVisibility()
    state.show_all()
    state.set_focus([INNER])
    assert actor.GetProperty().GetOpacity() == FAINT and not actor.GetPickable()
    state.set_focus(None)
    assert actor.GetProperty().GetOpacity() == SHELL_OPACITY and actor.GetPickable()


def test_a_selected_shell_is_outlined(window):
    window.state.select(SHELL)
    assert SHELL in window.view.overlay_ids and SHELL in window.view.outline.shown


def test_find_quiz_on_a_shell_accepts_a_click_over_a_nucleus_inside_it(window, qapp):
    window.start_quiz(QuizChoice("find", "structures", SHELL, False), rng=random.Random(1))
    quiz = window.quiz
    assert quiz.item.id == SHELL
    look_from_the_side(window.view)
    window.view.pick_at(*pixel_of(window.view, (0.0, 0.0, 0.0)))
    qapp.processEvents()
    assert quiz.phase == "feedback" and "Correct" in quiz.feedback.text()


def test_zooming_over_a_body_picks_once(window, monkeypatch):
    view = window.view
    picks = []
    real = view._pick
    monkeypatch.setattr(view, "_pick", lambda x, y: picks.append((x, y)) or real(x, y))
    position = np.array(view.camera.GetPosition())
    view.zoom_at(*pixel_of(view, (0.0, 0.0, 0.0)), 1.15)
    assert len(picks) == 1
    assert np.linalg.norm(np.array(view.camera.GetPosition())) < np.linalg.norm(position)
