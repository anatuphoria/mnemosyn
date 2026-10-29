from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from .experiments_panel import MIME

LABEL_WIDTH = 110
RULER_HEIGHT = 22
CHANGES_HEIGHT = 34
LANE_HEIGHT = 44
EDGE = 6
MIN_BLOCK_WIDTH = 6
MIN_SPAN = 30.0
INK = QColor("#d8d8e0")
MUTED = QColor("#7a7a88")
NORMAL = QColor("#55556a")
BLOCK = QColor("#d9a441")
PLAYHEAD = QColor("#e8e6df")
LANE_COLORS = ("#e08a5a", "#d9a441", "#6fa0ff", "#86c8a0", "#c896e6", "#e6c86f")
DAY = 1440.0


def time_text(minutes: float) -> str:
    minutes = round(minutes)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h" if hours else f"{days} d"
    return f"{hours} h {mins} min" if mins else f"{hours} h"


class Timeline(QWidget):
    edit_requested = Signal(int)

    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.compare_on = True
        self.hidden: set[str] = set()
        self.span = (0.0, document.experiment.length)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumHeight(RULER_HEIGHT + CHANGES_HEIGHT + LANE_HEIGHT)
        self._press = None
        self._cache: QPixmap | None = None
        self._cache_key = None
        self._length = document.experiment.length
        document.changed.connect(self._on_changed)
        document.model_changed.connect(self._on_model)
        document.playhead_moved.connect(lambda _t: self.update())
        document.selection_changed.connect(lambda _s: self.update())

    @property
    def compare(self) -> bool:
        return self.compare_on

    @compare.setter
    def compare(self, on: bool) -> None:
        self.compare_on = bool(on)
        self.update()

    def _on_model(self) -> None:
        self.hidden.clear()
        self._length = self.document.experiment.length
        self.span = (0.0, self._length)
        self._cache = None

    def _on_changed(self) -> None:
        length = self.document.experiment.length
        if length != self._length:
            self._length = length
            self.span = (0.0, length)
        self.update()

    def lane_keys(self) -> list[str]:
        values = [v for v in self.document.model.values if v.lane is not None]
        return [v.key for v in sorted(values, key=lambda v: v.lane) if v.key not in self.hidden]

    def hide_lane(self, key: str) -> None:
        self.hidden.add(key)
        self.update()

    def show_lanes(self) -> None:
        self.hidden.clear()
        self.update()

    def _plot_width(self) -> float:
        return max(self.width() - LABEL_WIDTH - 8, 10)

    def x_of(self, t: float) -> float:
        start, end = self.span
        return LABEL_WIDTH + (t - start) / (end - start) * self._plot_width()

    def t_of(self, x: float) -> float:
        start, end = self.span
        return start + (x - LABEL_WIDTH) / self._plot_width() * (end - start)

    def _snap(self, t: float) -> float:
        step = 1.0 if self.span[1] - self.span[0] < 2 * DAY else 15.0
        return round(t / step) * step

    def zoom(self, factor: float, around: float) -> None:
        length = self.document.experiment.length
        start, end = self.span
        width = min(max((end - start) * factor, MIN_SPAN), length)
        share = (around - start) / (end - start) if end > start else 0.5
        start = around - share * width
        start = min(max(start, 0.0), length - width)
        self.span = (start, start + width)
        self.update()

    def _pan(self, minutes: float) -> None:
        length = self.document.experiment.length
        start, end = self.span
        width = end - start
        start = min(max(start + minutes, 0.0), length - width)
        self.span = (start, start + width)
        self.update()

    def lane_rect(self, key: str) -> QRectF:
        index = self.lane_keys().index(key)
        top = RULER_HEIGHT + CHANGES_HEIGHT + index * LANE_HEIGHT
        return QRectF(LABEL_WIDTH, top, self._plot_width(), LANE_HEIGHT)

    def block_rect(self, index: int, preview: tuple[float, float | None] | None = None) -> QRectF:
        block = self.document.experiment.blocks[index]
        length = self.document.experiment.length
        start, size = preview if preview is not None else (block.start, block.length)
        if block.present:
            left, right = 0.0, length
        else:
            left = start
            right = start + size if size is not None else length
        x0 = self.x_of(left)
        x1 = max(self.x_of(right), x0 + MIN_BLOCK_WIDTH)
        return QRectF(x0, RULER_HEIGHT + 4, x1 - x0, CHANGES_HEIGHT - 8)

    def _block_at(self, pos: QPointF) -> int | None:
        blocks = self.document.experiment.blocks
        newest_first = list(reversed(range(len(blocks))))
        order = [i for i in newest_first if not blocks[i].present]
        for index in order + [i for i in newest_first if blocks[i].present]:
            if self.block_rect(index).contains(pos):
                return index
        return None

    def lane_lines(self, key: str) -> dict[str, np.ndarray]:
        start, end = self.span
        grid = np.linspace(start, end, max(int(self._plot_width()), 2))
        lines = {}
        doc = self.document
        runs = [("run", doc.run)]
        if self.compare_on:
            runs.append(("normal", doc.normal))
        if doc.snapshot is not None:
            runs.append(("snapshot", doc.snapshot))
        for name, run in runs:
            if run is not None:
                lines[name] = np.interp(grid, run.times, run.value(key))
        return lines

    def _background(self) -> QPixmap:
        doc = self.document
        key = (self.size().toTuple(), self.span, self.compare_on, frozenset(self.hidden),
               id(doc.run), id(doc.normal), id(doc.snapshot))
        if self._cache is None or key != self._cache_key:
            ratio = self.devicePixelRatioF()
            pixmap = QPixmap(self.size() * ratio)
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(QColor("#14141b"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_ruler(painter)
            for n, lane in enumerate(self.lane_keys()):
                self._paint_lane(painter, lane, QColor(LANE_COLORS[n % len(LANE_COLORS)]))
            painter.end()
            self._cache, self._cache_key = pixmap, key
        return self._cache

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_blocks(painter)
        x = self.x_of(self.document.playhead)
        painter.setPen(QPen(PLAYHEAD, 2))
        painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        painter.setPen(MUTED)
        start, end = self.span
        steps = [30, 60, 120, 240, 360, 720, 1440, 2880, 10080]
        step = next((s for s in steps if (end - start) / s <= 8), 10080)
        tick = (start // step) * step
        while tick <= end:
            x = self.x_of(tick)
            if x >= LABEL_WIDTH:
                painter.drawLine(QPointF(x, RULER_HEIGHT - 6), QPointF(x, RULER_HEIGHT))
                painter.drawText(QPointF(x + 3, RULER_HEIGHT - 8), time_text(tick))
            tick += step
        painter.drawText(QPointF(6, RULER_HEIGHT + CHANGES_HEIGHT / 2 + 4), "Changes")

    def _paint_blocks(self, painter: QPainter) -> None:
        doc = self.document
        blocks = doc.experiment.blocks
        for index in sorted(range(len(blocks)), key=lambda i: not blocks[i].present):
            block = blocks[index]
            preview = None
            if self._press and self._press.get("block") == index and "preview" in self._press:
                preview = self._press["preview"]
            rect = self.block_rect(index, preview)
            fill = QColor(BLOCK)
            fill.setAlpha(60 if block.present else 90)
            painter.setBrush(fill)
            selected = doc.selection == ("block", index)
            painter.setPen(QPen(PLAYHEAD if selected else BLOCK, 2 if selected else 1))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(BLOCK if not selected else PLAYHEAD)
            painter.drawText(rect.adjusted(5, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter,
                             doc.name_of(block.experiment))

    def _paint_lane(self, painter: QPainter, key: str, color: QColor) -> None:
        rect = self.lane_rect(key)
        value = self.document.simulator.values[key]
        painter.setPen(MUTED)
        painter.drawText(QPointF(6, rect.center().y() + 4), value.name)
        painter.drawLine(QPointF(0, rect.top()), QPointF(self.width(), rect.top()))
        lines = self.lane_lines(key)
        if not lines:
            return
        low = min(float(v.min()) for v in lines.values())
        high = max(float(v.max()) for v in lines.values())
        if high - low < 1e-9:
            low, high = low - 0.5, high + 0.5
        xs = np.linspace(rect.left(), rect.right(), len(next(iter(lines.values()))))
        for name in ("normal", "snapshot", "run"):
            if name not in lines:
                continue
            ys = rect.bottom() - 4 - (lines[name] - low) / (high - low) * (rect.height() - 8)
            path = QPainterPath(QPointF(xs[0], ys[0]))
            for x, y in zip(xs[1:], ys[1:]):
                path.lineTo(x, y)
            pen = QPen(NORMAL if name == "normal" else color, 1.5 if name == "normal" else 2)
            if name == "snapshot":
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus()
        if pos.y() < RULER_HEIGHT:
            self._press = {"kind": "scrub"}
            self.document.set_playhead(self.t_of(pos.x()))
            return
        index = self._block_at(pos)
        if index is not None:
            block = self.document.experiment.blocks[index]
            self.document.select(("block", index))
            if block.present:
                self._press = None
                return
            rect = self.block_rect(index)
            stretch = block.length is not None and pos.x() >= rect.right() - EDGE
            self._press = {"kind": "stretch" if stretch else "move", "block": index,
                           "x": pos.x(), "start": block.start, "length": block.length}
            return
        self._press = {"kind": "pan", "x": pos.x()}

    def _limits(self, start: float, length: float | None) -> tuple[float, float | None]:
        run = self.document.experiment.length
        start = min(max(start, 0.0), run - 1)
        if length is not None:
            length = min(max(length, 1.0), run - start)
        return start, length

    def mouseMoveEvent(self, event) -> None:
        press = self._press
        if not press or not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        x = event.position().x()
        if press["kind"] == "scrub":
            self.document.set_playhead(self.t_of(x))
            return
        minutes = (x - press["x"]) / self._plot_width() * (self.span[1] - self.span[0])
        if press["kind"] == "pan":
            self._pan(-minutes)
            press["x"] = x
            return
        if press["kind"] == "move":
            start, length = self._limits(self._snap(press["start"] + minutes), press["length"])
            if length is not None and start + length > self.document.experiment.length:
                start = self.document.experiment.length - length
        else:
            start, length = self._limits(press["start"],
                                         self._snap(press["length"] + minutes))
        press["preview"] = (start, length)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        press, self._press = self._press, None
        if not press or "preview" not in press:
            self.update()
            return
        start, length = press["preview"]
        index = press["block"]
        if press["kind"] == "move" and start != press["start"]:
            self.document.move_block(index, start)
        elif press["kind"] == "stretch" and length != press["length"]:
            self.document.stretch_block(index, length)
        self.update()

    def wheelEvent(self, event) -> None:
        steps = event.angleDelta().y() / 120
        if not steps:
            return
        self.zoom(0.8 ** steps, self.t_of(event.position().x()))
        event.accept()

    def keyPressEvent(self, event) -> None:
        selection = self.document.selection
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and selection and (
                selection[0] == "block"):
            self.document.delete_block(selection[1])
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        data = event.mimeData()
        if not data.hasFormat(MIME):
            return
        key = bytes(data.data(MIME)).decode("utf-8")
        self.document.add_block(key, self._snap(self.t_of(event.position().x())))
        event.acceptProposedAction()

    def contextMenuEvent(self, event) -> None:
        pos = QPointF(event.pos())
        menu = QMenu(self)
        index = self._block_at(pos)
        if index is not None:
            self.document.select(("block", index))
            menu.addAction(QAction("Edit", menu, triggered=lambda: self.edit_requested.emit(index)))
            menu.addAction(QAction("Duplicate", menu,
                                   triggered=lambda: self.document.duplicate_block(index)))
            menu.addAction(QAction("Delete", menu,
                                   triggered=lambda: self.document.delete_block(index)))
        else:
            lane = next((k for k in self.lane_keys() if self.lane_rect(k).contains(pos)), None)
            if lane is not None:
                menu.addAction(QAction("Hide lane", menu, triggered=lambda: self.hide_lane(lane)))
            if self.hidden:
                menu.addAction(QAction("Show every lane", menu, triggered=self.show_lanes))
            toggle = QAction("Show normal line", menu, checkable=True, checked=self.compare_on)
            toggle.toggled.connect(lambda on: setattr(self, "compare", on))
            menu.addAction(toggle)
        menu.exec(event.globalPos())
