import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from cns_desktop.design import theme
from cns_desktop.design.charts import Series, SmallMultiples
from cns_desktop.design.tokens import COLOURS, SIZE


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


def chart(qapp, count=3, height=400):
    widget = SmallMultiples("hours")
    widget.set_series([Series(f"v{n}", f"Value {n}", "ng/mL", "#6d98f2") for n in range(count)])
    xs = np.linspace(0, 24, 50)
    for n in range(count):
        widget.set_line(f"v{n}", "run", xs, 0.87 + 0.04 * np.sin(xs / 4 + n))
        widget.set_line(f"v{n}", "normal", xs, np.full_like(xs, 0.89))
    widget.set_x_range(0, 24)
    widget.resize(600, height)
    widget.show()
    qapp.processEvents()
    return widget


def test_rows_never_shrink_below_56_and_the_panel_scrolls(qapp):
    widget = chart(qapp, count=8, height=300)
    assert all(row.height() >= SIZE["chart_row"] for row in widget.rows)
    assert widget.scroll.verticalScrollBar().maximum() > 0


def test_rows_fill_the_height_when_there_are_few(qapp):
    widget = chart(qapp, count=1, height=400)
    assert widget.rows[0].height() > 200


def test_one_time_axis_sits_below_the_rows(qapp):
    widget = chart(qapp)
    assert all(not row.plot.getPlotItem().getAxis("bottom").isVisible() for row in widget.rows)
    axis = widget.axis.getPlotItem().getAxis("bottom")
    assert axis.isVisible() and axis.labelText == "hours"
    assert widget.axis.geometry().top() >= widget.scroll.geometry().bottom()


def test_no_axis_uses_an_si_prefix(qapp):
    widget = chart(qapp)
    for plot in [row.plot for row in widget.rows] + [widget.axis]:
        for name in ("left", "bottom"):
            assert not plot.getPlotItem().getAxis(name).autoSIPrefix
    ticks = widget.rows[0].plot.getPlotItem().getAxis("left")._tickLevels[0]
    values = [float(text) for _value, text in ticks]
    assert len(values) == 2 and 0.8 < min(values) < max(values) < 1.0


def test_series_are_named_in_the_name_column_not_a_legend(qapp):
    widget = chart(qapp)
    row = widget.row("v1")
    assert (row.name.text(), row.unit.text()) == ("Value 1", "ng/mL")
    assert row.name.parent().width() == 150
    for row in widget.rows:
        assert row.plot.getPlotItem().legend is None
    widget.set_now("v1", "0.91", "raised")
    assert widget.row("v1").now.text() == "0.91"
    assert widget.row("v1").now.property("tone") == "raised"


def test_the_normal_line_is_grey_and_the_snapshot_dashed(qapp):
    widget = chart(qapp)
    curves = widget.row("v0").curves
    assert curves["normal"].opts["pen"].color().name() == COLOURS["normal"]
    assert curves["snapshot"].opts["pen"].style() == pg.QtCore.Qt.PenStyle.DashLine


def test_clicking_a_row_sets_the_playhead(qapp):
    widget = chart(qapp)
    seen = []
    widget.clicked_x.connect(seen.append)
    row = widget.row("v2")
    box = row.plot.getPlotItem().vb
    widget.click(row, box.mapViewToScene(QPointF(6.0, 0.89)))
    assert seen and seen[0] == pytest.approx(6.0, abs=0.2)
    widget.click(row, QPointF(-50, -50))
    assert len(seen) == 1


def test_the_cursor_moves_on_every_row(qapp):
    widget = chart(qapp)
    widget.set_cursor(10.0)
    assert widget.cursor_x == 10.0
    assert all(row.cursor.value() == 10.0 for row in widget.rows)
