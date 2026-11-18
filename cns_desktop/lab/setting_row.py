from __future__ import annotations

import math
import re

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from cns_desktop.design.icons import icon
from cns_desktop.design.theme import set_flag, set_role, set_tone
from cns_desktop.design.tokens import GAP, SIZE

from .controls import ClockSpinBox, StopSwitch, ValueBar
from .scales import scale_for

FIGURES = 4
SILENT_UNITS = ("number", "")
NUMBER = re.compile(r"^\s*[-+]?(\d+([.,]\d*)?|[.,]\d+)\s*$")
FIELD_PAD = 26
FIELD_WIDTH = 76
TEXT_MARGIN = 6


def decimals_for(*numbers: float) -> int:
    smallest = min((abs(n) for n in numbers if n), default=1.0)
    return max(2, min(8, 3 - math.floor(math.log10(smallest))))


def figures(number: float, count: int = FIGURES) -> str:
    if number == 0:
        return "0"
    if abs(number) >= 10 ** count:
        return f"{number:.0f}"
    places = max(count - 1 - math.floor(math.log10(abs(number))), 0)
    text = f"{round(number, places):.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def unit_text(unit: str) -> str:
    if unit == "fraction":
        return "%"
    return "" if unit in SILENT_UNITS else unit


def value_text(value: float, unit: str) -> str:
    if unit == "fraction":
        return f"{figures(value * 100, 3)} %"
    shown = unit_text(unit)
    return f"{figures(value)} {shown}" if shown else figures(value)


class ValueBox(QDoubleSpinBox):
    def __init__(self, parameter, parent=None) -> None:
        super().__init__(parent)
        self.parameter = parameter
        self.percent = parameter.unit == "fraction"
        self.setProperty("compact", "true")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setDecimals(decimals_for(parameter.value, parameter.low, parameter.high))
        self.setRange(parameter.low, parameter.high)
        self.setSingleStep((parameter.high - parameter.low) / 100 or 1.0)
        self.setValue(parameter.value)
        self.lineEdit().setTextMargins(0, 0, TEXT_MARGIN, 0)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def textFromValue(self, value: float) -> str:
        return figures(value * 100, 3) if self.percent else figures(value)

    def valueFromText(self, text: str) -> float:
        cleaned = text.replace("%", "").strip().replace(",", ".")
        try:
            number = float(cleaned)
        except ValueError:
            return self.value()
        return number / 100 if self.percent else number

    def validate(self, text: str, pos: int):
        cleaned = text.replace("%", "").strip()
        if cleaned in ("", "-", "+", ".", ","):
            return (QValidator.State.Intermediate, text, pos)
        if not NUMBER.match(cleaned):
            return (QValidator.State.Invalid, text, pos)
        value = self.valueFromText(text)
        if self.minimum() <= value <= self.maximum():
            return (QValidator.State.Acceptable, text, pos)
        return (QValidator.State.Intermediate, text, pos)

    def fixup(self, text: str) -> str:
        return self.textFromValue(min(max(self.valueFromText(text), self.minimum()),
                                      self.maximum()))

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        p = self.parameter
        widest = max(metrics.horizontalAdvance(self.textFromValue(v))
                     for v in (p.low, p.high, p.value, (p.low + p.high) / 3))
        return QSize(max(widest + FIELD_PAD, FIELD_WIDTH), SIZE["control"])

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


def clock_box(parameter) -> ClockSpinBox:
    box = ClockSpinBox()
    box.setProperty("compact", "true")
    box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    box.setDecimals(0)
    box.setRange(parameter.low, parameter.high)
    box.setSingleStep((parameter.high - parameter.low) / 100 or 1.0)
    box.setValue(parameter.value)
    box.lineEdit().setTextMargins(0, 0, TEXT_MARGIN, 0)
    box.setFixedWidth(max(box.fontMetrics().horizontalAdvance("00:00") + FIELD_PAD, FIELD_WIDTH))
    return box


class _Name(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SettingRow(QWidget):
    previewed = Signal(str, float)
    committed = Signal(str, float)
    reset_requested = Signal(str)

    def __init__(self, parameter, texts: tuple[str, str, str], notes: tuple[str, str],
                 with_control: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.parameter = parameter
        self.key = parameter.key
        self.name, self.meaning, self.source = texts
        self.up_note, self.down_note = notes
        self.edited = False
        self.expanded = False
        self.scale = scale_for(parameter)
        self.toggle = QToolButton(self)
        self.toggle.setAutoRaise(True)
        self.toggle.setIconSize(QSize(SIZE["icon_header"], SIZE["icon_header"]))
        self.toggle.setFixedSize(SIZE["icon"] + GAP["tight"], SIZE["icon"] + GAP["tight"])
        self.toggle.setToolTip("Show what this setting means")
        self.toggle.clicked.connect(lambda: self.set_expanded(not self.expanded))
        self.label = _Name(self.name, self)
        self.label.setWordWrap(True)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.label.clicked.connect(lambda: self.set_expanded(not self.expanded))
        self.inline = parameter.control == "switch" and with_control
        self.unit = QLabel(unit_text(parameter.unit) if parameter.control != "clock" else "time of day",
                           self)
        self.unit.setWordWrap(True)
        self.unit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        set_role(self.unit, "secondary")
        set_tone(self.unit, "text3")
        self.unit.setVisible(self.inline and bool(self.unit.text()))
        self.field = clock_box(parameter) if parameter.control == "clock" else ValueBox(parameter)
        self.field.setToolTip(self.meaning)
        self.field.editingFinished.connect(lambda: self.committed.emit(self.key, self.field.value()))
        self.reset = QToolButton(self, text="Reset")
        self.reset.setIcon(icon("rotate-ccw"))
        self.reset.setIconSize(QSize(SIZE["icon_header"], SIZE["icon_header"]))
        self.reset.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.reset.setAutoRaise(True)
        self.reset.setFixedSize(SIZE["icon"] + GAP["tight"], SIZE["icon"] + GAP["tight"])
        normal = (self.field.textFromValue(parameter.value) if parameter.control == "clock"
                  else value_text(parameter.value, parameter.unit))
        self.reset.setToolTip(f"Back to the normal value, {normal}")
        self.reset.clicked.connect(lambda: self.reset_requested.emit(self.key))
        self.reset.hide()
        self.badge = QLabel(self)
        set_role(self.badge, "data")
        set_tone(self.badge, "edited")
        self.badge.hide()
        column = QVBoxLayout(self)
        column.setContentsMargins(SIZE["panel_pad"] - GAP["tight"], GAP["small"], GAP["small"],
                                  GAP["tight"])
        column.setSpacing(GAP["tight"])
        head = QHBoxLayout()
        column.addLayout(head)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(GAP["tight"])
        head.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignTop)
        names = QVBoxLayout()
        head.addLayout(names, 1)
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(0)
        names.addWidget(self.label)
        names.addWidget(self.unit)
        head.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignTop)
        self.control: QWidget | None = None
        if self.inline:
            head.addWidget(self.field, 0, Qt.AlignmentFlag.AlignTop)
            self.control = StopSwitch(parameter)
            self.control.committed.connect(lambda v: self.committed.emit(self.key, v))
        else:
            unit = "" if parameter.control == "clock" else unit_text(parameter.unit)
            self.control = ValueBar(self.scale, parameter.value, parameter.value, self.field, unit)
            self.control.setToolTip(self._hint())
            self.control.previewed.connect(self._previewed)
            self.control.committed.connect(lambda v: self.committed.emit(self.key, v))
        self.note = QLabel(self)
        self.note.setWordWrap(True)
        set_role(self.note, "secondary")
        set_tone(self.note, "text3")
        self.details = QLabel(self._details(), self)
        self.details.setWordWrap(True)
        set_role(self.details, "secondary")
        self.details.hide()
        body = QVBoxLayout()
        column.addLayout(body)
        body.setContentsMargins(self.toggle.width() + GAP["tight"], 0, 0, 0)
        body.setSpacing(GAP["tight"])
        body.addWidget(self.control)
        notes = QHBoxLayout()
        body.addLayout(notes)
        notes.setContentsMargins(0, 0, 0, 0)
        notes.setSpacing(GAP["small"])
        notes.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        notes.addWidget(self.note, 1)
        body.addWidget(self.details)
        self._sync_toggle()
        self._describe(parameter.value)

    def _hint(self) -> str:
        normal = self.field.textFromValue(self.parameter.value)
        return f"Drag to change, click to type. Normal is {normal}."

    def _details(self) -> str:
        parts = [self.meaning] if self.meaning else []
        if self.source:
            parts.append(f"Source: {self.source}")
        return "\n\n".join(parts) or "No description."

    def _sync_toggle(self) -> None:
        self.toggle.setIcon(icon("chevron-down" if self.expanded else "chevron-right"))

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self.details.setVisible(expanded)
        self._sync_toggle()

    def matches(self, words: str) -> bool:
        words = words.strip().lower()
        return not words or words in self.name.lower() or words in self.meaning.lower()

    def _previewed(self, value: float) -> None:
        self.show_value(value)
        self.previewed.emit(self.key, value)

    def show_value(self, value: float) -> None:
        self.field.blockSignals(True)
        self.field.setValue(value)
        self.field.blockSignals(False)
        self._describe(value)

    def _describe(self, value: float) -> None:
        normal = self.parameter.value
        changed = abs(value - normal) > 1e-12 * max(1.0, abs(normal))
        badge = self.scale.badge(value, normal) if changed else ""
        note = (self.up_note if value > normal else self.down_note) if changed else ""
        self.badge.setText(badge)
        self.badge.setVisible(bool(badge))
        self.note.setText(note)
        self.note.setVisible(bool(note))

    def set_value(self, value: float, edited: bool) -> None:
        self.edited = edited
        self.show_value(value)
        set_flag(self.field, "edited", edited)
        set_tone(self.label, "edited" if edited else "")
        self.reset.setVisible(edited)
        if isinstance(self.control, ValueBar):
            self.control.set_value(value, edited)
        elif isinstance(self.control, StopSwitch):
            self.control.set_value(value)
