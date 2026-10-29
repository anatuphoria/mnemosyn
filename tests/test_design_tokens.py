import pytest

from cns_desktop.design import tokens
from cns_desktop.design.tokens import COLOURS, contrast

SURFACES = ("s0", "s1", "s2", "s3")
SIGNALS = ("accent_text", "edited", "raised", "lowered", "normal", "danger", "success")


def test_contrast_of_black_and_white_is_21():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#ffffff", "#000000") == pytest.approx(21.0)


def test_text_roles_reach_their_contrast():
    for role in ("text", "text2"):
        for surface in SURFACES:
            assert contrast(COLOURS[role], COLOURS[surface]) >= 4.5, (role, surface)
    for surface in ("s0", "s1", "s2"):
        assert contrast(COLOURS["text3"], COLOURS[surface]) >= 3.0, surface


def test_signals_reach_three_to_one_on_every_surface():
    for role in SIGNALS:
        for surface in SURFACES:
            assert contrast(COLOURS[role], COLOURS[surface]) >= 3.0, (role, surface)
    for surface in ("s0", "s1", "s2"):
        assert contrast(COLOURS["control"], COLOURS[surface]) >= 3.0, surface


def test_white_on_accent_is_readable():
    assert contrast("#ffffff", COLOURS["accent"]) >= 4.5


def test_data_palette_reads_on_panels():
    assert len(tokens.DATA_PALETTE) == 6
    assert len(set(tokens.DATA_PALETTE)) == 6
    for colour in tokens.DATA_PALETTE:
        assert contrast(colour, COLOURS["s1"]) >= 3.0, colour


def test_colours_match_the_black_variant():
    assert COLOURS == {
        "s0": "#000000", "s1": "#0a0a0c", "s2": "#131317", "s3": "#1c1c21",
        "line": "#202026", "control": "#6a6a75",
        "text": "#f2f2f2", "text2": "#b4b4bc", "text3": "#6e6e78",
        "accent": "#3d6fd6", "accent_text": "#6d98f2", "edited": "#e4b04e",
        "raised": "#f0955f", "lowered": "#7cb0ff", "normal": "#8a8a95",
        "danger": "#ec6f62", "success": "#5fbf8f",
    }


def test_type_ramp_and_spacing_match_the_spec():
    assert tokens.TYPE == {
        "title": (22, 28, 600), "heading": (15, 20, 600), "body": (13, 20, 400),
        "label": (13, 20, 500), "secondary": (12, 16, 400), "data": (11, 14, 500),
    }
    assert tokens.SPACE == (4, 8, 12, 16, 24, 32)
    assert tokens.RADIUS == {"small": 4, "control": 6, "panel": 8}
    size = tokens.SIZE
    assert (size["control"], size["row"], size["header"], size["status"]) == (28, 28, 40, 24)
    assert (size["lane"], size["chart_row"]) == (44, 56)
    assert (size["icon"], size["icon_header"], size["icon_empty"]) == (16, 14, 20)
    assert (size["panel_left"], size["panel_right"], size["central_min"]) == (248, 320, 480)
    assert size["narrow"] == 1100
    assert tokens.ICON_STROKE == 1.75


def test_color_gives_a_qcolor_for_a_role():
    pytest.importorskip("PySide6")
    assert tokens.color("accent").name() == "#3d6fd6"
    assert tokens.color("accent", 0.15).alphaF() == pytest.approx(0.15, abs=0.01)
