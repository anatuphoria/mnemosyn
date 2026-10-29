import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel, QTabBar

from cns_atlas import Atlas
from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import SIZE
from cns_desktop.main_window import MainWindow

NAMES = ("Explore", "Slices", "Pathways", "Lab")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def open_at(qapp, atlas, tmp_path, width, height):
    settings = QSettings(str(tmp_path / f"{width}.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.resize(width, height)
    w.show()
    for _ in range(3):
        w.resize(width, height)
        qapp.processEvents()
    qapp.processEvents()
    return w


def docked(window):
    return [g for g in window.findChildren(PanelGroup) if g.isVisible() and not g.isFloating()]


@pytest.mark.parametrize("size", [(850, 600), (1100, 700)])
def test_every_workspace_survives_a_small_window(qapp, toy_lab_atlas, tmp_path, size):
    window = open_at(qapp, toy_lab_atlas, tmp_path, *size)
    try:
        assert window.width() == size[0]
        for name in NAMES:
            window.workspaces.switch(name)
            qapp.processEvents()
            qapp.processEvents()
            groups = docked(window)
            for n, one in enumerate(groups):
                for other in groups[n + 1:]:
                    assert not one.geometry().intersects(other.geometry()), (name, one, other)
            view = window.viewport
            assert view.width() >= view.minimumWidth(), name
            assert view.width() > 0 and window.view.height() > 0, name
            assert not [b for b in window.findChildren(QTabBar) if b.isVisible()], name
            assert window.topbar.sizeHint().width() <= window.width(), name
            for label in window.findChildren(QLabel):
                if label.isVisible() and not label.wordWrap() and label.text():
                    parent = label.parentWidget()
                    assert label.geometry().right() <= parent.width() + 1, (name, label.text())
    finally:
        window.lab.document.undo.setClean()
        window.close()


def test_every_workspace_fills_a_large_window(qapp, toy_lab_atlas, tmp_path):
    window = open_at(qapp, toy_lab_atlas, tmp_path, 2560, 1440)
    try:
        window.workspaces.switch("Explore")
        qapp.processEvents()
        left, right = window.structures_group, window.info_group
        assert abs(left.width() - SIZE["panel_left"]) <= 24
        assert abs(right.width() - SIZE["panel_right"]) <= 24
        assert window.viewport.width() > 1800
        assert window.topbar.level == 0
        window.workspaces.switch("Lab")
        qapp.processEvents()
        assert abs(window.lab.time_group.height() - 1440 // 3) <= 80
    finally:
        window.lab.document.undo.setClean()
        window.close()
