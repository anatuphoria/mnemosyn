import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import TYPE
from cns_desktop.design.widgets import SearchField
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.experiments_panel import ExperimentsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def test_experiments_have_icons_and_a_search(doc, qapp):
    page = ExperimentsPage(doc)
    panel = page.panel
    assert isinstance(page.search, SearchField)
    assert page.search.placeholderText() == "Find an experiment"
    for key in ("pill", "stress", "pill_test"):
        assert not panel.item_for(key).icon(0).isNull()
    group = panel.topLevelItem(0)
    assert group.font(0).pixelSize() == TYPE["data"][0]
    assert group.font(0).capitalization() == group.font(0).Capitalization.AllUppercase
    page.search.setText("pill")
    visible = [panel.topLevelItem(i).text(0) for i in range(panel.topLevelItemCount())
               if not panel.topLevelItem(i).isHidden()]
    assert visible == ["Drugs"]
    assert not panel.item_for("pill").isHidden() and panel.item_for("stress").isHidden()
    page.search.clear()
    assert not panel.item_for("stress").isHidden()


def test_long_experiment_names_get_a_tooltip(doc, qapp):
    panel = ExperimentsPage(doc).panel
    item = panel.item_for("pill")
    assert item.toolTip(0).startswith(item.text(0) + "\n")
    assert panel.textElideMode() == Qt.TextElideMode.ElideRight
    assert panel.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_the_main_option_shows_beside_the_name(doc, qapp):
    panel = ExperimentsPage(doc).panel
    assert panel.item_for("pill").text(1) == "1 units"
    assert panel.item_for("remove_b").text(1) == ""


def test_timeline_lanes_name_their_unit(doc, qapp):
    from cns_desktop.design.tokens import COLOURS, DATA_PALETTE, SIZE
    from cns_desktop.lab import timeline as module

    assert module.LABEL_WIDTH == 150 and module.LANE_HEIGHT == SIZE["lane"]
    assert module.CHANGES_HEIGHT == SIZE["lane"] and module.RULER_HEIGHT == 24
    assert module.LANE_COLORS == DATA_PALETTE
    assert module.BLOCK.name() == COLOURS["edited"]
    lanes = module.Timeline(doc)
    assert lanes.lane_heading("x") == ("X", "ng/mL")
    assert lanes.lane_heading("y") == ("Y", "times normal")


def test_blocks_carry_their_icon(doc, qapp):
    from cns_desktop.lab.timeline import Timeline

    lanes = Timeline(doc)
    doc.add_block("pill", 60.0)
    assert lanes.block_icon(0) == "pill"


def test_why_steps_show_effect_chips(doc, qapp):
    import re

    from cns_desktop.design.tokens import COLOURS
    from cns_desktop.lab.why_panel import WhyPanel

    panel = WhyPanel(doc)
    doc.add_block("remove_b", 0.0)
    doc.set_playhead(240.0)
    html = panel.html()
    chips = re.findall(r"<span style='color: (#[0-9a-f]{6});[^']*'>([a-z ]+)</span>", html)
    kinds = {text for _colour, text in chips}
    assert "change" in kinds and kinds & {"drives", "holds back"}
    colours = {text: colour for colour, text in chips}
    assert colours["change"] == COLOURS["edited"]
    if "holds back" in colours:
        assert colours["holds back"] == COLOURS["lowered"]
    assert "<h3>" in html
    assert "Remove the gland" in panel.toPlainText()


def test_circuit_text_is_body_size(doc, qapp):
    from cns_desktop.design.tokens import COLOURS
    from cns_desktop.lab.circuit import CircuitView

    view = CircuitView(doc)
    for text in view.part_texts.values():
        assert text.font().pixelSize() == TYPE["label"][0]
        assert text.brush().color().name() == COLOURS["text"]
    assert view.backgroundBrush().color().name() == COLOURS["s0"]


def test_edited_values_are_marked_by_the_design_system(doc, qapp):
    from cns_desktop.lab.model_panel import ModelPanel

    panel = ModelPanel(doc)
    doc.set_value("k", 3.0)
    assert panel._spins["k"].property("edited") == "true"
    assert panel._labels["k"].property("tone") == "edited"
    assert panel._spins["k"].styleSheet() == ""


def test_names_win_over_the_option_column_in_a_narrow_panel(doc, qapp):
    page = ExperimentsPage(doc)
    panel = page.panel
    page.resize(240, 400)
    page.show()
    qapp.processEvents()
    assert panel.isColumnHidden(1)
    page.resize(400, 400)
    qapp.processEvents()
    assert not panel.isColumnHidden(1)
