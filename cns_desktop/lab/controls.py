from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSizePolicy, QWidget

from cns_atlas.models import Curve, LabModel, Parameter
from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import COLOURS, GAP, SIZE
from cns_desktop.design.widgets import SegmentedControl

from .scales import ClockScale, Scale, curve_points

SNAP = 0.015
KEY_STEP = 0.01
PAGE_STEP = 0.1
WHEEL_STEP = 0.01
WHEEL_SETTLE_MS = 400
CURVE_POINTS = 80


def colour(name: str, alpha: int = 255) -> QColor:
    result = QColor(COLOURS[name])
    result.setAlpha(alpha)
    return result


class ClockSpinBox(QDoubleSpinBox):
    def textFromValue(self, value: float) -> str:
        return ClockScale.text(value)

    def valueFromText(self, text: str) -> float:
        hours, _, minutes = text.strip().partition(":")
        try:
            return float(int(hours) * 60 + int(minutes or 0))
        except ValueError:
            return self.value()

    def validate(self, text: str, pos: int):
        hours, colon, minutes = text.strip().partition(":")
        if not all(part.isdigit() or part == "" for part in (hours, minutes)) or text.count(":") > 1:
            return (QValidator.State.Invalid, text, pos)
        if hours and (not colon or len(minutes) == 2):
            whole = int(hours) * 60 + int(minutes or 0)
            if self.minimum() <= whole <= self.maximum():
                return (QValidator.State.Acceptable, text, pos)
        return (QValidator.State.Intermediate, text, pos)


class ScaleSlider(QWidget):
    previewed = Signal(float)
    committed = Signal(float)

    def __init__(self, scale: Scale, value: float, normal: float, parent=None) -> None:
        super().__init__(parent)
        self.scale = scale
        self.normal = normal
        self._value = value
        self._edited = False
        self._dragging = False
        self._grab = 0.0
        self._pressed = value
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(SIZE["slider"])
        self.setMinimumWidth(SIZE["field_min"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float, edited: bool = False) -> None:
        self._value, self._edited = value, edited
        self.update()

    def label_rects(self) -> list[tuple[QRectF, str]]:
        metrics = QFontMetrics(font("data"))
        track = self.track_rect()
        top = track.bottom() + GAP["medium"]
        marks = sorted(self.scale.marks(), key=lambda m: m[1] != "normal")
        kept: list[tuple[QRectF, str]] = []
        for fraction, label in marks:
            width = metrics.horizontalAdvance(label)
            x = track.left() + fraction * track.width() - width / 2
            x = min(max(x, 0.0), self.width() - width)
            rect = QRectF(x, top, width, metrics.height())
            padded = rect.adjusted(-GAP["tight"], 0, GAP["tight"], 0)
            if not any(padded.intersects(other) for other, _ in kept):
                kept.append((rect, label))
        return sorted(kept, key=lambda k: k[0].left())

    def track_rect(self) -> QRect:
        pad = SIZE["handle"] // 2 + 1
        return QRect(pad, pad, max(self.width() - 2 * pad, 1), GAP["tight"] // 2)

    def _value_at(self, x: float) -> float:
        track = self.track_rect()
        fraction = (x - track.left()) / track.width()
        if abs(fraction - self.scale.fraction(self.normal)) < SNAP:
            return self.normal
        return self.scale.value(fraction)

    def _preview(self, value: float) -> None:
        self._value = value
        self.update()
        self.previewed.emit(value)

    def _handle_x(self) -> float:
        track = self.track_rect()
        return track.left() + self.scale.fraction(self._value) * track.width()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._pressed = self._value
        x = event.position().x()
        offset = x - self._handle_x()
        if abs(offset) <= SIZE["handle"] / 2 + 1:
            self._grab = offset
        else:
            self._grab = 0.0
            self._preview(self._value_at(x))

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._preview(self._value_at(event.position().x() - self._grab))

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self._value != self._pressed:
                self.committed.emit(self._value)

    def keyPressEvent(self, event) -> None:
        steps = {Qt.Key.Key_Left: -KEY_STEP, Qt.Key.Key_Right: KEY_STEP,
                 Qt.Key.Key_PageDown: -PAGE_STEP, Qt.Key.Key_PageUp: PAGE_STEP}
        step = steps.get(event.key())
        if step is None:
            super().keyPressEvent(event)
            return
        self._preview(self.scale.value(self.scale.fraction(self._value) + step))

    def keyReleaseEvent(self, event) -> None:
        keys = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp)
        if event.key() in keys and not event.isAutoRepeat():
            self.committed.emit(self._value)
        else:
            super().keyReleaseEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self.track_rect()
        mid = track.center().y() + 0.5
        tone = colour("edited" if self._edited else "accent")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour("s3"))
        painter.drawRoundedRect(QRectF(track), track.height() / 2, track.height() / 2)
        here = track.left() + self.scale.fraction(self._value) * track.width()
        normal = track.left() + self.scale.fraction(self.normal) * track.width()
        painter.setBrush(tone)
        painter.drawRect(QRectF(min(here, normal), track.top(), abs(here - normal), track.height()))
        painter.setPen(QPen(colour("text2"), 1.5))
        painter.drawLine(QPointF(normal, mid - GAP["small"] + 1), QPointF(normal, mid + GAP["small"] - 1))
        painter.setFont(font("data"))
        painter.setPen(colour("text3"))
        ascent = painter.fontMetrics().ascent()
        for rect, label in self.label_rects():
            painter.drawText(QPointF(rect.left(), rect.top() + ascent), label)
        radius = SIZE["handle"] / 2
        painter.setPen(QPen(tone, 2))
        painter.setBrush(colour("text"))
        painter.drawEllipse(QPointF(here, mid), radius - 1, radius - 1)
        if self.hasFocus():
            painter.setPen(QPen(colour("accent_text"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(here, mid), radius + 1, radius + 1)


class StopSwitch(QWidget):
    committed = Signal(float)

    def __init__(self, parameter: Parameter, parent=None) -> None:
        super().__init__(parent)
        self.parameter = parameter
        self._updating = False
        self.segments = SegmentedControl([(s.key, s.name) for s in parameter.stops])
        self.segments.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.segments.setMinimumWidth(SIZE["field_min"])
        for stop in parameter.stops:
            self.segments.button(stop.key).setSizePolicy(QSizePolicy.Policy.Ignored,
                                                     QSizePolicy.Policy.Fixed)
        self.segments.changed.connect(self._on_changed)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.segments, 1)
        self.set_value(parameter.value)

    def set_value(self, value: float) -> None:
        stop = next((s for s in self.parameter.stops if abs(s.value - value) < 1e-9), None)
        self._updating = True
        try:
            if stop is None:
                self.segments.clear()
            else:
                self.segments.set_current(stop.key)
        finally:
            self._updating = False

    def current(self) -> str | None:
        return self.segments.current() or None

    def choose(self, key: str) -> None:
        self.segments.set_current(key)

    def _on_changed(self, key: str) -> None:
        if not self._updating:
            stop = next(s for s in self.parameter.stops if s.key == key)
            self.committed.emit(stop.value)


class CurveGraph(QWidget):
    previewed = Signal(str, float)
    committed = Signal(str, float)

    def __init__(self, model: LabModel, curve: Curve, values: dict[str, float], parent=None) -> None:
        super().__init__(parent)
        self.model, self.curve = model, curve
        self._values = dict(values)
        self._edited = False
        self._dragging = False
        self._engaged = False
        self._grab = 0.0
        self._pressed = 0.0
        self._normal = curve_points(model, curve, {}, CURVE_POINTS)
        self._settle = QTimer(self, singleShot=True, interval=WHEEL_SETTLE_MS)
        self._settle.timeout.connect(self._commit_wheel)
        self.handle = model.parameter(curve.parameters[0])
        self.second = model.parameter(curve.parameters[1]) if len(curve.parameters) > 1 else None
        self.setFixedHeight(SIZE["curve"])
        self.setMinimumWidth(SIZE["field_min"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        tip = f"Drag the dot to move {self.handle.name.lower()}"
        if self.second is not None:
            tip += f"; scroll to change {self.second.name.lower()}"
        self.setToolTip(tip)

    def values(self) -> dict[str, float]:
        return dict(self._values)

    def set_values(self, values: dict[str, float], edited: bool = False) -> None:
        self._values, self._edited = dict(values), edited
        self.update()

    def _value(self, key: str) -> float:
        return self._values.get(key, self.model.parameter(key).value)

    def _plot(self) -> QRectF:
        pad = SIZE["handle"] / 2 + 1
        text = font("data")
        line = QFontMetrics(text).height()
        return QRectF(pad, pad + line, max(self.width() - 2 * pad, 1.0),
                      max(self.height() - 2 * pad - 2 * line, 1.0))

    def _x_of(self, x: float, plot: QRectF) -> float:
        span = self.curve.x_high - self.curve.x_low
        return plot.left() + (x - self.curve.x_low) / span * plot.width()

    def _handle_at(self, px: float) -> float:
        plot = self._plot()
        span = self.curve.x_high - self.curve.x_low
        x = self.curve.x_low + (px - plot.left()) / plot.width() * span
        x = min(max(x, self.handle.low), self.handle.high)
        if abs(x - self.handle.value) / span < SNAP:
            return self.handle.value
        return x

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._engaged = True
        self._dragging = True
        self._pressed = self._value(self.handle.key)
        x = event.position().x()
        offset = x - self._x_of(self._pressed, self._plot())
        if abs(offset) <= SIZE["handle"] / 2 + 1:
            self._grab = offset
        else:
            self._grab = 0.0
            self._move(x)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._move(event.position().x() - self._grab)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            value = self._value(self.handle.key)
            if value != self._pressed:
                self.committed.emit(self.handle.key, value)

    def leaveEvent(self, event) -> None:
        self._engaged = False
        super().leaveEvent(event)

    def _move(self, px: float) -> None:
        self._values[self.handle.key] = self._handle_at(px)
        self.update()
        self.previewed.emit(self.handle.key, self._values[self.handle.key])

    def wheelEvent(self, event) -> None:
        if self.second is None or not self._engaged:
            event.ignore()
            return
        notches = event.angleDelta().y() / 120
        if not notches:
            return
        p = self.second
        value = self._value(p.key) + notches * WHEEL_STEP * (p.high - p.low)
        self._values[p.key] = min(max(value, p.low), p.high)
        self.update()
        self.previewed.emit(p.key, self._values[p.key])
        self._settle.start()
        event.accept()

    def _commit_wheel(self) -> None:
        if self.second is not None:
            self.committed.emit(self.second.key, self._value(self.second.key))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        current = curve_points(self.model, self.curve, self._values, CURVE_POINTS)
        ys = [y for _, y in (*self._normal, *current) if math.isfinite(y)]
        low, high = (min(ys), max(ys)) if ys else (0.0, 1.0)
        if high - low < 1e-12:
            low, high = low - 1.0, high + 1.0

        def point(x: float, y: float) -> QPointF:
            return QPointF(self._x_of(x, plot), plot.bottom() - (y - low) / (high - low) * plot.height())

        def path(points) -> QPainterPath:
            result = QPainterPath()
            started = False
            for x, y in points:
                if not math.isfinite(y):
                    started = False
                    continue
                if started:
                    result.lineTo(point(x, y))
                else:
                    result.moveTo(point(x, y))
                    started = True
            return result

        painter.setPen(QPen(colour("line"), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.setPen(QPen(colour("text3"), 1, Qt.PenStyle.DashLine))
        painter.drawPath(path(self._normal))
        tone = colour("edited" if self._edited else "accent")
        painter.setPen(QPen(tone, 2))
        painter.drawPath(path(current))
        hx = self._value(self.handle.key)
        here = self._x_of(hx, plot)
        painter.setPen(QPen(tone, 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(here, plot.top()), QPointF(here, plot.bottom()))
        values = dict(current)
        nearest = min(values, key=lambda x: abs(x - hx))
        y = values[nearest] if math.isfinite(values[nearest]) else low
        radius = SIZE["handle"] / 2
        painter.setPen(QPen(tone, 2))
        painter.setBrush(colour("text"))
        painter.drawEllipse(point(nearest, y), radius - 1, radius - 1)
        painter.setFont(font("data"))
        painter.setPen(colour("text3"))
        metrics = painter.fontMetrics()
        painter.drawText(QPointF(plot.left(), plot.top() - metrics.descent() - 1), self.curve.y_name)
        x_text = f"{self.curve.x_name} →"
        painter.drawText(QPointF(plot.left(), plot.bottom() + metrics.ascent() + 1), x_text)
