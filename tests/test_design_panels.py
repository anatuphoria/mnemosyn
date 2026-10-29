import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabBar, QWidget

from cns_desktop.design import theme
from cns_desktop.design.panels import PanelGroup


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


@pytest.fixture
def window(qapp):
    win = QMainWindow()
    win.setCentralWidget(QWidget())
    win.resize(1000, 700)
    yield win
    win.close()
    win.deleteLater()


def group(window, name, pages, area=Qt.DockWidgetArea.RightDockWidgetArea):
    panel = PanelGroup(name, [(key, label, QLabel(label)) for key, label in pages], window)
    window.addDockWidget(area, panel)
    return panel


def test_a_group_shows_one_page_at_a_time(window):
    panel = group(window, "Lab time", [("timeline", "Timeline"), ("charts", "Charts")])
    window.show()
    spy = QSignalSpy(panel.page_changed)
    assert panel.keys() == ["timeline", "charts"]
    assert panel.current() == "timeline"
    assert panel.page("timeline").isVisible() and not panel.page("charts").isVisible()
    panel.show_page("charts")
    assert panel.current() == "charts" and panel.header.tabs.current() == "charts"
    assert panel.page("charts").isVisible() and not panel.page("timeline").isVisible()
    assert spy.count() == 1 and spy.at(0) == ["charts"]
    panel.header.tabs.set_current("timeline")
    assert panel.current() == "timeline"


def test_one_page_groups_show_a_title_not_tabs(window):
    panel = group(window, "Structures", [("structures", "Structures")])
    window.show()
    assert panel.titleBarWidget() is panel.header
    assert panel.header.title.isVisible() and panel.header.title.text() == "STRUCTURES"
    assert not panel.header.tabs.isVisible()


def test_the_header_floats_and_closes_the_dock(window):
    panel = group(window, "Info", [("info", "Info")])
    window.show()
    panel.float_button.click()
    assert panel.isFloating()
    panel.float_button.click()
    assert not panel.isFloating()
    panel.close_button.click()
    assert panel.isHidden()


def test_buttons_follow_the_dock_features(window):
    panel = group(window, "Quiz", [("quiz", "Quiz")])
    panel.setFeatures(PanelGroup.DockWidgetFeature.DockWidgetMovable)
    window.show()
    assert not panel.close_button.isVisible() and not panel.float_button.isVisible()


def test_a_group_has_no_tab_bar_of_its_own(window):
    group(window, "Info", [("info", "Info"), ("slices", "Slices")])
    group(window, "Lab explain", [("why", "Why"), ("inspector", "Inspector")])
    window.show()
    assert not [bar for bar in window.findChildren(QTabBar) if bar.isVisible()]


def test_dragging_the_header_still_floats_the_dock(window):
    panel = group(window, "Info", [("info", "Info")])
    window.show()
    QTest.qWaitForWindowExposed(window)
    title = panel.header.title
    start = title.rect().center()
    QTest.mousePress(title, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        QTest.mouseMove(title, start + QPoint(0, step * 10))
    QTest.mouseRelease(title, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       start + QPoint(0, 80))
    assert panel.isFloating()


def test_joining_moves_pages_and_release_gives_them_back(window):
    info = group(window, "Info", [("info", "Info")])
    slices = group(window, "Slices", [("slices", "Slices")])
    window.show()
    page = slices.page("slices")
    info.join(slices)
    assert info.keys() == ["info", "slices"]
    assert info.joined() == [slices]
    assert slices.isHidden()
    assert info.header.tabs.isVisible() and not info.header.title.isVisible()
    info.show_page("slices")
    assert page.isVisible()
    info.release(slices)
    assert info.keys() == ["info"] and slices.keys() == ["slices"]
    assert slices.page("slices") is page and PanelGroup.of(page) is slices
    assert info.isVisible() and slices.isVisible()
    assert info.current() == "info"
    assert info.header.title.isVisible()


def test_a_joined_page_can_be_raised_through_its_widget(window):
    info = group(window, "Info", [("info", "Info")])
    slices = group(window, "Slices", [("slices", "Slices")])
    window.show()
    page = slices.page("slices")
    info.join(slices)
    assert PanelGroup.of(page) is info
    info.hide()
    slices.reveal("slices")
    assert info.isVisible() and info.current() == "slices" and page.isVisible()
    assert slices.isHidden()


def test_joining_twice_or_joining_itself_does_nothing(window):
    info = group(window, "Info", [("info", "Info")])
    slices = group(window, "Slices", [("slices", "Slices")])
    info.join(slices)
    info.join(slices)
    info.join(info)
    assert info.keys() == ["info", "slices"]
