import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLabel

from cns_desktop.design import stylesheet, theme, widgets
from cns_desktop.design.tokens import COLOURS, contrast


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


def colour_of(widget):
    widget.ensurePolished()
    return widget.palette().color(widget.foregroundRole()).name()


def test_segmented_control_switches_and_signals(qapp):
    control = widgets.SegmentedControl([("timeline", "Timeline"), ("charts", "Charts")])
    assert control.current() == "timeline"
    spy = QSignalSpy(control.changed)
    control.button("charts").click()
    assert control.current() == "charts"
    assert spy.count() == 1 and spy.at(0) == ["charts"]
    control.set_current("charts")
    assert spy.count() == 1
    control.set_current("timeline")
    assert spy.count() == 2
    assert control.button("timeline").isChecked() and not control.button("charts").isChecked()
    assert control.sizeHint().height() == 28


def test_segmented_control_works_from_the_keyboard(qapp):
    control = widgets.SegmentedControl([("a", "One"), ("b", "Two"), ("c", "Three")])
    assert control.focusPolicy() == Qt.FocusPolicy.StrongFocus
    QTest.keyClick(control, Qt.Key.Key_Right)
    QTest.keyClick(control, Qt.Key.Key_Right)
    assert control.current() == "c"
    QTest.keyClick(control, Qt.Key.Key_Right)
    assert control.current() == "c"
    QTest.keyClick(control, Qt.Key.Key_Left)
    assert control.current() == "b"


def test_segmented_control_can_show_icons(qapp):
    control = widgets.SegmentedControl([("brain", "Explore")], icons={"brain": "brain"})
    assert not control.button("brain").icon().isNull()


def test_icon_buttons_have_tooltips_with_shortcuts_and_a_visible_focus(qapp):
    action = QAction("&Frame selection")
    action.setShortcut(QKeySequence("F"))
    button = widgets.icon_button(action, "maximize")
    assert button.toolTip() == "Frame selection  F"
    assert not button.icon().isNull()
    assert (button.width(), button.height()) == (28, 28)
    assert button.iconSize().width() == 16
    assert button.focusPolicy() == Qt.FocusPolicy.TabFocus
    assert not action.isIconVisibleInMenu()
    action.setChecked(False)
    assert button.toolTip() == "Frame selection  F"
    rule = re.search(r"QToolButton:focus \{ border: 1px solid (#[0-9a-f]{6})", stylesheet.build())
    assert contrast(rule.group(1), COLOURS["s1"]) >= 3.0


def test_icon_buttons_without_a_shortcut_show_the_name(qapp):
    button = widgets.icon_button(QAction("Snapshot"), "camera")
    assert button.toolTip() == "Snapshot"


def test_panel_header_is_40_high_with_its_buttons(qapp):
    header = widgets.PanelHeader("Structures")
    hits = []
    button = header.add_button("ellipsis", "More", lambda: hits.append(1))
    assert header.sizeHint().height() == 40 and header.minimumHeight() == 40
    assert header.title.text() == "STRUCTURES"
    assert (button.width(), button.height()) == (24, 24)
    assert button.iconSize().width() == 14
    assert button.toolTip() == "More"
    button.click()
    assert hits == [1]


def test_panel_header_can_hold_tabs(qapp):
    tabs = widgets.SegmentedControl([("why", "Why"), ("inspector", "Inspector")])
    header = widgets.PanelHeader(tabs=tabs)
    assert header.tabs is tabs
    assert header.title.isHidden()


def test_search_field_has_an_icon_and_placeholder(qapp):
    field = widgets.SearchField("Find a structure  Ctrl+F")
    assert field.placeholderText() == "Find a structure  Ctrl+F"
    assert field.actions() and not field.actions()[0].icon().isNull()
    assert field.isClearButtonEnabled()


def test_elided_labels_keep_the_full_text_in_a_tooltip(qapp):
    label = QLabel()
    label.setFixedWidth(80)
    label.show()
    full = "Paraventricular nucleus of the hypothalamus"
    widgets.elided(label, full)
    assert label.text().endswith("…") and label.text() != full
    assert label.toolTip() == full
    label.setFixedWidth(1000)
    QApplication.processEvents()
    assert label.text() == full
    assert label.toolTip() == ""


def test_chips_use_role_colours(qapp):
    chip = widgets.chip("raises", "raised")
    assert colour_of(chip) == COLOURS["raised"]
    assert colour_of(widgets.chip("lowers", "lowered")) == COLOURS["lowered"]


def test_key_caps_use_the_data_style(qapp):
    cap = widgets.key_cap("Space")
    cap.ensurePolished()
    assert cap.font().pixelSize() == 11
    assert colour_of(cap) == COLOURS["text2"]


def test_cards_are_raised_surfaces(qapp):
    card = widgets.Card()
    card.ensurePolished()
    assert card.palette().color(card.backgroundRole()).name() == COLOURS["s2"]
