import pytest
from PySide6.QtWidgets import QApplication

from cns_desktop.design.tokens import DATA_PALETTE, SIZE
from pathway_helpers import open_window


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_behaviour_atlas, tmp_path):
    w = open_window(qapp, toy_behaviour_atlas, tmp_path)
    w.workspaces.switch("Pathways")
    w.pathways.open("mood")
    qapp.processEvents()
    yield w
    w.close()


def test_behaviour_lanes_look_like_the_lab(window):
    chart = window.chart
    rows = chart.multiples.rows
    assert rows and chart.row_height() == SIZE["lane"]
    assert all(row.height() == SIZE["lane"] for row in rows)
    assert [row.series.colour for row in rows] == list(DATA_PALETTE[:len(rows)])
    assert chart.note_area.isHidden()


def test_the_timeline_note_moves_to_the_step_tab(window):
    text = window.step_panel.details.toPlainText()
    assert "Timeline" in text and "Schematic shapes, not measured data." in text
    assert "Author A (2020)" in text
    window.pathways.go(1)
    assert "Schematic shapes, not measured data." in window.step_panel.details.toPlainText()
    window.pathways.leave()
    assert "Schematic shapes" not in window.step_panel.details.toPlainText()
