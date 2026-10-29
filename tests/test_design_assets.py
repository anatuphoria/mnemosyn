from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from cns_desktop.design import fonts, icons, tokens

RESOURCES = Path(__file__).resolve().parents[1] / "cns_desktop" / "resources"
SPEC_ICONS = ["brain", "layers-2", "route", "flask-conical", "eye-off", "scan", "eye", "waypoints", "rotate-ccw", "maximize", "crosshair", "graduation-cap", "info", "play", "pause", "skip-back", "undo-2", "redo-2", "git-compare-arrows", "camera", "activity", "clock-3", "scissors", "unlink", "pill", "calendar-days", "heart-pulse", "zap", "test-tube", "search", "ellipsis", "chevron-right", "chevron-down", "check", "zoom-in", "zoom-out", "network"]


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_inter_is_registered_once(qapp):
    assert fonts.load_fonts() == "Inter"
    count = len(QFontDatabase.styles("Inter"))
    assert fonts.load_fonts() == "Inter"
    assert len(QFontDatabase.styles("Inter")) == count
    assert {"Regular", "Medium", "SemiBold"} <= set(QFontDatabase.styles("Inter"))


def test_font_roles_have_the_ramp_sizes_and_tabular_figures(qapp):
    for role, (size, _line, weight) in tokens.TYPE.items():
        font = fonts.font(role)
        assert font.family() == "Inter"
        assert font.pixelSize() == size
        assert font.weight() == QFont.Weight(weight)
        assert font.featureValue(QFont.Tag("tnum")) == 1


def test_every_icon_name_has_a_file():
    assert set(SPEC_ICONS) <= set(icons.NAMES)
    for name in icons.NAMES:
        assert (RESOURCES / "icons" / f"{name}.svg").is_file(), name


def test_icons_are_tinted_with_the_role_colour(qapp):
    image = icons.pixmap("maximize", "accent_text", 32).toImage()
    best = max((image.pixelColor(x, y) for x in range(image.width())
                for y in range(image.height())), key=lambda c: c.alpha())
    want = tokens.color("accent_text")
    assert best.alpha() > 200
    assert abs(best.red() - want.red()) <= 10
    assert abs(best.green() - want.green()) <= 10
    assert abs(best.blue() - want.blue()) <= 10


def test_icons_have_both_resolutions(qapp):
    sizes = icons.icon("play", "text2", 16).availableSizes()
    assert {(s.width(), s.height()) for s in sizes} >= {(16, 16), (32, 32)}


def test_unknown_icons_are_an_error(qapp):
    with pytest.raises(KeyError):
        icons.icon("no-such-icon")


def test_licences_ship_with_the_assets():
    assert "SIL Open Font License" in (RESOURCES / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "ISC License" in (RESOURCES / "icons" / "LICENSE").read_text(encoding="utf-8")


def test_the_about_box_names_inter_and_lucide():
    from cns_desktop.views.about_dialog import BUILT_WITH

    assert "Inter" in BUILT_WITH and "SIL Open Font License" in BUILT_WITH
    assert "Lucide" in BUILT_WITH and "ISC" in BUILT_WITH


def test_icon_files_are_tinted_copies_for_the_stylesheet():
    path = icons.file("chevron-down", "text2")
    text = path.read_text(encoding="utf-8")
    assert tokens.COLOURS["text2"] in text and "currentColor" not in text
    assert icons.file("chevron-down", "text2") == path
