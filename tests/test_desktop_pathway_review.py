import random

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.tokens import SIZE
from cns_desktop.main_window import MainWindow
from cns_study.session import QuizChoice
from pathway_helpers import open_window


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


def test_layouts_saved_before_the_step_panel_are_dropped(qapp, toy_pathway_atlas, tmp_path):
    settings = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    settings.setValue("workspaces/version", 2)
    settings.setValue("workspaces/Explore", b"old layout")
    settings.sync()
    w = MainWindow(Atlas.open(toy_pathway_atlas), progress_path=tmp_path / "p.sqlite",
                   settings=settings)
    w.show()
    qapp.processEvents()
    assert settings.value("workspaces/Explore") is None
    assert not w.step_group.isVisible()
    w.close()


def test_the_window_menu_brings_the_step_panel_back(window, qapp):
    assert window.step_group.toggleViewAction() in window.window_menu.actions()
    window.step_group.close()
    qapp.processEvents()
    window.step_group.toggleViewAction().trigger()
    qapp.processEvents()
    assert window.step_group.isVisible() and window.step_group.keys() == ["step", "info", "slices"]


def test_long_step_names_are_never_cut_off(window, qapp):
    panel = window.pathways
    panel.open("loop")
    item = panel.steps.item(0)
    item.setText("1 " + "Middle cingulate cortex and posterior cingulate cortex (left) " * 2)
    page = panel.steps_page
    window.resizeDocks([window.routes_group], [SIZE["panel_min"]], Qt.Orientation.Horizontal)
    qapp.processEvents()
    delegate = panel.steps.itemDelegate()
    rect = panel.steps.visualItemRect(item)
    assert delegate.needed_height(item.text(), rect.width()) <= rect.height()
    assert page.isVisible()


def test_a_quiz_in_pathways_hides_and_locks_the_step_panel(window, qapp):
    window.start_quiz(QuizChoice("find", "structures", None, False), rng=random.Random(1))
    qapp.processEvents()
    assert not window.step_group.isVisible()
    assert not window.step_group.toggleViewAction().isEnabled()
    window.quiz.stop()
    window.leave_quiz()
    qapp.processEvents()
    assert window.step_group.isVisible() and window.step_group.toggleViewAction().isEnabled()


def test_the_activity_chart_keeps_no_hidden_note_box(window):
    assert not hasattr(window.chart, "note_area") and not hasattr(window.chart, "note")
