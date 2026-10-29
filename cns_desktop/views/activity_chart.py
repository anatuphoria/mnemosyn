from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from cns_atlas import Timeline
from cns_atlas.timelines import note_parts

from ..design import rich
from ..design.charts import Series, SmallMultiples
from ..design.theme import set_role
from ..design.tokens import SIZE
from ..state import AppState


class _Cursor:
    def __init__(self, multiples: SmallMultiples) -> None:
        self.multiples = multiples

    def value(self) -> float:
        return self.multiples.cursor_x


class ActivityChart(QWidget):
    seek_requested = Signal(float)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.timeline: Timeline | None = None
        self.timeline_items: list = []
        self.plot = SmallMultiples()
        self.multiples = self.plot
        self.cursor = _Cursor(self.multiples)
        self.multiples.clicked_x.connect(self._seek)
        self.title = QLabel()
        set_role(self.title, "data")
        self.time_label = QLabel()
        set_role(self.time_label, "data")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.RichText)
        self.note.setOpenExternalLinks(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        set_role(self.note, "secondary")
        self.note.setContentsMargins(SIZE["panel_pad"], 8, SIZE["panel_pad"], 8)
        self.note_area = QScrollArea()
        self.note_area.setWidgetResizable(True)
        self.note_area.setWidget(self.note)
        self.note.hide()
        heading = QHBoxLayout()
        heading.setContentsMargins(SIZE["panel_pad"], 4, SIZE["panel_pad"], 4)
        heading.addWidget(self.title)
        heading.addStretch(1)
        heading.addWidget(self.time_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(heading)
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addWidget(self.plot, 3)
        row.addWidget(self.note_area, 1)
        layout.addLayout(row, 1)

    def show_timeline(self, timeline: Timeline | None, name: str = "") -> None:
        self.timeline = timeline
        self.timeline_items = []
        if timeline is None:
            self.multiples.set_series([])
            self.time_label.setText("")
            self.title.setText("")
            self.note.hide()
            return
        self.multiples.set_series([Series(f"c{n}", c.name, "relative level", c.color)
                                   for n, c in enumerate(timeline.curves)], y_range=(0.0, 1.0))
        for n, c in enumerate(timeline.curves):
            times, levels = zip(*c.points)
            self.multiples.set_line(f"c{n}", "run", times, levels)
            self.timeline_items.append(self.multiples.row(f"c{n}").curves["run"])
        self.multiples.set_axis_label(timeline.unit)
        self.multiples.set_x_range(0, timeline.duration)
        self.title.setText(f"{name} · schematic" if name else "Schematic")
        text, refs = note_parts(timeline.note, self.state.atlas.references)
        items = "".join(f"<br>[{n}] {escape(r.citation())}" for n, r in enumerate(refs, 1))
        self.note.setText(rich.secondary(f"{escape(text)} Schematic shapes, not measured data."
                                         f"{items}"))
        self.note.show()
        self.set_time(0.0)

    def set_time(self, time: float) -> None:
        self.multiples.set_cursor(time)
        if self.timeline is not None:
            self.time_label.setText(f"{time:g} / {self.timeline.duration:g} {self.timeline.unit}")

    def _seek(self, x: float) -> None:
        if self.timeline is not None:
            self.seek_requested.emit(x)
