import random

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_study.session import QuizChoice


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, root, tmp_path):
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    return w


@pytest.fixture
def cells_window(qapp, toy_cells_atlas, tmp_path):
    w = open_window(qapp, toy_cells_atlas, tmp_path)
    yield w
    w.close()


@pytest.fixture
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    yield w
    w.close()


def open_toy(w) -> None:
    w.state.select(101)
    w.open_cells("toy")
    QApplication.processEvents()


def test_info_link_opens_the_cells_dock(cells_window):
    cells_window.state.select(101)
    assert "cells:toy" in cells_window.info.toHtml()
    cells_window.info.anchorClicked.emit(QUrl("cells:toy"))
    QApplication.processEvents()
    assert cells_window.cell_dock.isVisible() and cells_window.state.cell_view == "toy"
    assert cells_window.cells.cell_view.key == "toy"


def test_cells_dock_is_not_built_at_startup(cells_window):
    assert cells_window.cells is None and cells_window.cell_dock is None


def test_no_cells_link_or_action_without_cell_views(window):
    window.state.select(101)
    assert "cells:" not in window.info.toHtml()
    assert not window.shortcuts["Cells"].isEnabled()


def test_cells_action_follows_the_selection(cells_window):
    cells_window.state.select(110)
    assert not cells_window.shortcuts["Cells"].isEnabled()
    cells_window.state.select(101)
    assert cells_window.shortcuts["Cells"].isEnabled()


def test_n_toggles_the_cells_dock(cells_window):
    cells_window.state.select(101)
    cells_window.shortcuts["Cells"].trigger()
    QApplication.processEvents()
    assert cells_window.cell_dock.isVisible()
    cells_window.shortcuts["Cells"].trigger()
    QApplication.processEvents()
    assert not cells_window.cell_dock.isVisible() and cells_window.state.cell_view is None


def test_space_plays_cells_only_while_the_dock_is_visible(cells_window):
    open_toy(cells_window)
    cells_window.view.setFocus()
    QTest.keyClick(cells_window.view, Qt.Key.Key_Space)
    assert cells_window.cells.playing
    cells_window.close_cells()
    QApplication.processEvents()
    assert not cells_window.cells.playing
    assert not cells_window.shortcuts["Play or pause"].isEnabled()


def test_right_key_steps_the_cells_view(cells_window):
    open_toy(cells_window)
    cells_window.view.setFocus()
    QTest.keyClick(cells_window.view, Qt.Key.Key_Right)
    assert cells_window.cells.index == 1


def test_space_in_the_search_box_types_a_space_with_cells_open(cells_window):
    open_toy(cells_window)
    cells_window.tree_dock.raise_()
    box = cells_window.tree.filter_box
    box.setFocus()
    QTest.keyClicks(box, "a b")
    assert box.text() == "a b" and not cells_window.cells.playing


def test_opening_cells_pauses_a_playing_route(cells_window):
    cells_window.pathways.open("loop")
    cells_window.pathways.play()
    open_toy(cells_window)
    assert not cells_window.pathways.playing


def test_route_keys_return_to_the_route_after_closing_cells(cells_window):
    cells_window.pathways.open("loop")
    open_toy(cells_window)
    cells_window.close_cells()
    QApplication.processEvents()
    cells_window.view.setFocus()
    QTest.keyClick(cells_window.view, Qt.Key.Key_Space)
    assert cells_window.pathways.playing and not cells_window.cells.playing
    cells_window.pathways.pause()


def test_dock_stays_open_on_another_selection(cells_window):
    open_toy(cells_window)
    cells_window.state.select(110)
    QApplication.processEvents()
    assert cells_window.cell_dock.isVisible() and cells_window.state.cell_view == "toy"


def test_right_side_mirrors_the_drawing_but_not_its_text(cells_window):
    open_toy(cells_window)
    left = [item.sceneBoundingRect().center().x() for item in cells_window.cells.items("box:input")]
    cells_window.state.select(102)
    QApplication.processEvents()
    assert cells_window.state.cell_side == "right" and cells_window.cells.side == "right"
    right = [item.sceneBoundingRect().center().x() for item in cells_window.cells.items("box:input")]
    assert right != left
    assert all(item.sceneTransform().m11() > 0 for item in cells_window.cells.items("label"))


def test_quiz_closes_the_cells_dock(cells_window):
    open_toy(cells_window)
    cells_window.start_quiz(QuizChoice("name-typed", "structures", None, False),
                            rng=random.Random(1))
    QApplication.processEvents()
    assert not cells_window.cell_dock.isVisible()
    cells_window.quiz.stop()


def test_leaving_a_quiz_keeps_cells_off_without_a_view(cells_window):
    cells_window.state.select(110)
    cells_window.start_quiz(QuizChoice("name-typed", "structures", None, False),
                            rng=random.Random(1))
    cells_window.quiz.stop()
    QApplication.processEvents()
    cells_window.state.select(110)
    assert not cells_window.shortcuts["Cells"].isEnabled()


def plane_centre(w):
    return tuple(round(c, 3) for c in w.view.cell_plane_actor.GetCenter())


def test_plane_appears_on_open_and_goes_on_close(cells_window):
    open_toy(cells_window)
    assert cells_window.view.cell_plane_actor.GetVisibility()
    cells_window.close_cells()
    QApplication.processEvents()
    assert not cells_window.view.cell_plane_actor.GetVisibility()


def test_plane_follows_the_side(cells_window):
    open_toy(cells_window)
    left = plane_centre(cells_window)
    cells_window.state.select(102)
    QApplication.processEvents()
    assert plane_centre(cells_window) != left


def test_plane_is_not_pickable(cells_window):
    open_toy(cells_window)
    assert not cells_window.view.cell_plane_actor.GetPickable()


def test_no_plane_before_cells_open(cells_window):
    assert cells_window.view.cell_plane_actor is None


def test_the_dock_opens_large_enough_and_fitted(cells_window):
    open_toy(cells_window)
    QApplication.processEvents()
    panel = cells_window.cells
    assert panel.view.viewport().height() >= 300
    shown = panel.view.mapToScene(panel.view.viewport().rect()).boundingRect()
    content = panel.content_rect()
    both = shown.intersected(content)
    assert both.width() * both.height() / (content.width() * content.height()) > 0.95


def test_reopening_the_dock_from_its_menu_restores_everything(cells_window):
    open_toy(cells_window)
    cells_window.close_cells()
    QApplication.processEvents()
    cells_window.cell_dock.toggleViewAction().trigger()
    QApplication.processEvents()
    assert cells_window.state.cell_view == "toy"
    assert cells_window.view.cell_plane_actor.GetVisibility()
    assert cells_window.shortcuts["Play or pause"].isEnabled()


def test_the_cells_dock_cannot_be_reopened_during_a_quiz(cells_window):
    open_toy(cells_window)
    cells_window.start_quiz(QuizChoice("name-typed", "structures", None, False),
                            rng=random.Random(1))
    assert not cells_window.cell_dock.toggleViewAction().isEnabled()
    cells_window.quiz.stop()
    QApplication.processEvents()
    assert cells_window.cell_dock.toggleViewAction().isEnabled()
