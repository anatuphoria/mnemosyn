import re

import pytest
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QLabel, QLineEdit,
                               QPushButton, QSpinBox)

from cns_desktop.design import stylesheet, theme
from cns_desktop.design.tokens import COLOURS


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


def test_the_stylesheet_uses_only_token_colours():
    found = set(re.findall(r"#[0-9a-fA-F]{6}\b", stylesheet.build()))
    assert found
    assert found <= set(COLOURS.values())


def test_the_stylesheet_is_applied_once(qapp):
    assert theme.is_applied(qapp)
    assert qapp.styleSheet() == stylesheet.build()


def test_controls_are_28_high(qapp):
    combo = QComboBox()
    combo.addItems(["1 day", "8 weeks"])
    for widget in (QLineEdit(), combo, QDoubleSpinBox(), QSpinBox(), QPushButton("Run")):
        widget.ensurePolished()
        assert widget.sizeHint().height() == 28, type(widget).__name__


def test_the_app_font_is_inter_13(qapp):
    font = qapp.font()
    assert font.family() == "Inter"
    assert font.pixelSize() == 13


def test_selected_rows_use_the_accent():
    css = stylesheet.build()
    assert re.search(r"::item:selected[^}]*border-left: 2px solid " + COLOURS["accent"], css)


def test_text_roles_set_size_and_colour(qapp):
    label = QLabel("Cortisol")
    theme.set_role(label, "secondary")
    label.ensurePolished()
    assert label.font().pixelSize() == 12
    assert label.palette().color(label.foregroundRole()).name() == COLOURS["text2"]
    theme.set_role(label, "heading")
    assert label.font().pixelSize() == 15
    assert label.palette().color(label.foregroundRole()).name() == COLOURS["text"]
