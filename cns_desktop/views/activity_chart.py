from __future__ import annotations

from html import escape

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from cns_atlas import Timeline
from cns_atlas.timelines import note_parts

from ..state import AppState


class ActivityChart(QWidget):
    seek_requested = Signal(float)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.timeline: Timeline | None = None
        self.timeline_items: list = []
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0a0a10")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.legend = self.plot.addLegend()
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffffff", width=1))
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.RichText)
        self.note.setOpenExternalLinks(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.note_area = QScrollArea()
        self.note_area.setWidgetResizable(True)
        self.note_area.setWidget(self.note)
        self.note.hide()
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.time_label)
        row = QHBoxLayout()
        row.addWidget(self.plot, 3)
        row.addWidget(self.note_area, 1)
        layout.addLayout(row, 1)
        self.plot.scene().sigMouseClicked.connect(self._on_click)
        self.plot.disableAutoRange()

    def show_timeline(self, timeline: Timeline | None, name: str = "") -> None:
        for item in self.timeline_items:
            self.plot.removeItem(item)
        self.timeline_items = []
        self.legend.clear()
        if self.cursor.scene() is not None:
            self.plot.removeItem(self.cursor)
        self.timeline = timeline
        if timeline is None:
            self.time_label.setText("")
            self.note.hide()
            self.plot.setTitle("")
            return
        for c in timeline.curves:
            times, levels = zip(*c.points)
            item = self.plot.plot(times, levels, pen=pg.mkPen(c.color, width=2), name=c.name)
            self.timeline_items.append(item)
        self.plot.addItem(self.cursor)
        self.set_time(0.0)
        self.plot.setLabel("bottom", f"time ({timeline.unit})", units=None)
        self.plot.setLabel("left", "relative level")
        self.plot.setXRange(0, timeline.duration, padding=0.02)
        self.plot.setYRange(0, 1.05, padding=0)
        self.plot.setTitle(f"{name} - schematic")
        text, refs = note_parts(timeline.note, self.state.atlas.references)
        items = "".join(f"<br>[{n}] {escape(r.citation())}" for n, r in enumerate(refs, 1))
        self.note.setText(f"<small>{escape(text)} Schematic shapes, not measured data."
                          f"{items}</small>")
        self.note.show()

    def set_time(self, time: float) -> None:
        self.cursor.setValue(time)
        if self.timeline is not None:
            self.time_label.setText(f"{time:g} / {self.timeline.duration:g} {self.timeline.unit}")

    def _on_click(self, event) -> None:
        if self.timeline is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.plot.plotItem.vb.sceneBoundingRect().contains(event.scenePos()):
            return
        point = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
        self.seek_requested.emit(float(point.x()))
