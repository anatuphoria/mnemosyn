import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.theme import apply_theme
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def open_window(qapp, atlas, tmp_path, width=1400, height=900):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.show()
    for _ in range(3):
        w.resize(width, height)
        qapp.processEvents()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    w.close()


def test_an_idle_top_bar_stops_fitting(window, qapp):
    bar = window.topbar
    calls = []
    original = bar.fit
    bar.fit = lambda width=None: (calls.append(width), original(width))
    for _ in range(20):
        qapp.processEvents()
    calls.clear()
    for _ in range(20):
        qapp.processEvents()
    assert len(calls) <= 1


def test_the_stylesheet_survives_an_unwritable_icon_cache(monkeypatch):
    from cns_desktop.design import icons, stylesheet

    def refuse(*_args, **_kwargs):
        raise PermissionError("not yours")

    icons.file.cache_clear()
    icons._folder.cache_clear()
    stylesheet.build.cache_clear()
    monkeypatch.setattr(icons.tempfile, "mkdtemp", refuse)
    try:
        css = stylesheet.build()
        assert "QComboBox::down-arrow { image: none" in css
    finally:
        icons.file.cache_clear()
        icons._folder.cache_clear()
        stylesheet.build.cache_clear()


def test_icon_files_live_in_a_private_folder():
    import stat

    from cns_desktop.design import icons

    path = icons.file("chevron-down", "text2")
    folder = path.parent
    assert folder.name.startswith("mnemosyn-icons-")
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700


def resize_to(window, qapp, width, height):
    for _ in range(3):
        window.resize(width, height)
        qapp.processEvents()
    qapp.processEvents()


def test_a_closed_panel_stays_closed_across_a_narrow_window(window, qapp):
    window.info_group.close_button.click()
    resize_to(window, qapp, 1000, 800)
    assert window.structures_group.keys() == ["structures"]
    resize_to(window, qapp, 1400, 900)
    assert window.info_group.isHidden()


def test_a_panel_toggled_from_the_window_menu_counts_as_a_change(window, qapp):
    window.info_group.toggleViewAction().trigger()
    assert window.info_group.isHidden()
    resize_to(window, qapp, 1000, 800)
    assert window.info_group.isHidden()
    assert window.structures_group.keys() == ["structures"]


def _rule(css, selector):
    import re

    found = re.search(re.escape(selector) + r" \{([^}]*)\}", css)
    return found.group(1) if found else ""


def test_focused_primary_buttons_and_checkboxes_show_a_ring():
    import re

    from cns_desktop.design import stylesheet
    from cns_desktop.design.tokens import COLOURS, contrast

    css = stylesheet.build()
    primary = _rule(css, 'QPushButton[variant="primary"]:focus')
    colour = re.search(r"border: \d+px solid (#[0-9a-f]{6})", primary).group(1)
    assert contrast(colour, COLOURS["accent"]) >= 3.0
    box = _rule(css, "QCheckBox::indicator:focus")
    colour = re.search(r"border: \d+px solid (#[0-9a-f]{6})", box).group(1)
    assert contrast(colour, COLOURS["control"]) >= 3.0


def test_closing_the_window_stops_the_lab(qapp, toy_lab_atlas, tmp_path, capfd):
    import time

    w = open_window(qapp, toy_lab_atlas, tmp_path)
    w.workspaces.switch("Lab")
    w.lab.play()
    assert w.lab.timer.isActive()
    w.lab.document.undo.setClean()
    w.close()
    assert not w.lab.playing and not w.lab.timer.isActive()
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        qapp.processEvents()
    assert "already deleted" not in capfd.readouterr().err


def test_menu_items_are_centred_in_the_top_bar(window, qapp):
    from PySide6.QtCore import QRectF

    bar = window.topbar
    middle = (bar.height() - 1) / 2

    def centre_of(widget, rect):
        box = QRectF(rect)
        return widget.mapTo(bar, box.topLeft().toPoint()).y() + box.height() / 2

    for action in bar.menus.actions():
        if action.isVisible():
            centre = centre_of(bar.menus, bar.menus.actionGeometry(action))
            assert abs(centre - middle) <= 1.0, (action.text(), centre, middle)
    for widget in (bar.mark, bar.switch):
        assert abs(centre_of(widget, widget.rect()) - middle) <= 1.0, widget


def test_the_top_bar_mark_is_one_greek_key_in_the_accent_role(window, qapp):
    from cns_desktop.design.brand import KeyMark
    from cns_desktop.design.tokens import COLOURS

    mark = window.topbar.mark
    assert isinstance(mark, KeyMark)
    assert (mark.width(), mark.height()) == (20, 20)
    assert mark.role == "accent"
    assert mark.toolTip() == "Mnemosyn"

    def ink(widget):
        image = widget.grab().toImage()
        best = max((image.pixelColor(x, y) for x in range(image.width())
                    for y in range(image.height())),
                   key=lambda c: abs(c.red() - c.blue()) + c.lightness())
        return best

    colour = ink(mark)
    want = QColor(COLOURS["accent"])
    assert abs(colour.red() - want.red()) < 24 and abs(colour.blue() - want.blue()) < 24
    mark.set_role("text")
    colour = ink(mark)
    assert colour.lightness() > 200


def test_tree_branches_show_chevrons():
    from cns_desktop.design import stylesheet

    css = stylesheet.build()
    assert "QTreeView::branch:has-children:!has-siblings:closed" in css or \
        "QTreeView::branch:has-children:closed" in css
    assert "chevron-right" in css and "chevron-down" in css
