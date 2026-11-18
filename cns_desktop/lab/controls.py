from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSizePolicy, QWidget

from cns_atlas.models import Curve, LabModel, Parameter
from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import COLOURS, GAP, RADIUS, SIZE
from cns_desktop.design.widgets import SegmentedControl

from .scales import ClockScale, Scale, curve_points

SNAP = 0.015
KEY_STEP = 0.01
PAGE_STEP = 0.1
WHEEL_STEP = 0.01
WHEEL_SETTLE_MS = 400
CURVE_POINTS = 80
DRAG_START = 3
FILL_ALPHA = 60


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


class ValueBar(QWidget):
    previewed = Signal(float)
    committed = Signal(float)

    def __init__(self, scale: Scale, value: float, normal: float, editor: QDoubleSpinBox,
                 unit: str = "", parent=None) -> None:
        super().__init__(parent)
        self.scale = scale
        self.normal = normal
        self.editor = editor
        self.unit = unit
        self._value = value
        self._edited = False
        self._press: float | None = None
        self._start = 0.0
        self._dragging = False
        self._pressed = value
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(SIZE["control"])
        self.setMinimumWidth(SIZE["field_min"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        editor.setParent(self)
        editor.hide()
        editor.installEventFilter(self)
        editor.editingFinished.connect(self.close_editor)

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float, edited: bool = False) -> None:
        self._value, self._edited = value, edited
        self.update()

    def track_rect(self) -> QRect:
        return self.rect().adjusted(1, 1, -1, -1)

    def editing(self) -> bool:
        return self.editor.isVisible()

    def open_editor(self) -> None:
        self.editor.blockSignals(True)
        self.editor.setValue(self._value)
        self.editor.blockSignals(False)
        self._place_editor()
        self.editor.show()
        self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self.editor.selectAll()

    def close_editor(self) -> None:
        if self.editor.isVisible():
            self.editor.hide()
            self.update()

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.editor and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape):
            self.editor.blockSignals(True)
            self.editor.setValue(self._value)
            self.editor.blockSignals(False)
            self.editor.hide()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        return super().eventFilter(watched, event)

    def _place_editor(self) -> None:
        height = min(self.editor.sizeHint().height(), self.editor.maximumHeight(), self.height())
        self.editor.setGeometry(0, (self.height() - height) // 2, self.width(), height)

    def resizeEvent(self, event) -> None:
        self._place_editor()
        super().resizeEvent(event)

    def _at(self, fraction: float) -> float:
        if abs(fraction - self.scale.fraction(self.normal)) < SNAP:
            return self.normal
        return self.scale.value(fraction)

    def _preview(self, value: float) -> None:
        self._value = value
        self.update()
        self.previewed.emit(value)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press = event.position().x()
        self._start = self.scale.fraction(self._value)
        self._pressed = self._value
        self._dragging = False

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return
        moved = event.position().x() - self._press
        if not self._dragging and abs(moved) < DRAG_START:
            return
        self._dragging = True
        self._preview(self._at(self._start + moved / max(self.track_rect().width(), 1)))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        self._press = None
        if self._dragging:
            self._dragging = False
            if self._value != self._pressed:
                self.committed.emit(self._value)
        else:
            self.open_editor()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2):
            self.open_editor()
            return
        steps = {Qt.Key.Key_Left: -KEY_STEP, Qt.Key.Key_Right: KEY_STEP,
                 Qt.Key.Key_PageDown: -PAGE_STEP, Qt.Key.Key_PageUp: PAGE_STEP}
        step = steps.get(event.key())
        if step is None:
            super().keyPressEvent(event)
            return
        self._preview(self._at(self.scale.fraction(self._value) + step))

    def keyReleaseEvent(self, event) -> None:
        keys = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp)
        if event.key() in keys and not event.isAutoRepeat():
            self.committed.emit(self._value)
        else:
            super().keyReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        event.ignore()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = RADIUS["control"]
        tone = "edited" if self._edited else "accent"
        border = "accent" if self.hasFocus() else ("edited" if self._edited else "line")
        painter.setPen(QPen(colour(border), 1))
        painter.setBrush(colour("s0"))
        painter.drawRoundedRect(frame, radius, radius)
        inner = QRectF(self.track_rect())
        clip = QPainterPath()
        clip.addRoundedRect(inner, radius - 1, radius - 1)
        painter.setClipPath(clip)
        here = inner.left() + self.scale.fraction(self._value) * inner.width()
        normal = inner.left() + self.scale.fraction(self.normal) * inner.width()
        moved = abs(here - normal) >= 1
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour("s3" if self.underMouse() else "s2"))
        painter.drawRect(QRectF(inner.left(), inner.top(), here - inner.left(), inner.height()))
        if moved:
            painter.setBrush(colour(tone, FILL_ALPHA))
            painter.drawRect(QRectF(min(here, normal), inner.top(), abs(here - normal),
                                    inner.height()))
            painter.setPen(QPen(colour("text3"), 1))
            inset = GAP["tight"] + 1
            painter.drawLine(QPointF(normal, inner.top() + inset),
                             QPointF(normal, inner.bottom() - inset))
        painter.setClipping(False)
        painter.setFont(font("label"))
        metrics = painter.fontMetrics()
        text = self.editor.textFromValue(self._value)
        unit_width = metrics.horizontalAdvance(self.unit) if self.unit else 0
        right = inner.right() - GAP["small"]
        width = metrics.horizontalAdvance(text) + (unit_width + GAP["tight"] if self.unit else 0)
        words = QRectF(right - width - GAP["tight"], inner.top(), width + GAP["small"],
                       inner.height())
        if not words.left() <= here <= words.right():
            painter.setClipPath(clip)
            painter.setPen(QPen(colour(tone if moved else "control"), 2))
            painter.drawLine(QPointF(here, inner.top()), QPointF(here, inner.bottom()))
            painter.setClipping(False)
        base = inner.center().y() + (metrics.ascent() - metrics.descent()) / 2
        if self.unit:
            painter.setPen(colour("text3"))
            painter.drawText(QPointF(right - unit_width, base), self.unit)
            right -= unit_width + GAP["tight"]
        painter.setPen(colour("edited" if self._edited else "text"))
        painter.drawText(QPointF(right - metrics.horizontalAdvance(text), base), text)


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
