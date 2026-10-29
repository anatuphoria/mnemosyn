import random

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMenuBar, QTabBar, QToolBar

from cns_atlas import Atlas
from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.topbar import TopBar
from cns_desktop.main_window import MainWindow
from cns_study.session import QuizChoice

LEFT, RIGHT = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
BOTTOM = Qt.DockWidgetArea.BottomDockWidgetArea


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def settings_at(path):
    return QSettings(str(path / "settings.ini"), QSettings.Format.IniFormat)


def open_window(qapp, atlas, tmp_path, size=(1400, 900), settings=None):
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings if settings is not None else settings_at(tmp_path))
    w.resize(*size)
    w.show()
    qapp.processEvents()
    return w


def resize_to(window, qapp, width, height):
    for _ in range(3):
        window.resize(width, height)
        qapp.processEvents()
    qapp.processEvents()


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def visible_groups(window):
    return {g.objectName(): window.dockWidgetArea(g) for g in window.findChildren(PanelGroup)
            if g.isVisible()}


def menu_names(window):
    return [a.text() for a in window.topbar.menus.actions() if a.isVisible()]


def test_the_top_bar_holds_menus_actions_and_the_switch(window):
    assert isinstance(window.menuWidget(), TopBar)
    assert window.topbar.menus.parent() is window.topbar
    assert window.findChildren(QToolBar) == []
    assert [m for m in window.findChildren(QMenuBar) if m is not window.topbar.menus] == []
    switch = window.workspaces.switcher
    assert switch.parent() is window.topbar
    assert switch.keys() == ["Explore", "Slices", "Pathways", "Lab"]
    group = window.topbar.group("Explore")
    tips = [b.toolTip() for b in group.findChildren(type(window.workspaces.button("Lab")))]
    assert tips == ["Hide  H", "Isolate  I", "Show all  U", "Tracts  T", "Start quiz  Q"]
    assert group.isVisible() and not window.topbar.group("Lab").isVisible()


def test_menus_are_file_edit_view_study_experiment_window_help(window):
    assert menu_names(window) == ["File", "Edit", "View", "Study", "Window", "Help"]
    window.workspaces.switch("Lab")
    assert menu_names(window) == ["File", "Edit", "View", "Study", "Experiment", "Window", "Help"]
    assert window.topbar.group("Lab").isVisible()
    assert not window.topbar.group("Explore").isVisible()
    view = [a.text() for a in window.topbar.menu("View").actions() if a.text()]
    assert view == ["Hide", "Isolate", "Show all", "Tracts", "Reset view", "Frame selection",
                    "Centre slice"]
    help_items = [a.text() for a in window.topbar.menu("Help").actions()]
    assert help_items == ["About Mnemosyn", "Guide on the website"]


def test_explore_has_no_pathways_panel(window):
    assert window.routes_group.isHidden()
    assert "Pathways" not in visible_groups(window)
    window.workspaces.switch("Pathways")
    assert window.routes_group.isVisible()


def test_each_workspace_opens_with_its_groups(window):
    assert visible_groups(window) == {"Structures": LEFT, "Info": RIGHT}
    assert window.info_group.keys() == ["info", "slices"]
    window.workspaces.switch("Slices")
    assert visible_groups(window) == {"Structures": LEFT, "Slices": RIGHT, "Info": RIGHT}
    window.workspaces.switch("Pathways")
    assert visible_groups(window) == {"Pathways": LEFT, "Info": RIGHT}
    assert window.info_group.keys() == ["info", "slices"]
    window.workspaces.switch("Lab")
    assert visible_groups(window) == {"Lab tools": LEFT, "Lab explain": RIGHT, "Lab time": BOTTOM}


def test_the_lab_uses_three_panel_groups(window):
    lab = window.lab
    assert [g.objectName() for g in lab.docks] == ["Lab tools", "Lab explain", "Lab time"]
    assert lab.tools_group.keys() == ["experiments", "model"]
    assert lab.explain_group.keys() == ["why", "inspector"]
    assert lab.time_group.keys() == ["timeline", "charts"]
    assert lab.dock("Charts") is lab.time_group
    window.workspaces.switch("Lab")
    lab.show_chart()
    assert lab.time_group.current() == "charts" and lab.charts.isVisible()


def test_slices_shows_the_slice_view_and_info_side_by_side(window, qapp):
    window.workspaces.switch("Slices")
    qapp.processEvents()
    slices, info = window.slices_group, window.info_group
    assert slices.isVisible() and info.isVisible()
    assert slices.keys() == ["slices"] and info.keys() == ["info"]
    assert slices.geometry().right() < info.geometry().left()
    assert slices.width() > info.width()


def test_shortcuts_work_in_every_workspace_as_before(window, qapp):
    hits = []
    window.state.visibility_changed.connect(lambda _ids: hits.append("visibility"))
    window.view.reset_view = lambda: hits.append("reset")
    window.shortcuts["Reset view"].triggered.disconnect()
    window.shortcuts["Reset view"].triggered.connect(window.view.reset_view)
    for name in ("Explore", "Slices", "Pathways"):
        window.workspaces.switch(name)
        window.activateWindow()
        hits.clear()
        QTest.keyClick(window, Qt.Key.Key_T)
        QTest.keyClick(window, Qt.Key.Key_R)
        qapp.processEvents()
        assert "visibility" in hits and "reset" in hits, name


def test_floating_closing_and_restoring_a_panel_leaves_nothing_behind(window, qapp):
    info = window.info_group
    info.setFloating(True)
    qapp.processEvents()
    info.close()
    info.toggleViewAction().trigger()
    assert info.isVisible()
    for name in ("Slices", "Explore", "Pathways", "Explore"):
        window.workspaces.switch(name)
        qapp.processEvents()
        assert not [bar for bar in window.findChildren(QTabBar) if bar.isVisible()]
        headers = [g.header for g in window.findChildren(PanelGroup) if g.isVisible()]
        assert len(headers) == len({id(h) for h in headers})
        assert all(g.keys() for g in window.findChildren(PanelGroup) if g.isVisible())


def test_no_tab_bar_is_ever_visible_in_the_window(window, qapp):
    for name in ("Explore", "Slices", "Pathways", "Lab", "Explore"):
        window.workspaces.switch(name)
        qapp.processEvents()
        assert not [bar for bar in window.findChildren(QTabBar) if bar.isVisible()], name


def test_an_old_layout_is_replaced_by_the_new_defaults(qapp, toy_lab_atlas, tmp_path):
    settings = settings_at(tmp_path)
    settings.setValue("workspaces/version", 1)
    settings.setValue("workspaces/Explore", b"not a layout from this version")
    settings.sync()
    w = open_window(qapp, toy_lab_atlas, tmp_path, settings=settings)
    assert w.workspaces._stored("Explore") is None
    assert visible_groups(w) == {"Structures": LEFT, "Info": RIGHT}
    w.lab.document.undo.setClean()
    w.close()


def test_a_quiz_opens_its_panel_in_any_workspace(window, qapp):
    for name in ("Slices", "Pathways"):
        window.workspaces.switch(name)
        window.start_quiz(QuizChoice("find", "structures", None, False), rng=random.Random(1))
        qapp.processEvents()
        assert window.workspaces.current == name
        assert window.quiz_group.isVisible() and window.slices.isVisible()
        assert not window.info.isVisible()
        window.quiz.stop()
        window.leave_quiz()
        qapp.processEvents()
        assert not window.quiz_group.isVisible()
        if name == "Pathways":
            assert window.info_group.keys() == ["info", "slices"]


def test_a_narrow_first_start_joins_the_right_panel_into_the_left(qapp, toy_lab_atlas,
                                                                  tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path, size=(1000, 700))
    assert w.structures_group.keys() == ["structures", "info", "slices"]
    assert visible_groups(w) == {"Structures": LEFT}
    w.workspaces.switch("Lab")
    assert w.lab.time_group.keys() == ["timeline", "charts", "why", "inspector"]
    w.workspaces.switch("Explore")
    w.close()
    again = open_window(qapp, toy_lab_atlas, tmp_path, size=(1000, 700))
    again.structures_group.release_all()
    again.workspaces.save()
    again.close()
    third = open_window(qapp, toy_lab_atlas, tmp_path, size=(1000, 700))
    assert third.structures_group.keys() == ["structures"]
    third.lab.document.undo.setClean()
    third.close()


def test_joins_survive_a_restart(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    w.info_group.release_all()
    w.structures_group.join(w.slices_group)
    w.close()
    again = open_window(qapp, toy_lab_atlas, tmp_path)
    assert again.structures_group.keys() == ["structures", "slices"]
    assert again.info_group.keys() == ["info"]
    again.lab.document.undo.setClean()
    again.close()


def test_the_status_bar_shows_key_caps(window, qapp):
    def caps():
        return [label.text() for label in window.status_keys.findChildren(QLabel)
                if label.property("keycap") == "true" and not label.isHidden()]

    window._update_status()
    assert caps() == ["F", "H", "I", "Q"]
    window.workspaces.switch("Lab")
    window._update_status()
    qapp.processEvents()
    assert caps() == ["Space", "V", "Del"]
    assert window.statusBar().height() == 24


def test_a_window_made_narrow_after_opening_gets_the_narrow_defaults(window, qapp):
    assert window.structures_group.keys() == ["structures"]
    resize_to(window, qapp, 900, 800)
    assert window.structures_group.keys() == ["structures", "info", "slices"]
    resize_to(window, qapp, 1400, 900)
    assert window.structures_group.keys() == ["structures"]
    assert window.info_group.keys() == ["info", "slices"]


def test_a_layout_the_person_changed_is_never_rearranged(window, qapp):
    window.addDockWidget(LEFT, window.info_group)
    qapp.processEvents()
    resize_to(window, qapp, 900, 800)
    assert window.structures_group.keys() == ["structures"]
    assert window.dockWidgetArea(window.info_group) == LEFT


def test_the_top_bar_compacts_step_by_step(window, qapp):
    bar = window.topbar
    assert bar.menus.isVisible() and not bar.menu_button.isVisible()
    button = window.workspaces.button("Slices")
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    resize_to(window, qapp, 900, 800)
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert bar.sizeHint().width() <= 900
    window.workspaces.switch("Lab")
    qapp.processEvents()
    qapp.processEvents()
    assert not bar.menus.isVisible() and bar.menu_button.isVisible()
    titles = [a.text() for a in bar.menu_button.menu().actions() if a.isVisible()]
    assert titles == ["File", "Edit", "View", "Study", "Experiment", "Window", "Help"]
    assert bar.mark.isVisible()
    assert bar.sizeHint().width() <= 900


def test_the_lab_top_bar_fits_a_narrow_window(window, qapp):
    resize_to(window, qapp, 850, 800)
    window.workspaces.switch("Lab")
    qapp.processEvents()
    assert window.topbar.sizeHint().width() <= 850
    for box in (window.lab.speed_box, window.lab.length_box):
        assert box.width() >= box.minimumSizeHint().width()


def test_long_status_text_is_cut_with_a_tooltip(window, qapp):
    resize_to(window, qapp, 850, 800)
    status = window.status
    status.setText("selected: " + "Paraventricular nucleus of the hypothalamus " * 4)
    qapp.processEvents()
    assert status.text().startswith("selected:")
    assert status.shown_text().endswith("…") and status.toolTip() == status.text()


def test_the_top_bar_never_squeezes_its_pickers(window, qapp):
    for width in (1440, 1250, 1000, 850):
        resize_to(window, qapp, width, 800)
        for name in ("Explore", "Lab"):
            window.workspaces.switch(name)
            qapp.processEvents()
            qapp.processEvents()
            bar = window.topbar
            assert bar.sizeHint().width() <= bar.width(), (width, name)
            box = window.lab.system_box
            if name == "Lab":
                assert box.width() >= box.sizeHint().width(), (width, name)
