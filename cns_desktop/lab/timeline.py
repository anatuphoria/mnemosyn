from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QScrollBar, QWidget

from cns_desktop.design import icons
from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import DATA_PALETTE, RADIUS, SIZE, color

from .experiments_panel import MIME, icon_for
from .labels import plain
from .lane_values import lane_scale, mark_text, tone

LABEL_WIDTH = 150
RULER_HEIGHT = 24
OVERVIEW_HEIGHT = SIZE["overview"]
RIGHT_MARGIN = 8
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
BAR = color("s2")
WINDOW = color("accent")
BAR_INSET = 5
BADGE_PAD = 6
BADGE_INSET = 3
GUIDE_ALPHA = 110
FINE_STEPS = 10
TAG_PAD = 4
HIGHLIGHT_MS = 1500
LANE_COLORS = DATA_PALETTE
NAME_ROW = 15
VALUE_GAP = 6
MARK_INSET = 4
MARK_BACKING = 210
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
        self._show_overview = True
        self.show_guides = True
        self._show_hover = True
        self._hover_pos: QPointF | None = None
        self.highlighted: str | None = None
        self._fade = QTimer(self, singleShot=True, timeout=lambda: self._highlight(None))
        self.hidden: set[str] = set()
        self.span = (0.0, document.experiment.length)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._press = None
        self._cache: QPixmap | None = None
        self._cache_key = None
        self._length = document.experiment.length
        self.scroll = QScrollBar(Qt.Orientation.Vertical, self)
        self.scroll.hide()
        self.scroll.valueChanged.connect(lambda _v: self.update())
        document.changed.connect(self._on_changed)
        self._fit_height()
        self._sync_scroll()
        document.model_changed.connect(self._on_model)
        document.playhead_moved.connect(lambda _t: self.update())
        document.selection_changed.connect(lambda _s: self.update())

    @property
    def show_overview(self) -> bool:
        return self._show_overview

    @show_overview.setter
    def show_overview(self, on: bool) -> None:
        self._show_overview = bool(on)
        self._fit_height()
        self._sync_scroll()
        self.update()

    @property
    def show_hover(self) -> bool:
        return self._show_hover

    @show_hover.setter
    def show_hover(self, on: bool) -> None:
        self._show_hover = bool(on)
        if not on:
            self._set_hover(None)

    @property
    def hover_t(self) -> float | None:
        return None if self._hover_pos is None else self._hover_at(self._hover_pos)

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
        self._hover_pos = None
        self.scroll.setValue(0)
        self._fit_height()
        self._sync_scroll()

    def _fit_height(self) -> None:
        self.setMinimumHeight(round(self.body_top() + CHANGES_HEIGHT + LANE_HEIGHT))

    def _on_changed(self) -> None:
        length = self.document.experiment.length
        if length != self._length:
            self._length = length
            self.span = (0.0, length)
            self.scroll.setValue(0)
            self._hover_pos = None
        self._sync_scroll()
        self.update()

    def overview_x(self, t: float) -> float:
        return LABEL_WIDTH + t / self.document.experiment.length * self._plot_width()

    def _overview_t(self, x: float) -> float:
        return (x - LABEL_WIDTH) / self._plot_width() * self.document.experiment.length

    def overview_window(self) -> QRectF:
        bar = self.overview_rect()
        left, right = self.overview_x(self.span[0]), self.overview_x(self.span[1])
        if right - left < 2 * GRAB:
            middle = (left + right) / 2
            left, right = middle - GRAB, middle + GRAB
        end = LABEL_WIDTH + self._plot_width()
        if left < LABEL_WIDTH:
            left, right = LABEL_WIDTH, right + LABEL_WIDTH - left
        if right > end:
            left, right = left - (right - end), end
        return QRectF(left, bar.top() + BAR_INSET, right - left, bar.height() - 2 * BAR_INSET)

    def _set_span(self, start: float, end: float) -> None:
        length = self.document.experiment.length
        width = min(max(end - start, MIN_SPAN), length)
        start = min(max(start, 0.0), length - width)
        self.span = (start, start + width)
        self.update()

    def _press_overview(self, pos: QPointF) -> None:
        window = self.overview_window()
        inside = window.left() <= pos.x() <= window.right()
        if inside and window.width() <= 4 * GRAB:
            kind = "window"
        elif abs(pos.x() - window.right()) <= GRAB:
            kind = "window_right"
        elif abs(pos.x() - window.left()) <= GRAB:
            kind = "window_left"
        else:
            kind = "window"
            if not window.contains(QPointF(pos.x(), window.center().y())) and pos.x() >= LABEL_WIDTH:
                width = self.span[1] - self.span[0]
                middle = self._overview_t(pos.x())
                self._set_span(middle - width / 2, middle + width / 2)
        self._press = {"kind": kind, "x": pos.x(), "span": self.span}

    def _drag_overview(self, press: dict, x: float) -> None:
        minutes = (x - press["x"]) / self._plot_width() * self.document.experiment.length
        start, end = press["span"]
        length = self.document.experiment.length
        if press["kind"] == "window":
            self._set_span(start + minutes, end + minutes)
        elif press["kind"] == "window_left":
            self._set_span(min(max(start + minutes, 0.0), end - MIN_SPAN), end)
        else:
            end = max(min(end + minutes, length), start + MIN_SPAN)
            self.span = (start, end)
            self.update()

    def overview_rect(self) -> QRectF:
        return QRectF(0, 0, self.width(), OVERVIEW_HEIGHT if self.show_overview else 0)

    def ruler_rect(self) -> QRectF:
        return QRectF(0, self.overview_rect().bottom(), self.width(), RULER_HEIGHT)

    def body_top(self) -> float:
        return self.ruler_rect().bottom()

    def _body_height(self) -> float:
        return self.changes_height() + len(self.lane_keys()) * LANE_HEIGHT

    def _sync_scroll(self) -> None:
        visible = self.height() - self.body_top()
        extra = max(0, round(self._body_height() - visible))
        self.scroll.setRange(0, extra)
        self.scroll.setPageStep(max(round(visible), 1))
        self.scroll.setSingleStep(LANE_HEIGHT // 2)
        width = self.scroll.sizeHint().width()
        self.scroll.setGeometry(self.width() - width, round(self.body_top()), width,
                                max(round(visible), 0))
        self.scroll.setVisible(extra > 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_scroll()

    def lane_keys(self) -> list[str]:
        values = [v for v in self.document.model.values if v.lane is not None]
        return [v.key for v in sorted(values, key=lambda v: v.lane) if v.key not in self.hidden]

    def hide_lane(self, key: str) -> None:
        self.hidden.add(key)
        self._sync_scroll()
        self.update()

    def show_lanes(self) -> None:
        self.hidden.clear()
        self._sync_scroll()
        self.update()

    def highlight_lane(self, key: str, milliseconds: int = HIGHLIGHT_MS) -> None:
        if key in self.hidden:
            self.hidden.discard(key)
            self._sync_scroll()
        self._highlight(key)
        rect = self.lane_rect(key)
        visible = self.height() - self.body_top()
        if rect.top() < self.body_top() or rect.bottom() > self.height():
            offset = rect.top() - self.body_top() + self.scroll.value()
            self.scroll.setValue(round(offset - max(visible - rect.height(), 0) / 2))
        self._fade.start(milliseconds)

    def _highlight(self, key: str | None) -> None:
        self.highlighted = key
        self.update()

    def _plot_width(self) -> float:
        right = self.scroll.sizeHint().width() if not self.scroll.isHidden() else RIGHT_MARGIN
        return max(self.width() - LABEL_WIDTH - right, 10)

    def _plot_area(self) -> QRectF:
        return QRectF(LABEL_WIDTH, 0, self._plot_width(), self.height())

    def _body_area(self) -> QRectF:
        return QRectF(0, self.body_top(), self.width(), self.height() - self.body_top())

    def _block_span(self, index: int) -> tuple[float, float]:
        block = self.document.experiment.blocks[index]
        length = self.document.experiment.length
        if block.present:
            return 0.0, length
        size = self._block_length(block)
        return block.start, block.start + size if size is not None else length

    def _block_length(self, block) -> float | None:
        if block.length is not None:
            return block.length
        test = next((t for t in self.document.model.tests if t.key == block.experiment), None)
        return test.length if test is not None else None

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

    def changes_height(self) -> float:
        return CHANGES_HEIGHT * max(max(self.block_rows(), default=0) + 1, 1)

    def _changes_top(self) -> float:
        return self.body_top() - self.scroll.value()

    def _lanes_top(self) -> float:
        return self._changes_top() + self.changes_height()

    def _lane_height(self) -> float:
        count = max(len(self.lane_keys()), 1)
        room = self.height() - self.body_top() - self.changes_height()
        return max(LANE_HEIGHT, room / count)

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
            size = self._block_length(block) if size is None else size
            right = start + size if size is not None else length
        x0 = self.x_of(left)
        x1 = max(self.x_of(right), x0 + MIN_BLOCK_WIDTH)
        top = self._changes_top() + self.block_rows()[index] * CHANGES_HEIGHT
        return QRectF(x0, top + 4, x1 - x0, CHANGES_HEIGHT - 8)

    def _block_at(self, pos: QPointF) -> int | None:
        if pos.x() < LABEL_WIDTH or pos.y() < self.body_top():
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

    def _shown_runs(self) -> list[tuple[str, object]]:
        doc = self.document
        runs = [("run", doc.run)]
        if self.compare_on:
            runs.append(("normal", doc.normal))
        if doc.snapshot is not None:
            runs.append(("snapshot", doc.snapshot))
        return [(name, run) for name, run in runs if run is not None]

    def lane_lines(self, key: str) -> dict[str, np.ndarray]:
        start, end = self.span
        grid = np.linspace(start, end, max(int(self._plot_width()), 2))
        return {name: np.interp(grid, run.times, run.value(key))
                for name, run in self._shown_runs()}

    def lane_value(self, key: str) -> tuple[str, str]:
        doc = self.document
        if doc.run is None:
            return "", ""
        mine = doc.run.display(key, doc.playhead)
        normal = doc.normal.display(key, doc.playhead) if doc.normal is not None else None
        return plain(mine, 3, compact=True), tone(mine, normal)

    def lane_marks(self, key: str) -> tuple[str, str]:
        runs = [run for _name, run in self._shown_runs()]
        if not runs:
            return "", ""
        scale = self.document.simulator.values[key].display_scale
        low, high = lane_scale(runs, key)
        return mark_text(low * scale), mark_text(high * scale)

    def name_layout(self, key: str) -> tuple[QRectF, QRectF, QRectF]:
        rect = self.lane_rect(key)
        column = QRectF(PAD, rect.top() + 6, LABEL_WIDTH - PAD - 8, rect.height() - 12)
        text, _tone = self.lane_value(key)
        width = QFontMetricsF(font("label")).horizontalAdvance(text) if text else 0.0
        bottom = column.bottom() - NAME_ROW
        name = QRectF(column.left(), column.top(), column.width(), NAME_ROW)
        value = QRectF(column.right() - width, bottom, width, NAME_ROW)
        unit = QRectF(column.left(), bottom,
                      max(value.left() - VALUE_GAP - column.left(), 0.0), NAME_ROW)
        return name, unit, value

    def _background(self) -> QPixmap:
        doc = self.document
        key = (self.size().toTuple(), self.span, self.compare_on, frozenset(self.hidden),
               self.changes_height(), self.scroll.value(), self.scroll.isHidden(),
               self.show_overview, self.highlighted, id(doc.run), id(doc.normal),
               id(doc.snapshot))
        if self._cache is None or key != self._cache_key:
            ratio = self.devicePixelRatioF()
            pixmap = QPixmap(self.size() * ratio)
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(BACKGROUND)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipRect(self._body_area())
            self._paint_changes_row(painter)
            for n, lane in enumerate(self.lane_keys()):
                self._paint_lane(painter, lane, QColor(LANE_COLORS[n % len(LANE_COLORS)]))
            painter.setClipping(False)
            self._paint_header(painter)
            painter.end()
            self._cache, self._cache_key = pixmap, key
        return self._cache

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = self._body_area()
        painter.setClipRect(body)
        self._paint_names(painter)
        painter.setClipRect(self._plot_area().intersected(body))
        self._paint_guides(painter)
        self._paint_blocks(painter)
        self._paint_hover(painter)
        painter.setClipRect(self._plot_area())
        x = self.x_of(self.document.playhead)
        painter.setPen(QPen(PLAYHEAD, 2))
        painter.drawLine(QPointF(x, self.ruler_rect().top()), QPointF(x, self.height()))
        painter.setClipping(False)
        self._paint_hover_time(painter)
        self._paint_badge(painter)
        if self.show_overview:
            self._paint_overview(painter)
        painter.end()

    def _paint_overview(self, painter: QPainter) -> None:
        bar = self.overview_rect()
        painter.setFont(font("secondary"))
        painter.setPen(MUTED)
        painter.drawText(QRectF(PAD, bar.top(), LABEL_WIDTH - PAD, bar.height()),
                         Qt.AlignmentFlag.AlignVCenter, "Whole run")
        track = QRectF(LABEL_WIDTH, bar.top() + BAR_INSET, self._plot_width(),
                       bar.height() - 2 * BAR_INSET)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BAR)
        painter.drawRoundedRect(track, RADIUS["small"], RADIUS["small"])
        painter.setPen(QPen(BLOCK, 2))
        for index in range(len(self.document.experiment.blocks)):
            x = self.overview_x(self._block_span(index)[0])
            painter.drawLine(QPointF(x, track.top() + 2), QPointF(x, track.bottom() - 2))
        x = self.overview_x(self.document.playhead)
        painter.setPen(QPen(PLAYHEAD, 1))
        painter.drawLine(QPointF(x, track.top()), QPointF(x, track.bottom()))
        painter.setPen(QPen(WINDOW, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.overview_window(), RADIUS["small"], RADIUS["small"])

    def _paint_header(self, painter: QPainter) -> None:
        header = QRectF(0, 0, self.width(), self.body_top())
        painter.fillRect(header, BACKGROUND)
        ruler = self.ruler_rect()
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, ruler.bottom()), QPointF(self.width(), ruler.bottom()))
        painter.drawLine(QPointF(LABEL_WIDTH, ruler.top()), QPointF(LABEL_WIDTH, self.height()))
        painter.setFont(font("data"))
        painter.setPen(MUTED)
        for x, rect, text in self.ruler_labels():
            painter.drawLine(QPointF(x, ruler.bottom() - 6), QPointF(x, ruler.bottom()))
            painter.drawText(rect, Qt.AlignmentFlag.AlignBottom, text)

    def _paint_changes_row(self, painter: QPainter) -> None:
        top, changes = self._changes_top(), self.changes_height()
        painter.setFont(font("label"))
        painter.setPen(INK)
        painter.drawText(QRectF(PAD, top, LABEL_WIDTH - PAD, changes),
                         Qt.AlignmentFlag.AlignVCenter, "Changes")
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, top + changes), QPointF(self.width(), top + changes))
        painter.drawLine(QPointF(LABEL_WIDTH, top), QPointF(LABEL_WIDTH, self.height()))

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
            rect = QRectF(x + 4, self.ruler_rect().top(), metrics.horizontalAdvance(text),
                          RULER_HEIGHT - 4)
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
            preview = self._preview_of(index)
            rect = self.block_rect(index, preview)
            label = self.block_label_rect(index, preview)
            fill = QColor(BLOCK)
            fill.setAlpha(40 if block.present else 64)
            painter.setBrush(fill)
            selected = doc.selection == ("block", index)
            painter.setPen(QPen(PLAYHEAD if selected else BLOCK, 2 if selected else 1))
            painter.drawRoundedRect(rect, RADIUS["small"], RADIUS["small"])
            text_rect = label.adjusted(6, 0, -4, 0)
            if label.width() > 40:
                size = SIZE["icon_header"]
                top = rect.center().y() - size / 2
                painter.drawPixmap(QPointF(label.left() + 6, top),
                                   icons.pixmap(self.block_icon(index), "edited", size))
                text_rect = label.adjusted(10 + size, 0, -4, 0)
            painter.setFont(font("secondary"))
            painter.setPen(INK if selected else BLOCK)
            name = painter.fontMetrics().elidedText(doc.name_of(block.experiment),
                                                    Qt.TextElideMode.ElideRight,
                                                    max(int(text_rect.width()), 0))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, name)

    def block_label_rect(self, index: int,
                         preview: tuple[float, float | None] | None = None) -> QRectF:
        rect = self.block_rect(index, preview)
        left = max(rect.left(), LABEL_WIDTH)
        right = min(rect.right(), LABEL_WIDTH + self._plot_width())
        return QRectF(left, rect.top(), max(right - left, 0.0), rect.height())

    def _preview_of(self, index: int):
        press = self._press
        if press and press.get("block") == index and "preview" in press:
            return press["preview"]
        return None

    def guide_xs(self) -> list[float]:
        if not self.show_guides:
            return []
        xs = []
        for index, block in enumerate(self.document.experiment.blocks):
            if block.present:
                continue
            preview = self._preview_of(index)
            x = self.x_of(preview[0] if preview is not None else block.start)
            if LABEL_WIDTH <= x <= LABEL_WIDTH + self._plot_width():
                xs.append(x)
        return xs

    def hover_values(self) -> dict[str, str]:
        run = self.document.run
        if self.hover_t is None or run is None:
            return {}
        return {key: plain(run.display(key, self.hover_t), 3) for key in self.lane_keys()}

    def _hover_at(self, pos: QPointF) -> float | None:
        keys = self.lane_keys()
        if not (self.show_hover and keys) or pos.x() < LABEL_WIDTH:
            return None
        if pos.x() > LABEL_WIDTH + self._plot_width() or pos.y() < self._lanes_top():
            return None
        if pos.y() < self.body_top() or pos.y() > self.lane_rect(keys[-1]).bottom():
            return None
        return self.t_of(pos.x())

    def _set_hover(self, pos: QPointF | None) -> None:
        if pos != self._hover_pos:
            self._hover_pos = pos
            self.update()

    def leaveEvent(self, event) -> None:
        self._set_hover(None)
        super().leaveEvent(event)

    def _paint_hover(self, painter: QPainter) -> None:
        values = self.hover_values()
        if not values:
            return
        x = self.x_of(self.hover_t)
        keys = self.lane_keys()
        painter.setPen(QPen(MUTED, 1))
        painter.drawLine(QPointF(x, self._lanes_top()), QPointF(x, self.lane_rect(keys[-1]).bottom()))
        painter.setFont(font("data"))
        metrics = painter.fontMetrics()
        for key in keys:
            text = values[key]
            lane = self.lane_rect(key)
            width = metrics.horizontalAdvance(text) + 2 * TAG_PAD
            left = x + TAG_PAD if x + TAG_PAD + width <= lane.right() else x - TAG_PAD - width
            tag = QRectF(left, lane.center().y() - metrics.height() / 2, width, metrics.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(BAR)
            painter.drawRoundedRect(tag, RADIUS["small"], RADIUS["small"])
            painter.setPen(MUTED)
            painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_hover_time(self, painter: QPainter) -> None:
        if not self.hover_values():
            return
        ruler, text = self.ruler_rect(), time_text(self.hover_t)
        width = QFontMetricsF(font("data")).horizontalAdvance(text) + 2 * BADGE_PAD
        left = min(max(self.x_of(self.hover_t) - width / 2, LABEL_WIDTH),
                   LABEL_WIDTH + self._plot_width() - width)
        tag = QRectF(left, ruler.top() + BADGE_INSET, width, ruler.height() - 2 * BADGE_INSET)
        if tag.intersects(self.badge_rect()):
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BAR)
        painter.drawRoundedRect(tag, RADIUS["small"], RADIUS["small"])
        painter.setFont(font("data"))
        painter.setPen(MUTED)
        painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, text)

    def badge_rect(self) -> QRectF:
        ruler = self.ruler_rect()
        text = time_text(self.document.playhead)
        width = QFontMetricsF(font("data")).horizontalAdvance(text) + 2 * BADGE_PAD
        left = self.x_of(self.document.playhead) - width / 2
        left = min(max(left, LABEL_WIDTH), LABEL_WIDTH + self._plot_width() - width)
        return QRectF(left, ruler.top() + BADGE_INSET, width, ruler.height() - 2 * BADGE_INSET)

    def _paint_guides(self, painter: QPainter) -> None:
        keys = self.lane_keys()
        if not keys:
            return
        top, bottom = self._lanes_top(), self.lane_rect(keys[-1]).bottom()
        ink = QColor(BLOCK)
        ink.setAlpha(GUIDE_ALPHA)
        pen = QPen(ink, 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for x in self.guide_xs():
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))

    def _paint_badge(self, painter: QPainter) -> None:
        badge = self.badge_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(PLAYHEAD)
        painter.drawRoundedRect(badge, RADIUS["small"], RADIUS["small"])
        painter.setFont(font("data"))
        painter.setPen(BACKGROUND)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, time_text(self.document.playhead))

    def _paint_names(self, painter: QPainter) -> None:
        for key in self.lane_keys():
            name_rect, unit_rect, value_rect = self.name_layout(key)
            name, unit = self.lane_heading(key)
            text, shade = self.lane_value(key)
            for rect, words, role, ink in ((name_rect, name, "label", INK),
                                           (unit_rect, unit, "secondary", MUTED)):
                painter.setFont(font(role))
                painter.setPen(ink)
                painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics()
                                 .elidedText(words, Qt.TextElideMode.ElideRight, int(rect.width())))
            painter.setFont(font("label"))
            painter.setPen(color(shade) if shade else INK)
            painter.drawText(value_rect, Qt.AlignmentFlag.AlignVCenter
                             | Qt.AlignmentFlag.AlignRight, text)

    def _paint_lane(self, painter: QPainter, key: str, color: QColor) -> None:
        rect = self.lane_rect(key)
        if key == self.highlighted:
            painter.fillRect(QRectF(0, rect.top(), self.width(), rect.height()), BAR)
        painter.setPen(LINE)
        painter.drawLine(QPointF(0, rect.bottom()), QPointF(self.width(), rect.bottom()))
        lines = self.lane_lines(key)
        if not lines:
            return
        low, high = lane_scale([run for _name, run in self._shown_runs()], key)
        bottom_mark, top_mark = self.lane_marks(key)
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
        painter.setFont(font("data"))
        metrics = painter.fontMetrics()
        backing = QColor(BACKGROUND)
        backing.setAlpha(MARK_BACKING)
        for text, top in ((top_mark, rect.top() + 2), (bottom_mark,
                                                       rect.bottom() - 2 - metrics.height())):
            box = QRectF(rect.left(), top, metrics.horizontalAdvance(text) + 2 * MARK_INSET,
                         metrics.height())
            painter.fillRect(box, backing)
            painter.setPen(MUTED)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._set_hover(None)
        self.setFocus()
        if pos.y() < self.ruler_rect().top():
            self._press_overview(pos)
            return
        if self.ruler_rect().contains(pos) or self._on_playhead(pos):
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
        return pos.x() >= LABEL_WIDTH and pos.y() >= self.ruler_rect().top() and abs(pos.x() - self.x_of(self.document.playhead)) <= GRAB

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
            self._set_hover(QPointF(event.position()))
            return super().mouseMoveEvent(event)
        x = event.position().x()
        if press["kind"].startswith("window"):
            self._drag_overview(press, x)
            return
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
        window = self.overview_window()
        if pos.y() < self.ruler_rect().top():
            edge = min(abs(pos.x() - window.left()), abs(pos.x() - window.right())) <= GRAB
            inside = window.left() <= pos.x() <= window.right()
            shape = (Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.OpenHandCursor
                     if inside else Qt.CursorShape.PointingHandCursor)
        elif self._on_playhead(pos) or self.ruler_rect().contains(pos):
            shape = Qt.CursorShape.SizeHorCursor
        elif index is not None and not self.document.experiment.blocks[index].present:
            block = self.document.experiment.blocks[index]
            edge = block.length is not None and pos.x() >= self.block_rect(index).right() - EDGE
            shape = Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.OpenHandCursor
        else:
            shape = Qt.CursorShape.ArrowCursor
        self.setCursor(shape)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.position().y() < self.body_top():
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
        if event.position().x() < LABEL_WIDTH and not sideways and steps:
            self.scroll.setValue(self.scroll.value() - round(steps * LANE_HEIGHT))
            event.accept()
            return
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
        doc = self.document
        width = self.span[1] - self.span[0]
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = width / FINE_STEPS if shift else width / self._plot_width()
        moves = {Qt.Key.Key_Right: doc.playhead + step, Qt.Key.Key_Left: doc.playhead - step,
                 Qt.Key.Key_Home: 0.0, Qt.Key.Key_End: doc.experiment.length}
        if event.key() in moves:
            doc.set_playhead(moves[event.key()])
            self._follow(doc.playhead)
            return
        selection = self.document.selection
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and selection and (
                selection[0] == "block"):
            self.document.delete_block(selection[1])
            return
        super().keyPressEvent(event)

    def _follow(self, t: float) -> None:
        start, end = self.span
        if t < start:
            self._set_span(t, t + end - start)
        elif t > end:
            self._set_span(t - (end - start), t)

    def _set_guides(self, on: bool) -> None:
        self.show_guides = bool(on)
        self.update()

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
            guides = QAction("Show change guides", menu, checkable=True, checked=self.show_guides)
            guides.toggled.connect(self._set_guides)
            menu.addAction(guides)
        menu.exec(event.globalPos())
