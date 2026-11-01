from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from cns_desktop.design import icons
from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import DATA_PALETTE, RADIUS, SIZE, color

from .experiments_panel import MIME, icon_for

LABEL_WIDTH = 150
RULER_HEIGHT = 24
CHANGES_HEIGHT = SIZE["lane"]
LANE_HEIGHT = SIZE["lane"]
PAD = SIZE["panel_pad"]
EDGE = 6
GRAB = 5
SWIPE = 0.1
MIN_BLOCK_WIDTH = 6
MIN_SPAN = 30.0
INK = color("text")
MUTED = color("text2")
NORMAL = color("normal")
BLOCK = color("edited")
PLAYHEAD = color("text")
LINE = color("line")
BACKGROUND = color("s1")
LANE_COLORS = DATA_PALETTE
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
        self._press = None
        self._cache: QPixmap | None = None
        self._cache_key = None
        self._length = document.experiment.length
        document.changed.connect(self._on_changed)
        self._fit_height()
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
        self._fit_height()

    def _fit_height(self) -> None:
        self.setMinimumHeight(round(self._lanes_top() + len(self.lane_keys()) * LANE_HEIGHT))

    def _on_changed(self) -> None:
        length = self.document.experiment.length
        if length != self._length:
            self._length = length
            self.span = (0.0, length)
        self._fit_height()
        self.update()

    def lane_keys(self) -> list[str]:
        values = [v for v in self.document.model.values if v.lane is not None]
        return [v.key for v in sorted(values, key=lambda v: v.lane) if v.key not in self.hidden]

    def hide_lane(self, key: str) -> None:
        self.hidden.add(key)
        self._fit_height()
        self.update()

    def show_lanes(self) -> None:
        self.hidden.clear()
        self._fit_height()
        self.update()

    def _plot_width(self) -> float:
        return max(self.width() - LABEL_WIDTH - 8, 10)

    def _plot_area(self) -> QRectF:
        return QRectF(LABEL_WIDTH, 0, self.width() - LABEL_WIDTH, self.height())

    def _block_span(self, index: int) -> tuple[float, float]:
        block = self.document.experiment.blocks[index]
        length = self.document.experiment.length
        if block.present:
            return 0.0, length
        return block.start, block.start + block.length if block.length is not None else length

    def block_rows(self) -> list[int]:
        blocks = self.document.experiment.blocks
        order = sorted(range(len(blocks)),
                       key=lambda i: (not blocks[i].present, self._block_span(i)[0], i))
        ends: list[float] = []
        rows = [0] * len(blocks)
        for index in order:
            start, end = self._block_span(index)
            row = next((r for r, last in enumerate(ends) if last <= start), len(ends))
            if row == len(ends):
                ends.append(end)
            else:
                ends[row] = end
            rows[index] = row
        return rows

    def _changes_height(self) -> float:
        return CHANGES_HEIGHT * max(max(self.block_rows(), default=0) + 1, 1)

    def _lanes_top(self) -> float:
        return RULER_HEIGHT + self._changes_height()

    def _lane_height(self) -> float:
        count = max(len(self.lane_keys()), 1)
        return max(LANE_HEIGHT, (self.height() - self._lanes_top()) / count)

    def x_of(self, t: float) -> float:
        start, end = self.span
        return LABEL_WIDTH + (t - start) / (end - start) * self._plot_width()

    def t_of(self, x: float) -> float:
        start, end = self.span
        return start + (x - LABEL_WIDTH) / self._plot_width() * (end - start)

    def _snap(self, t: float) -> float:
        step = 1.0 if self.span[1] - self.span[0] < 2 * DAY else 15.0
        return round(t / step) * step

    def show_whole_run(self) -> None:
        self.span = (0.0, self.document.experiment.length)
        self.update()

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
        height = self._lane_height()
        return QRectF(LABEL_WIDTH, self._lanes_top() + index * height, self._plot_width(), height)

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
        top = RULER_HEIGHT + self.block_rows()[index] * CHANGES_HEIGHT
        return QRectF(x0, top + 4, x1 - x0, CHANGES_HEIGHT - 8)

    def _block_at(self, pos: QPointF) -> int | None:
        if pos.x() < LABEL_WIDTH:
            return None
        blocks = self.document.experiment.blocks
        newest_first = list(reversed(range(len(blocks))))
        order = [i for i in newest_first if not blocks[i].present]
        for index in order + [i for i in newest_first if blocks[i].present]:
            if self.block_rect(index).contains(pos):
                return index
        return None

    def lane_heading(self, key: str) -> tuple[str, str]:
        value = self.document.simulator.values[key]
        return value.name, value.display_unit

    def block_icon(self, index: int) -> str:
        return icon_for(self.document.model, self.document.experiment.blocks[index].experiment)

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
               self._changes_height(), id(doc.run), id(doc.normal), id(doc.snapshot))
        if self._cache is None or key != self._cache_key:
            ratio = self.devicePixelRatioF()
            pixmap = QPixmap(self.size() * ratio)
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(BACKGROUND)
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
        painter.setClipRect(self._plot_area())
        self._paint_blocks(painter)
        x = self.x_of(self.document.playhead)
        painter.setPen(QPen(PLAYHEAD, 2))
        painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, RULER_HEIGHT), QPointF(self.width(), RULER_HEIGHT))
        painter.drawLine(QPointF(LABEL_WIDTH, 0), QPointF(LABEL_WIDTH, self.height()))
        painter.setFont(font("data"))
        painter.setPen(MUTED)
        for x, rect, text in self.ruler_labels():
            painter.drawLine(QPointF(x, RULER_HEIGHT - 6), QPointF(x, RULER_HEIGHT))
            painter.drawText(rect, Qt.AlignmentFlag.AlignBottom, text)
        painter.setFont(font("label"))
        painter.setPen(INK)
        changes = self._changes_height()
        painter.drawText(QRectF(PAD, RULER_HEIGHT, LABEL_WIDTH - PAD, changes),
                         Qt.AlignmentFlag.AlignVCenter, "Changes")
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, RULER_HEIGHT + changes),
                         QPointF(self.width(), RULER_HEIGHT + changes))

    def ruler_labels(self) -> list[tuple[float, QRectF, str]]:
        metrics = QFontMetricsF(font("data"))
        start, end = self.span
        steps = [30, 60, 120, 240, 360, 720, 1440, 2880, 10080]
        step = next((s for s in steps if (end - start) / s <= 8), 10080)
        labels = []
        tick = (start // step) * step
        while tick <= end:
            x = self.x_of(tick)
            text = time_text(tick)
            rect = QRectF(x + 4, 0, metrics.horizontalAdvance(text), RULER_HEIGHT - 4)
            if rect.right() > self.width():
                rect.moveRight(x - 4)
            if x >= LABEL_WIDTH and rect.left() >= LABEL_WIDTH:
                labels.append((x, rect, text))
            tick += step
        return labels

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
            fill.setAlpha(40 if block.present else 64)
            painter.setBrush(fill)
            selected = doc.selection == ("block", index)
            painter.setPen(QPen(PLAYHEAD if selected else BLOCK, 2 if selected else 1))
            painter.drawRoundedRect(rect, RADIUS["small"], RADIUS["small"])
            text_rect = rect.adjusted(6, 0, -4, 0)
            if rect.width() > 40:
                size = SIZE["icon_header"]
                top = rect.center().y() - size / 2
                painter.drawPixmap(QPointF(rect.left() + 6, top),
                                   icons.pixmap(self.block_icon(index), "edited", size))
                text_rect = rect.adjusted(10 + size, 0, -4, 0)
            painter.setFont(font("secondary"))
            painter.setPen(INK if selected else BLOCK)
            name = painter.fontMetrics().elidedText(doc.name_of(block.experiment),
                                                    Qt.TextElideMode.ElideRight,
                                                    max(int(text_rect.width()), 0))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, name)

    def _paint_lane(self, painter: QPainter, key: str, color: QColor) -> None:
        rect = self.lane_rect(key)
        name, unit = self.lane_heading(key)
        head = QRectF(PAD, rect.top() + 6, LABEL_WIDTH - PAD - 8, rect.height() - 12)
        painter.setFont(font("label"))
        painter.setPen(INK)
        metrics = painter.fontMetrics()
        painter.drawText(head, Qt.AlignmentFlag.AlignTop,
                         metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(head.width())))
        painter.setFont(font("secondary"))
        painter.setPen(MUTED)
        painter.drawText(head, Qt.AlignmentFlag.AlignBottom, unit)
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, rect.bottom()), QPointF(self.width(), rect.bottom()))
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
        if pos.y() < RULER_HEIGHT or self._on_playhead(pos):
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

    def _on_playhead(self, pos: QPointF) -> bool:
        return pos.x() >= LABEL_WIDTH and abs(pos.x() - self.x_of(self.document.playhead)) <= GRAB

    def _limits(self, start: float, length: float | None) -> tuple[float, float | None]:
        run = self.document.experiment.length
        start = min(max(start, 0.0), run - 1)
        if length is not None:
            length = min(max(length, 1.0), run - start)
        return start, length

    def mouseMoveEvent(self, event) -> None:
        press = self._press
        if not press or not (event.buttons() & Qt.MouseButton.LeftButton):
            self._show_cursor(event.position())
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

    def _show_cursor(self, pos: QPointF) -> None:
        index = self._block_at(pos)
        if self._on_playhead(pos) or pos.y() < RULER_HEIGHT:
            shape = Qt.CursorShape.SizeHorCursor
        elif index is not None and not self.document.experiment.blocks[index].present:
            block = self.document.experiment.blocks[index]
            edge = block.length is not None and pos.x() >= self.block_rect(index).right() - EDGE
            shape = Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.OpenHandCursor
        else:
            shape = Qt.CursorShape.ArrowCursor
        self.setCursor(shape)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.position().y() < RULER_HEIGHT:
            self.show_whole_run()
            return
        super().mouseDoubleClickEvent(event)

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
        sideways, steps = event.angleDelta().x() / 120, event.angleDelta().y() / 120
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and not sideways:
            sideways, steps = steps, 0.0
        if sideways:
            self._pan(-sideways * SWIPE * (self.span[1] - self.span[0]))
        elif steps:
            self.zoom(0.8 ** steps, self.t_of(event.position().x()))
        else:
            return
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
            if self.span != (0.0, self.document.experiment.length):
                menu.addAction(QAction("Show the whole run", menu, triggered=self.show_whole_run))
            toggle = QAction("Show normal line", menu, checkable=True, checked=self.compare_on)
            toggle.toggled.connect(lambda on: setattr(self, "compare", on))
            menu.addAction(toggle)
        menu.exec(event.globalPos())
