from __future__ import annotations

import math

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from cns_desktop.design.icons import icon
from cns_desktop.design.theme import set_flag, set_role, set_tone
from cns_desktop.design.tokens import GAP, SIZE

from .controls import ClockSpinBox, CurveGraph, ScaleSlider, StopSwitch
from .scales import scale_for

SAME = 1e-12
OTHER = "Other"


def short_source(references) -> str:
    parts = []
    for ref in references:
        authors = [a.strip() for a in ref.authors.split(",") if a.strip()]
        first = authors[0] if authors else ref.title
        parts.append(f"{first}{' et al.' if len(authors) > 1 else ''} ({ref.year})")
    return "; ".join(parts)


def decimals_for(*numbers: float) -> int:
    smallest = min((abs(n) for n in numbers if n), default=1.0)
    return max(2, min(8, 3 - math.floor(math.log10(smallest))))


class ModelPanel(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.body = QWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.reset_all = QPushButton("Reset all")
        self.reset_all.clicked.connect(document.reset_values)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.reset_all)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(row)
        document.changed.connect(self.refresh)
        document.model_changed.connect(self.populate)
        self.populate()

    def minimumSizeHint(self) -> QSize:
        return QSize(SIZE["panel_min"], super().minimumSizeHint().height())

    def _text(self, key: str) -> str:
        found = self.document.atlas.lab_text(self.document.model.key, key)
        return found[0] if found else ""

    def populate(self) -> None:
        self.body = QWidget()
        self.column = QVBoxLayout(self.body)
        self.column.setContentsMargins(0, 0, 0, GAP["small"])
        self.column.setSpacing(0)
        self.scroll.setWidget(self.body)
        model = self.document.model
        references = self.document.atlas.references
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._resets: dict[str, QToolButton] = {}
        self._labels: dict[str, QLabel] = {}
        self._controls: dict[str, QWidget] = {}
        self._badges: dict[str, QLabel] = {}
        self._notes: dict[str, QLabel] = {}
        self._texts: dict[str, tuple[str, str, str]] = {}
        self._titles: list[str] = []
        shown = [p for p in model.parameters if p.panel]
        for p in shown:
            source = short_source([references[k] for k in p.refs if k in references])
            self._texts[p.key] = (p.name, self._text(f"parameter.{p.key}.meaning"), source)
        order: list[str] = []
        for p in shown:
            if p.group not in order:
                order.append(p.group)
        order.sort(key=lambda g: g == "")
        for group in order:
            title = self._text(f"group.{group}.name") if group else OTHER
            self._titles.append(title.upper())
            heading = QLabel(title.upper())
            set_role(heading, "data")
            heading.setContentsMargins(SIZE["panel_pad"], GAP["medium"], GAP["small"], GAP["tight"])
            self.column.addWidget(heading)
            placed: set[str] = set()
            for p in shown:
                if p.group != group or p.key in placed:
                    continue
                curve = model.curve_of(p.key) if p.control == "curve" else None
                if curve is not None:
                    self.column.addWidget(self._curve_block(curve))
                    placed.update(curve.parameters)
                else:
                    self.column.addWidget(self._row(p))
                    placed.add(p.key)
        self.column.addStretch(1)
        self.refresh()

    def _field(self, p) -> QWidget:
        spin = ClockSpinBox() if p.control == "clock" else QDoubleSpinBox()
        spin.setMinimumWidth(SIZE["field_min"])
        spin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        spin.setDecimals(0 if p.control == "clock" else decimals_for(p.value, p.low, p.high))
        spin.setRange(p.low, p.high)
        spin.setSingleStep((p.high - p.low) / 100 or 1.0)
        if p.control != "clock":
            spin.setSuffix(f" {p.unit}")
        spin.setValue(p.value)
        spin.setToolTip("\n".join(t for t in self._texts[p.key][1:] if t))
        spin.editingFinished.connect(lambda k=p.key: self._typed(k))
        reset = QToolButton(text="Reset")
        reset.setIcon(icon("rotate-ccw"))
        reset.setIconSize(QSize(SIZE["icon_header"], SIZE["icon_header"]))
        reset.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        shown = spin.textFromValue(p.value) if p.control == "clock" else f"{p.value:g} {p.unit}"
        reset.setToolTip(f"Back to the normal value, {shown}")
        reset.clicked.connect(lambda _=False, k=p.key: self.document.reset_value(k))
        line = QWidget()
        row = QHBoxLayout(line)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(GAP["tight"])
        row.addWidget(spin, 1)
        if p.control == "rate":
            badge = QLabel()
            set_tone(badge, "edited")
            set_role(badge, "data")
            row.addWidget(badge)
            self._badges[p.key] = badge
        row.addWidget(reset)
        self._spins[p.key] = spin
        self._resets[p.key] = reset
        return line

    def _label(self, p) -> QLabel:
        label = QLabel(p.name)
        label.setWordWrap(True)
        label.setToolTip("\n".join(t for t in self._texts[p.key][1:] if t))
        self._labels[p.key] = label
        return label

    def _box(self) -> tuple[QWidget, QVBoxLayout]:
        box = QWidget()
        stack = QVBoxLayout(box)
        stack.setContentsMargins(SIZE["panel_pad"], GAP["small"], GAP["small"], GAP["small"])
        stack.setSpacing(GAP["tight"])
        return box, stack

    def _row(self, p) -> QWidget:
        box, stack = self._box()
        stack.addWidget(self._label(p))
        stack.addWidget(self._field(p))
        if p.control == "switch":
            control = StopSwitch(p)
            control.committed.connect(lambda v, k=p.key: self._commit(k, v))
        else:
            control = ScaleSlider(scale_for(p), p.value, p.value)
            control.previewed.connect(lambda v, k=p.key: self._preview(k, v))
            control.committed.connect(lambda v, k=p.key: self._commit(k, v))
        stack.addWidget(control)
        self._controls[p.key] = control
        if p.control == "rate":
            note = QLabel()
            note.setWordWrap(True)
            set_role(note, "secondary")
            set_tone(note, "text3")
            stack.addWidget(note)
            self._notes[p.key] = note
        return box

    def _curve_block(self, curve) -> QWidget:
        model = self.document.model
        box, stack = self._box()
        title = QLabel(curve.name)
        title.setWordWrap(True)
        stack.addWidget(title)
        graph = CurveGraph(model, curve, {})
        graph.previewed.connect(self._preview)
        graph.committed.connect(self._commit)
        stack.addWidget(graph)
        for key in curve.parameters:
            p = model.parameter(key)
            label = self._label(p)
            set_role(label, "secondary")
            stack.addWidget(label)
            stack.addWidget(self._field(p))
            self._controls[key] = graph
        return box

    def spin(self, key: str) -> QDoubleSpinBox:
        return self._spins[key]

    def reset_button(self, key: str) -> QToolButton:
        return self._resets[key]

    def control(self, key: str) -> QWidget:
        return self._controls[key]

    def badge(self, key: str) -> QLabel:
        return self._badges[key]

    def note(self, key: str) -> QLabel:
        return self._notes[key]

    def group_titles(self) -> list[str]:
        return list(self._titles)

    def row_text(self, key: str) -> tuple[str, str, str]:
        return self._texts[key]

    def is_marked(self, key: str) -> bool:
        return key in self.document.experiment.value_map

    def _current(self, key: str) -> float:
        return self.document.experiment.value_map.get(key, self.document.model.parameter(key).value)

    def _typed(self, key: str) -> None:
        self._commit(key, self._spins[key].value())

    def _commit(self, key: str, value: float) -> None:
        normal = self.document.model.parameter(key).value
        if abs(value - normal) <= SAME * max(1.0, abs(normal)):
            if self.is_marked(key):
                self.document.reset_value(key)
            else:
                self.refresh()
            return
        if abs(value - self._current(key)) > SAME:
            self.document.set_value(key, value)
        else:
            self.refresh()

    def _preview(self, key: str, value: float) -> None:
        spin = self._spins[key]
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)
        self._describe(key, value)

    def _describe(self, key: str, value: float) -> None:
        p = self.document.model.parameter(key)
        text = scale_for(p).badge(value, p.value)
        if key in self._badges:
            self._badges[key].setText(text)
            self._badges[key].setVisible(bool(text))
        if key in self._notes:
            side = "" if not text else ("up" if value > p.value else "down")
            note = self._text(f"parameter.{key}.{side}") if side else ""
            self._notes[key].setText(note)
            self._notes[key].setVisible(bool(note))

    def refresh(self) -> None:
        edited = self.document.experiment.value_map
        model = self.document.model
        for key, spin in self._spins.items():
            value = edited.get(key, model.parameter(key).value)
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
            marked = key in edited
            set_flag(spin, "edited", marked)
            set_tone(self._labels[key], "edited" if marked else "")
            self._resets[key].setEnabled(marked)
            control = self._controls[key]
            if isinstance(control, ScaleSlider):
                control.set_value(value, marked)
            elif isinstance(control, StopSwitch):
                control.set_value(value)
            self._describe(key, value)
        for curve in model.curves:
            if curve.parameters and curve.parameters[0] in self._controls:
                graph = self._controls[curve.parameters[0]]
                graph.set_values(dict(edited), any(k in edited for k in curve.parameters))
        self.reset_all.setEnabled(bool(edited))
