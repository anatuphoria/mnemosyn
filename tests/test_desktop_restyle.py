import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import DISCLAIMER, Atlas
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import COLOURS, TYPE
from cns_desktop.design.widgets import SearchField
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def window(qapp, toy_behaviour_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_behaviour_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def test_long_names_end_in_an_ellipsis_with_a_tooltip(window, qapp):
    tree = window.tree.tree
    assert tree.textElideMode() == Qt.TextElideMode.ElideRight
    assert tree.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    for structure_id, item in window.tree.items.items():
        assert item.toolTip(0) == window.state.atlas.get(structure_id).name


def test_the_tree_uses_a_search_field(window):
    box = window.tree.filter_box
    assert isinstance(box, SearchField)
    assert box.placeholderText() == "Find a structure  Ctrl+F"


def test_the_info_title_uses_the_title_style(window):
    css = window.info.document().defaultStyleSheet()
    size, _line, weight = TYPE["title"]
    assert re.search(rf"h2 \{{[^}}]*font-size: {size}px; font-weight: {weight}", css)
    assert re.search(r"h4 \{[^}]*color: " + COLOURS["text2"], css)
    html = window.info.html_for(101)
    assert "&#9632;&nbsp;" in html


def test_the_disclaimer_is_quiet_not_red(window):
    html = window.info.html_for(101)
    assert "#c55" not in html
    card = re.search(r"<table[^>]*bgcolor='(#[0-9a-f]{6})'[^>]*>.*?</table>", html, re.DOTALL)
    assert card and card.group(1) == COLOURS["s2"]
    assert DISCLAIMER.split(".")[0] in card.group(0)
    assert COLOURS["text2"] in card.group(0)


def test_the_draft_note_is_a_chip(window):
    html = window.info.html_for(101)
    if "not yet reviewed" in html:
        assert re.search(r"color: " + COLOURS["edited"] + r"[^>]*>Draft<", html)


def test_pathway_sides_and_controls_use_the_shared_widgets(window, qapp):
    from cns_desktop.design.widgets import SegmentedControl
    from cns_desktop.views.pathway_panel import PAUSE_TIP, PLAY_TIP, RELAY_COLOR

    panel = window.pathways
    assert isinstance(panel.side_control, SegmentedControl)
    assert panel.side_control.keys() == ["left", "right"]
    assert (PLAY_TIP, PAUSE_TIP) == ("Play  Space", "Pause  Space")
    assert panel.back_button.toolTip() == "Back  Left"
    assert panel.next_button.toolTip() == "Next  Right"
    assert RELAY_COLOR.name() == COLOURS["normal"]
    header = panel.choices.item(0)
    assert header.font().capitalization() == header.font().Capitalization.AllUppercase
    assert header.font().pixelSize() == TYPE["data"][0]
    assert panel.leave_button.text() == "Leave pathway"
    assert panel.leave_button.toolTip() == "Leave pathway  Esc"
    assert panel.title.property("role") == "heading"
    assert panel.start.property("role") == "secondary"


def test_quiz_and_dialog_buttons_use_the_button_variants(window, qapp):
    from cns_desktop.views import quiz_panel
    from cns_desktop.views.quiz_setup import QuizSetup

    quiz = window.quiz
    assert quiz.end_button.text() == "End quiz" and quiz.end_button.toolTip() == "Esc"
    assert quiz.reveal_button.text() == "Show the description"
    assert quiz.reveal_button.toolTip() == "Space"
    assert quiz.reveal_button.property("variant") == "primary"
    assert quiz.end_button.property("variant") == "ghost"
    assert COLOURS["success"] in quiz_panel.RIGHT and COLOURS["danger"] in quiz_panel.WRONG
    setup = QuizSetup(window.state.atlas, window.progress_store(), window)
    start = setup.buttons.button(setup.buttons.StandardButton.Ok)
    assert start.text() == "Start" and start.property("variant") == "primary"
    setup.reject()


def test_progress_lists_use_no_dashes(window, qapp):
    from cns_desktop.views.progress_dialog import ProgressDialog

    dialog = ProgressDialog(window.state.atlas, window.progress_store(), window)
    rows = [dialog.weakest.item(i).text() for i in range(dialog.weakest.count())]
    assert not any(" - " in row for row in rows)
    assert dialog.heading.property("role") == "heading"
    dialog.reject()
