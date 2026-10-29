import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.workspaces import NAMES

LEFT, RIGHT = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def settings_at(path):
    return QSettings(str(path / "settings.ini"), QSettings.Format.IniFormat)


def open_window(qapp, atlas, tmp_path, settings=None):
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings if settings is not None else settings_at(tmp_path))
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_behaviour_atlas, tmp_path):
    w = open_window(qapp, toy_behaviour_atlas, tmp_path)
    yield w
    qapp.processEvents()
    w.close()


def fake_lab(window):
    dock = QDockWidget("Lab panel", window)
    dock.setObjectName("Lab panel")
    dock.setWidget(QLabel("lab"))
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    calls = []
    window.workspaces.register_lab([dock], lambda: calls.append("enter"),
                                   lambda: calls.append("leave"))
    return dock, calls


def test_explore_is_todays_layout(window):
    assert NAMES == ("Explore", "Slices", "Pathways", "Lab")
    assert window.workspaces.current == "Explore"
    assert window.dockWidgetArea(window.tree_dock) == LEFT
    assert window.dockWidgetArea(window.pathway_dock) == LEFT
    assert window.dockWidgetArea(window.slice_dock) == RIGHT
    assert window.dockWidgetArea(window.info_dock) == RIGHT
    assert window.chart_dock.isHidden() and window.quiz_dock.isHidden()
    assert window.view.parent() is not window
    assert window.viewport.view is window.view


def test_the_lab_button_shows_only_when_a_lab_is_registered(window):
    assert window.workspaces.button("Lab").isHidden()
    fake_lab(window)
    assert not window.workspaces.button("Lab").isHidden()


def test_slices_gives_the_slice_panel_room_and_pathways_raises_its_panel(window):
    window.workspaces.switch("Slices")
    assert window.slice_dock.isVisible() and window.info_dock.isVisible()
    window.workspaces.switch("Pathways")
    window.repaint()
    assert not window.pathway_dock.visibleRegion().isEmpty()
    assert window.tree_dock.visibleRegion().isEmpty()


def test_each_workspace_remembers_its_own_layout(qapp, toy_behaviour_atlas, tmp_path):
    window = open_window(qapp, toy_behaviour_atlas, tmp_path)
    window.workspaces.switch("Slices")
    window.addDockWidget(LEFT, window.info_dock)
    window.workspaces.switch("Explore")
    assert window.dockWidgetArea(window.info_dock) == RIGHT
    window.workspaces.switch("Slices")
    assert window.dockWidgetArea(window.info_dock) == LEFT
    window.close()
    again = open_window(qapp, toy_behaviour_atlas, tmp_path)
    again.workspaces.switch("Slices")
    assert again.dockWidgetArea(again.info_dock) == LEFT
    again.close()


def test_reset_layout_restores_the_default(window):
    window.workspaces.switch("Slices")
    window.addDockWidget(LEFT, window.info_dock)
    window.workspaces.reset("Slices")
    assert window.dockWidgetArea(window.info_dock) == RIGHT


def test_a_stale_layout_version_is_ignored(qapp, toy_behaviour_atlas, tmp_path):
    window = open_window(qapp, toy_behaviour_atlas, tmp_path)
    window.workspaces.switch("Slices")
    window.addDockWidget(LEFT, window.info_dock)
    window.workspaces.switch("Explore")
    window.close()
    settings = settings_at(tmp_path)
    settings.setValue("workspaces/version", 0)
    settings.sync()
    again = open_window(qapp, toy_behaviour_atlas, tmp_path, settings)
    assert again.workspaces._stored("Slices") is None
    again.workspaces.switch("Slices")
    assert again.dockWidgetArea(again.info_dock) == RIGHT
    again.close()


def test_lab_docks_live_only_in_the_lab(window):
    dock, calls = fake_lab(window)
    assert dock.isHidden() and not dock.toggleViewAction().isEnabled()
    window.workspaces.switch("Lab")
    assert dock.isVisible() and window.tree_dock.isHidden() and window.slice_dock.isHidden()
    assert calls == ["enter"]
    window.workspaces.switch("Explore")
    assert dock.isHidden() and calls == ["enter", "leave"]
    assert window.tree_dock.isVisible()


def test_switching_to_the_lab_leaves_an_active_route_and_quiz_locks_the_switcher(window):
    fake_lab(window)
    window.pathways.open("mood")
    assert window.pathway_active
    window.workspaces.switch("Lab")
    assert not window.pathway_active and window.workspaces.current == "Lab"
    window.workspaces.switch("Explore")
    window.enter_quiz()
    assert not window.workspaces.button("Slices").isEnabled()
    window.workspaces.switch("Slices")
    assert window.workspaces.current == "Explore"
    window.leave_quiz()
    assert window.workspaces.button("Slices").isEnabled()


def test_ctrl_numbers_switch_workspaces(qapp, window):
    window.activateWindow()
    QTest.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    qapp.processEvents()
    assert window.workspaces.current == "Slices"
    QTest.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    assert window.workspaces.current == "Explore"


def test_the_window_menu_lists_the_panels_and_reset(window):
    texts = [a.text() for a in window.window_menu.actions() if a.text()]
    assert {"Structures", "Pathways", "Slices", "Info"} <= set(texts)
    assert texts[-1] == "Reset layout"
