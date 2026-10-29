from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from cns_desktop.design.fonts import font
from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import COLOURS, SIZE

NAME_WIDTH = 150
VALUE_AXIS = 44
TIME_AXIS = 28
LINES = ("normal", "snapshot", "run")


@dataclass(frozen=True)
class Series:
    key: str
    name: str
    unit: str
    colour: str


def _tick(value: float) -> str:
    return "0" if abs(value) < 5e-4 else f"{value:.3g}"


class TimeAxis(pg.AxisItem):
    def __init__(self) -> None:
        super().__init__("bottom")
        self.unit = ""

    def tickStrings(self, values, scale, spacing):
        suffix = f" {self.unit}" if self.unit else ""
        return [f"{v:g}{suffix}" for v in values]


def _plain_axes(item: pg.PlotItem) -> None:
    for name in ("left", "bottom", "top", "right"):
        axis = item.getAxis(name)
        axis.enableAutoSIPrefix(False)
        axis.setPen(pg.mkPen(COLOURS["line"]))
        axis.setTextPen(pg.mkPen(COLOURS["text2"]))
        axis.setStyle(tickFont=font("data"), tickLength=-4, hideOverlappingLabels=False)


def _plot() -> pg.PlotWidget:
    plot = pg.PlotWidget()
    plot.setBackground(COLOURS["s1"])
    plot.setMenuEnabled(False)
    plot.setMouseEnabled(False, False)
    plot.hideButtons()
    item = plot.getPlotItem()
    _plain_axes(item)
    return plot


class Row(QWidget):
    def __init__(self, series: Series) -> None:
        super().__init__()
        self.series = series
        self.setMinimumHeight(SIZE["chart_row"])
        names = QFrame()
        names.setFixedWidth(NAME_WIDTH)
        column = QVBoxLayout(names)
        column.setContentsMargins(SIZE["panel_pad"], 6, 8, 6)
        column.setSpacing(0)
        self.name = QLabel(series.name)
        set_role(self.name, "label")
        self.unit = QLabel(series.unit)
        set_role(self.unit, "secondary")
        self.now = QLabel()
        set_role(self.now, "data")
        for label in (self.name, self.unit, self.now):
            column.addWidget(label)
        column.addStretch(1)
        self.plot = _plot()
        item = self.plot.getPlotItem()
        item.hideAxis("bottom")
        item.getAxis("left").setWidth(VALUE_AXIS)
        item.showGrid(x=True, y=False, alpha=0.12)
        colour = series.colour
        self.curves = {
            "normal": item.plot(pen=pg.mkPen(COLOURS["normal"], width=1.5)),
            "snapshot": item.plot(pen=pg.mkPen(colour, width=1.5, style=Qt.PenStyle.DashLine)),
            "run": item.plot(pen=pg.mkPen(colour, width=2)),
        }
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(COLOURS["text"]))
        item.addItem(self.cursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(names)
        row.addWidget(self.plot, 1)

    def mark_range(self, fixed: tuple[float, float] | None = None) -> None:
        if fixed is not None:
            low, high = fixed
        else:
            data = [curve.getData()[1] for curve in self.curves.values()
                    if curve.isVisible() and curve.getData()[1] is not None
                    and len(curve.getData()[1])]
            if not data:
                return
            values = np.concatenate(data)
            low, high = float(np.nanmin(values)), float(np.nanmax(values))
        if high - low < 1e-12:
            spread = abs(high) * 0.05 or 1.0
            low, high = low - spread, high + spread
        pad = (high - low) * 0.22
        item = self.plot.getPlotItem()
        item.setYRange(low - pad, high + pad, padding=0)
        item.getAxis("left").setTicks([[(low, _tick(low)), (high, _tick(high))], []])


class SmallMultiples(QWidget):
    clicked_x = Signal(float)

    def __init__(self, axis_label: str = "", parent=None) -> None:
        super().__init__(parent)
        self.rows: list[Row] = []
        self._rows: dict[str, Row] = {}
        self.cursor_x = 0.0
        self.y_range: tuple[float, float] | None = None
        self.body = QWidget()
        self._column = QVBoxLayout(self.body)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.axis = _plot()
        self.axis.getPlotItem().setAxisItems({"bottom": TimeAxis()})
        _plain_axes(self.axis.getPlotItem())
        self.axis.setFixedHeight(TIME_AXIS)
        axis_item = self.axis.getPlotItem()
        axis_item.hideAxis("left")
        axis_item.getAxis("bottom").setStyle(tickLength=4)
        axis_item.setContentsMargins(NAME_WIDTH + VALUE_AXIS, 0, 0, 0)
        self.set_axis_label(axis_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.axis)

    def set_axis_label(self, text: str) -> None:
        axis = self.axis.getPlotItem().getAxis("bottom")
        axis.unit = text
        axis.labelText = text
        axis.showLabel(False)
        axis.setHeight(TIME_AXIS)
        axis.picture = None
        axis.update()

    def row(self, key: str) -> Row:
        return self._rows[key]

    def set_series(self, series: list[Series],
                   y_range: tuple[float, float] | None = None) -> None:
        for row in self.rows:
            self._column.removeWidget(row)
            row.setParent(None)
        self.rows, self._rows, self.y_range = [], {}, y_range
        for one in series:
            row = Row(one)
            row.plot.scene().sigMouseClicked.connect(
                lambda event, r=row: self.click(r, event.scenePos()) if
                event.button() == Qt.MouseButton.LeftButton else None)
            if self.rows:
                row.plot.setXLink(self.rows[0].plot)
            self.rows.append(row)
            self._rows[one.key] = row
            self._column.addWidget(row, 1)
            row.show()
        self.set_cursor(self.cursor_x)

    def set_line(self, key: str, name: str, xs, ys) -> None:
        row = self._rows[key]
        curve = row.curves[name]
        curve.setData(xs, ys)
        curve.setVisible(True)
        row.mark_range(self.y_range)

    def clear_line(self, key: str, name: str) -> None:
        row = self._rows[key]
        row.curves[name].setData([], [])
        row.curves[name].setVisible(False)
        row.mark_range(self.y_range)

    def set_now(self, key: str, text: str, role: str = "text") -> None:
        label = self._rows[key].now
        label.setText(text)
        set_tone(label, role)

    def set_cursor(self, x: float) -> None:
        self.cursor_x = float(x)
        for row in self.rows:
            row.cursor.setValue(self.cursor_x)

    def set_x_range(self, low: float, high: float) -> None:
        for plot in (*(row.plot for row in self.rows[:1]), self.axis):
            plot.getPlotItem().setXRange(low, high, padding=0)

    def click(self, row: Row, scene_pos) -> None:
        box = row.plot.getPlotItem().vb
        if not box.sceneBoundingRect().contains(scene_pos):
            return
        self.clicked_x.emit(float(box.mapSceneToView(scene_pos).x()))
