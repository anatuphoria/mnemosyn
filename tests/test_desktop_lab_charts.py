import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.charts import LabCharts
from cns_desktop.lab.document import LabDocument


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def charts(qapp, toy_lab_atlas):
    doc = LabDocument(Atlas.open(toy_lab_atlas), "toy")
    widget = LabCharts(doc)
    widget.resize(800, 500)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()


class Click:
    def __init__(self, pos):
        self._pos = pos

    def scenePos(self):
        return self._pos

    def button(self):
        return Qt.MouseButton.LeftButton


def test_one_plot_per_lane_with_units(charts):
    assert list(charts.plots) == ["x", "y", "m"]
    rows = charts.multiples
    assert (rows.row("x").name.text(), rows.row("x").unit.text()) == ("X", "ng/mL")
    assert rows.row("y").unit.text() == "times normal"
    assert rows.axis.getPlotItem().getAxis("bottom").labelText == "h"


def test_each_row_shows_its_value_now(charts):
    doc = charts.document
    doc.set_playhead(120.0)
    assert charts.multiples.row("x").now.text() != ""
    doc.add_block("remove_b", 0.0)
    doc.set_playhead(600.0)
    tones = {charts.multiples.row(k).now.property("tone") for k in ("x", "y")}
    assert tones & {"raised", "lowered"}


def test_curves_follow_the_run_and_the_normal(charts):
    run, normal = charts.curves["x"]["run"], charts.curves["x"]["normal"]
    xs, ys = run.getData()
    assert xs[-1] == pytest.approx(24.0)
    assert ys[0] == pytest.approx(charts.document.run.display("x", 0.0))
    assert normal.isVisible()
    charts.set_compare(False)
    assert not normal.isVisible()
    charts.document.take_snapshot()
    assert charts.curves["x"]["snapshot"].isVisible()


def test_the_cursor_follows_the_playhead(charts):
    charts.document.set_playhead(600.0)
    assert charts.cursors["x"].value() == pytest.approx(10.0)


def test_clicking_sets_the_playhead(charts):
    plot = charts.plots["y"]
    scene = plot.vb.mapViewToScene(QPointF(5.0, 1.0))
    charts.on_click(Click(scene))
    assert charts.document.playhead == pytest.approx(300.0, abs=1.0)
