import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from cns_atlas import Atlas
from cns_desktop.design.tokens import SIZE
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.model_panel import HINT, NO_MATCH, NOTHING_DIRECT, ModelPanel
from cns_desktop.lab.setting_row import ValueBox, figures, value_text


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


@pytest.fixture
def panel(doc, qapp):
    made = ModelPanel(doc)
    made.resize(SIZE["panel_left"], 900)
    made.show()
    qapp.processEvents()
    yield made
    made.close()


def shown(panel, key):
    return panel.row(key).isVisibleTo(panel)


def test_numbers_read_cleanly():
    assert figures(0.0020000) == "0.002" and figures(18.98) == "18.98" and figures(93.0) == "93"
    assert figures(0.104167) == "0.1042" and figures(12345.6) == "12346"
    assert value_text(0.5, "fraction") == "50 %" and value_text(6.0, "number") == "6"
    assert value_text(3.0, "/min") == "3 /min"


def test_a_fraction_reads_and_takes_a_percentage(doc):
    p = doc.model.parameter("a")
    box = ValueBox(p)
    box.setValue(0.5)
    assert box.text() == "50"
    box.lineEdit().setText("25")
    box.interpretText()
    assert box.value() == pytest.approx(0.25)


def test_with_nothing_selected_or_changed_the_panel_says_how_to_use_the_context(panel):
    assert panel.hint.isVisibleTo(panel) and panel.hint.text() == HINT
    assert panel.context_heading() == "" and panel.context_keys() == []


def test_selecting_a_value_brings_its_settings_to_the_top(doc, panel):
    doc.select(("value", "y"))
    assert panel.context_heading() == "SHAPES Y" and panel.context_keys() == ["w"]
    assert not panel.hint.isVisibleTo(panel)
    doc.select(("value", "m"))
    assert panel.context_keys() == [] and panel.context_note.text() == NOTHING_DIRECT
    doc.select(None)
    assert panel.context_heading() == ""


def test_a_context_row_edits_the_same_value_as_its_group_row(doc, panel):
    doc.select(("value", "y"))
    row = panel._context_rows[0]
    row.committed.emit("w", 0.2)
    assert doc.experiment.value_map == {"w": 0.2}
    assert panel.row("w").field.value() == pytest.approx(0.2)
    assert panel._context_rows[0].reset.isVisibleTo(panel)


def test_with_changes_and_no_selection_the_top_lists_them_and_what_moved(doc, panel, qapp):
    doc.set_value("w", 0.3)
    assert panel.context_heading() == "YOUR CHANGES" and panel.context_keys() == ["w"]
    doc.set_playhead(240.0)
    qapp.processEvents()
    assert panel.moved.isVisibleTo(panel) and panel.moved.text().startswith("At ")


def test_search_shows_matching_rows_and_folds_nothing_away(doc, panel):
    name = panel.row_text("w")[0]
    panel.search.setText(name.split()[0])
    assert shown(panel, "w") and not shown(panel, "stress")
    assert all(g.is_shown_open() for g in panel.groups() if g.isVisibleTo(panel))
    panel.search.setText("zzzz")
    assert panel.no_match.isVisibleTo(panel) and panel.no_match.text() == NO_MATCH
    panel.search.clear()
    assert shown(panel, "stress") and not panel.no_match.isVisibleTo(panel)


def test_changed_only_keeps_the_edited_rows_and_counts_them(doc, panel):
    assert panel.changed_only.text() == "Changed" and not panel.changed_only.isEnabled()
    doc.set_value("w", 0.3)
    assert panel.changed_only.text() == "Changed 1"
    panel.changed_only.setChecked(True)
    assert shown(panel, "w") and not shown(panel, "stress") and not shown(panel, "k")
    panel.changed_only.setChecked(False)
    assert shown(panel, "stress")


def test_a_group_folds_counts_its_changes_and_stays_folded_after_a_rebuild(doc, panel):
    group = next(g for g in panel.groups() if g.title == "STRESS")
    group.header.click()
    assert not group.body.isVisibleTo(panel)
    panel.populate()
    group = next(g for g in panel.groups() if g.title == "STRESS")
    assert not group.is_shown_open()
    doc.set_value("w", 0.3)
    clearing = next(g for g in panel.groups() if g.title == "CLEARING")
    assert clearing.count.text() == "1 changed" and clearing.count.isVisibleTo(panel)


def test_a_name_unfolds_its_meaning_and_source(panel):
    row = panel.row("k")
    assert not row.details.isVisibleTo(panel)
    QTest.mouseClick(row.label, Qt.MouseButton.LeftButton)
    assert row.details.isVisibleTo(panel)
    assert "Where Y holds back half of X." in row.details.text()
    assert "Author A (2020)" in row.details.text()
    row.toggle.click()
    assert not row.details.isVisibleTo(panel)


def test_the_reset_icon_shows_only_for_a_changed_setting(doc, panel):
    assert not panel.reset_button("w").isVisibleTo(panel)
    doc.set_value("w", 0.3)
    assert panel.reset_button("w").isVisibleTo(panel)


def test_clicking_a_lane_name_selects_that_value(doc, qapp):
    from cns_desktop.lab.timeline import Timeline

    timeline = Timeline(doc)
    timeline.resize(900, 400)
    timeline.show()
    qapp.processEvents()
    rect = timeline.lane_rect("y")
    at = QPointF(20, rect.center().y()).toPoint()
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at)
    assert doc.selection == ("value", "y")
    timeline.close()
