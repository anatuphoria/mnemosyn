from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .timeline import LANE_COLORS

NORMAL = "#55556a"


class LabCharts(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.compare = True
        self.layout_widget = pg.GraphicsLayoutWidget()
        self.layout_widget.setBackground("#0a0a10")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.layout_widget)
        self.layout_widget.scene().sigMouseClicked.connect(self.on_click)
        document.model_changed.connect(self.populate)
        self.populate()
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(self._move_cursor)
        self.refresh()

    def populate(self) -> None:
        self.layout_widget.clear()
        self.plots: dict[str, pg.PlotItem] = {}
        self.curves: dict[str, dict[str, pg.PlotDataItem]] = {}
        self.cursors: dict[str, pg.InfiniteLine] = {}
        values = sorted((v for v in self.document.model.values if v.lane is not None),
                        key=lambda v: v.lane)
        first = None
        for n, value in enumerate(values):
            plot = self.layout_widget.addPlot(row=n, col=0)
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setLabel("left", f"{value.name} ({value.display_unit})")
            plot.setLabel("bottom", "hours")
            if first is None:
                first = plot
            else:
                plot.setXLink(first)
            color = LANE_COLORS[n % len(LANE_COLORS)]
            self.curves[value.key] = {
                "normal": plot.plot(pen=pg.mkPen(NORMAL, width=1.5)),
                "snapshot": plot.plot(pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine)),
                "run": plot.plot(pen=pg.mkPen(color, width=2)),
            }
            cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#e8e6df", width=1))
            plot.addItem(cursor)
            self.plots[value.key] = plot
            self.cursors[value.key] = cursor

    def set_compare(self, on: bool) -> None:
        self.compare = bool(on)
        self.refresh()

    def _data(self, run, key: str):
        scale = self.document.simulator.values[key].display_scale
        return np.asarray(run.times) / 60.0, run.value(key) * scale

    def refresh(self) -> None:
        doc = self.document
        for key, curves in self.curves.items():
            for name, run, shown in (("run", doc.run, True), ("normal", doc.normal, self.compare),
                                     ("snapshot", doc.snapshot, doc.snapshot is not None)):
                curve = curves[name]
                if run is None or not shown:
                    curve.setData([], [])
                    curve.setVisible(False)
                    continue
                curve.setData(*self._data(run, key))
                curve.setVisible(True)
        self._move_cursor(doc.playhead)

    def _move_cursor(self, t: float) -> None:
        for cursor in self.cursors.values():
            cursor.setValue(t / 60.0)

    def on_click(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        for plot in self.plots.values():
            if plot.vb.sceneBoundingRect().contains(pos):
                self.document.set_playhead(plot.vb.mapSceneToView(pos).x() * 60.0)
                return
