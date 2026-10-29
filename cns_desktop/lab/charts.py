from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cns_desktop.design.charts import Series, SmallMultiples
from cns_desktop.design.tokens import DATA_PALETTE

from .labels import plain

HOURS = 60.0


class LabCharts(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.compare = True
        self.multiples = SmallMultiples("h")
        self.multiples.clicked_x.connect(lambda x: self.document.set_playhead(x * HOURS))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.multiples)
        document.model_changed.connect(self.populate)
        self.populate()
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(self._move_cursor)
        self.refresh()

    def populate(self) -> None:
        values = sorted((v for v in self.document.model.values if v.lane is not None),
                        key=lambda v: v.lane)
        self.multiples.set_series([
            Series(v.key, v.name, v.display_unit, DATA_PALETTE[n % len(DATA_PALETTE)])
            for n, v in enumerate(values)])
        self.plots = {row.series.key: row.plot.getPlotItem() for row in self.multiples.rows}
        self.curves = {row.series.key: row.curves for row in self.multiples.rows}
        self.cursors = {row.series.key: row.cursor for row in self.multiples.rows}

    def set_compare(self, on: bool) -> None:
        self.compare = bool(on)
        self.refresh()

    def _data(self, run, key: str):
        scale = self.document.simulator.values[key].display_scale
        return np.asarray(run.times) / HOURS, run.value(key) * scale

    def refresh(self) -> None:
        doc = self.document
        for key in self.curves:
            for name, run, shown in (("run", doc.run, True), ("normal", doc.normal, self.compare),
                                     ("snapshot", doc.snapshot, doc.snapshot is not None)):
                if run is None or not shown:
                    self.multiples.clear_line(key, name)
                else:
                    self.multiples.set_line(key, name, *self._data(run, key))
        self.multiples.set_x_range(0.0, doc.experiment.length / HOURS)
        self._move_cursor(doc.playhead)

    def _now(self, key: str) -> None:
        doc = self.document
        if doc.run is None:
            self.multiples.set_now(key, "")
            return
        mine = doc.run.display(key, doc.playhead)
        tone = ""
        if doc.normal is not None:
            theirs = doc.normal.display(key, doc.playhead)
            if abs(theirs) > 1e-12:
                ratio = mine / theirs
                tone = "raised" if ratio > 1.02 else "lowered" if ratio < 0.98 else ""
        self.multiples.set_now(key, plain(mine, 3), tone)

    def _move_cursor(self, t: float) -> None:
        self.multiples.set_cursor(t / HOURS)
        for key in self.curves:
            self._now(key)

    def on_click(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        for row in self.multiples.rows:
            if row.plot.getPlotItem().vb.sceneBoundingRect().contains(event.scenePos()):
                self.multiples.click(row, event.scenePos())
                return
