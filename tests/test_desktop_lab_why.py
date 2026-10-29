import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.inspector import Inspector
from cns_desktop.lab.why_panel import WhyPanel, time_heading


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def test_the_chain_appears_numbered_with_sources(doc):
    panel = WhyPanel(doc)
    doc.add_block("remove_b", 0.0)
    doc.set_playhead(240.0)
    text = panel.toPlainText()
    assert "Remove the gland" in text and "Takes the gland away." in text
    assert "Y holds back the making of X [1]." in text and "Y falls to 0% of normal." in text
    assert "References" in text and "Author A" in text
    assert text.rstrip().endswith("Draft: not yet reviewed.")


def test_no_changes_shows_the_normal_note(doc):
    panel = WhyPanel(doc)
    assert "X rises in the morning [1]." in panel.toPlainText()
    doc.set_playhead(15 * 60.0)
    assert "X rises in the morning" not in panel.toPlainText()


def test_edited_values_are_listed(doc):
    panel = WhyPanel(doc)
    doc.set_value("k", 3.0)
    assert "Feedback halfway point is 3 model units (normal 1)." in panel.toPlainText()


def test_an_error_replaces_the_chain(doc):
    panel = WhyPanel(doc)
    doc.error = "The model cannot settle with these values."
    doc.run = None
    panel.refresh()
    assert panel.toPlainText().startswith("The model cannot settle with these values.")


def test_the_heading_names_the_time_and_the_last_change(doc):
    doc.add_block("pill", 120.0)
    doc.set_option(0, "dose", 2.0)
    assert time_heading(doc, 160.0) == "At 2 h 40 min, 40 min after Y pill 2 units"
    assert time_heading(doc, 60.0) == "At 1 h"
    doc.set_length(3 * 1440.0)
    assert time_heading(doc, 2 * 1440.0 + 380.0) == "At day 3, 14:20, 2 d 4 h after Y pill 2 units"


def test_inspector_edits_a_block_option_as_one_undo_step(doc):
    inspector = Inspector(doc)
    doc.add_block("pill", 120.0)
    doc.select(("block", 0))
    spin = inspector.option_spin("dose")
    spin.setValue(4.0)
    spin.editingFinished.emit()
    assert doc.experiment.blocks[0].option_map == {"dose": 4.0} and doc.undo.count() == 2
    start = inspector.start_spin()
    start.setValue(3.0)
    start.editingFinished.emit()
    assert doc.experiment.blocks[0].start == 180.0


def test_inspector_switches_a_condition_to_a_time(doc):
    inspector = Inspector(doc)
    doc.add_block("remove_b", 0.0)
    doc.select(("block", 0))
    inspector.mode_box().setCurrentIndex(1)
    assert doc.experiment.blocks[0].mode == "from a time"


def test_a_test_block_shows_its_result(doc):
    inspector = Inspector(doc)
    doc.add_block("pill_test", 120.0)
    doc.select(("block", 0))
    text = inspector.text()
    assert "Y suppression test" in text
    assert "Normal:" in text and "below 10.8 ng/mL" in text


def test_a_part_shows_its_values_and_sources(doc):
    inspector = Inspector(doc)
    doc.select(("part", "a"))
    text = inspector.text()
    assert "Alpha" in text and "X:" in text and "ng/mL" in text and "normal 5 to 15" in text
    assert "Author A (2020)" in text


def test_a_link_shows_its_text_and_strength(doc):
    inspector = Inspector(doc)
    doc.add_block("remove_b", 0.0)
    doc.select(("link", "fb"))
    text = inspector.text()
    assert "Y holds back the making of X" in text and "times normal" in text


def test_return_and_tab_in_inspector_fields_apply_without_crashing(qapp, doc):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    inspector = Inspector(doc)
    inspector.show()
    doc.add_block("pill", 120.0)
    doc.select(("block", 0))
    qapp.processEvents()
    spin = inspector.option_spin("dose")
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, "5")
    QTest.keyClick(spin, Qt.Key.Key_Return)
    qapp.processEvents()
    assert doc.experiment.blocks[0].option_map == {"dose": 5.0}
    assert inspector.option_spin("dose") is spin
    start = inspector.start_spin()
    start.setFocus()
    start.selectAll()
    QTest.keyClicks(start, "4")
    QTest.keyClick(start, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert doc.experiment.blocks[0].start == 240.0 and inspector.start_spin() is start
    doc.select(None)
    qapp.processEvents()
    title = inspector.title_box()
    title.setFocus()
    QTest.keyClicks(title, "x")
    QTest.keyClick(title, Qt.Key.Key_Return)
    qapp.processEvents()
    assert doc.experiment.title == "x" and inspector.title_box() is title
    inspector.close()


def test_an_edited_value_is_explained_not_the_normal_day(doc):
    panel = WhyPanel(doc)
    doc.set_value("a", 0.9)
    text = panel.toPlainText()
    assert "X rises in the morning" not in text
    assert "The body clock drives X." in text
