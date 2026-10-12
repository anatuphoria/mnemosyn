from __future__ import annotations

import zlib
from html import escape

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from cns_atlas import Timeline
from cns_atlas.timelines import note_parts

from ..state import AppState

DURATION_S = 60.0
SAMPLES = 600
PLAY = "Play (Space)"
PAUSE = "Pause (Space)"
SPEEDS = ((0.5, "½×"), (1.0, "1×"), (2.0, "2×"))


def placeholder_series(structure_id: int) -> tuple[np.ndarray, np.ndarray]:
    """Fake deterministic signal until a real model exists."""
    rng = np.random.default_rng(zlib.crc32(str(structure_id).encode()))
    t = np.linspace(0.0, DURATION_S, SAMPLES)
    freqs = rng.uniform(0.02, 0.4, size=3)
    phases = rng.uniform(0, 2 * np.pi, size=3)
    y = sum(np.sin(2 * np.pi * f * t + p) / (i + 1)
            for i, (f, p) in enumerate(zip(freqs, phases)))
    y += rng.normal(0, 0.08, SAMPLES)
    return t, y


class ActivityChart(QWidget):
    seek_requested = Signal(float)
    back_requested = Signal()
    next_requested = Signal()
    play_requested = Signal()
    speed_changed = Signal(float)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.timeline: Timeline | None = None
        self.timeline_items: list = []
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0a0a10")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.curve = self.plot.plot(pen=pg.mkPen(width=2))
        self.legend = self.plot.addLegend()
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffffff", width=1))
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.RichText)
        self.note.setOpenExternalLinks(True)
        self.note.hide()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.back_button = QPushButton("Back")
        self.play_button = QPushButton(PLAY)
        self.next_button = QPushButton("Next")
        self.speed = QComboBox()
        for value, text in SPEEDS:
            self.speed.addItem(text, value)
        self.speed.setCurrentIndex(1)
        self.step_label = QLabel()
        self.time_label = QLabel()
        for widget in (self.back_button, self.play_button, self.next_button, self.speed):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.controls = QWidget()
        bar = QHBoxLayout(self.controls)
        bar.setContentsMargins(4, 2, 4, 2)
        for widget in (self.back_button, self.play_button, self.next_button, self.speed):
            bar.addWidget(widget)
        bar.addWidget(self.step_label, 1)
        bar.addWidget(self.time_label)
        self.step_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.time_label.setFixedWidth(
            self.time_label.fontMetrics().horizontalAdvance("0000.0 / 0000 min") + 8)
        self.controls.hide()
        self.back_button.clicked.connect(self.back_requested)
        self.next_button.clicked.connect(self.next_requested)
        self.play_button.clicked.connect(self.play_requested)
        self.speed.currentIndexChanged.connect(
            lambda i: self.speed_changed.emit(float(self.speed.itemData(i))))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controls)
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.note)
        self.plot.scene().sigMouseClicked.connect(self._on_click)
        state.selection_changed.connect(self._on_selection)
        self._activity_axes()
        self.show_structure(state.selected)

    def _activity_axes(self) -> None:
        self.plot.setLabel("bottom", "time", units="s")
        self.plot.setLabel("left", "activity (a.u.)")
        self.plot.enableAutoRange()

    def _on_selection(self, structure_id: int | None) -> None:
        if self.timeline is None:
            self.show_structure(structure_id)

    def show_structure(self, structure_id: int | None) -> None:
        if structure_id is None:
            self.curve.setData([], [])
            self.plot.setTitle("Select a structure")
            return
        s = self.state.atlas.get(structure_id)
        t, y = placeholder_series(structure_id)
        self.curve.setData(t, y, pen=pg.mkPen(s.rgb_triplet, width=2))
        self.plot.setTitle(f"{s.name} - PLACEHOLDER data (no model yet)")

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
            self.curve.show()
            self._activity_axes()
            self.show_structure(self.state.selected)
            return
        self.curve.hide()
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

    def show_controls(self, shown: bool) -> None:
        self.controls.setVisible(shown)
        if not shown:
            self.set_playing(False)

    def set_step(self, text: str) -> None:
        self.step_label.setText(text)

    def set_edges(self, can_back: bool, can_next: bool) -> None:
        self.back_button.setEnabled(can_back)
        self.next_button.setEnabled(can_next)

    def set_playing(self, playing: bool) -> None:
        self.play_button.setText(PAUSE if playing else PLAY)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not self.controls.isHidden():
            self.play_requested.emit()
        else:
            super().keyPressEvent(event)

    def _on_click(self, event) -> None:
        if self.timeline is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.plot.plotItem.vb.sceneBoundingRect().contains(event.scenePos()):
            return
        point = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
        self.seek_requested.emit(float(point.x()))
