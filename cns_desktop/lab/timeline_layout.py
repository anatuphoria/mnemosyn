from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFontMetricsF

from cns_desktop.design.fonts import font

from .experiments_panel import icon_for
from .labels import plain
from .lane_values import lane_scale, mark_text, tone
from .timeline_metrics import (BADGE_INSET, BADGE_PAD, BAR_GAP, BAR_INSET, BLOCK_ROW, DOSE_ROW,
                               GRAB, MARKER,
                               LABEL_WIDTH, LANE_HEIGHT,
                               MIN_BLOCK_WIDTH, NAME_ROW,
                               OVERVIEW_HEIGHT, PAD, RIGHT_MARGIN,
                               RULER_HEIGHT, VALUE_GAP)


class TimelineLayout:
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

    def overview_rect(self) -> QRectF:
        return QRectF(0, 0, self.width(), OVERVIEW_HEIGHT if self.show_overview else 0)

    def ruler_rect(self) -> QRectF:
        return QRectF(0, self.overview_rect().bottom(), self.width(), RULER_HEIGHT)

    def body_top(self) -> float:
        return self.ruler_rect().bottom()

    def _body_height(self) -> float:
        return self.changes_height() + len(self.lane_keys()) * LANE_HEIGHT

    def wanted_height(self) -> int:
        return math.ceil(self.body_top() + self._body_height())

    def lane_keys(self) -> list[str]:
        values = [v for v in self.document.model.values if v.lane is not None]
        return [v.key for v in sorted(values, key=lambda v: v.lane) if v.key not in self.hidden]

    def _plot_width(self) -> float:
        right = self.scroll.sizeHint().width() if not self.scroll.isHidden() else RIGHT_MARGIN
        return max(self.width() - LABEL_WIDTH - right, 10)

    def _plot_area(self) -> QRectF:
        return QRectF(LABEL_WIDTH, 0, self._plot_width(), self.height())

    def _body_area(self) -> QRectF:
        return QRectF(0, self.body_top(), self.width(), self.height() - self.body_top())

    def block_kind(self, index: int) -> str:
        block = self.document.experiment.blocks[index]
        if block.present:
            return "present"
        model = self.document.model
        if any(t.key == block.experiment for t in model.tests):
            return "test"
        if block.length is not None:
            return "lasting"
        experiment = next((e for e in model.experiments if e.key == block.experiment), None)
        edits = experiment.edits if experiment is not None else ()
        if edits and all(e.op == "dose" and not e.daily for e in edits):
            return "dose"
        return "to_end"

    def has_doses(self) -> bool:
        return any(self.block_kind(i) == "dose"
                   for i in range(len(self.document.experiment.blocks)))

    def _block_span(self, index: int) -> tuple[float, float]:
        block = self.document.experiment.blocks[index]
        length = self.document.experiment.length
        if block.present:
            return 0.0, length
        if self.block_kind(index) == "dose":
            return block.start, block.start
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
            if self.block_kind(index) == "dose":
                continue
            start, end = self._block_span(index)
            row = next((r for r, last in enumerate(ends) if last <= start), len(ends))
            if row == len(ends):
                ends.append(end)
            else:
                ends[row] = end
            rows[index] = row
        return rows

    def _dose_height(self) -> float:
        return DOSE_ROW if self.has_doses() else 0.0

    def _bar_rows(self) -> int:
        rows = self.block_rows()
        bars = [rows[i] for i in range(len(rows)) if self.block_kind(i) != "dose"]
        return max(bars, default=0) + 1

    def changes_height(self) -> float:
        return self._dose_height() + BLOCK_ROW * self._bar_rows()

    def _bars_top(self) -> float:
        return self._changes_top() + self._dose_height()

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
        return self.document.scale.snap(t, self.span[1] - self.span[0])

    def lane_rect(self, key: str) -> QRectF:
        index = self.lane_keys().index(key)
        height = self._lane_height()
        return QRectF(LABEL_WIDTH, self._lanes_top() + index * height, self._plot_width(), height)

    def dose_rect(self, index: int, preview: tuple[float, float | None] | None = None) -> QRectF:
        block = self.document.experiment.blocks[index]
        start = preview[0] if preview is not None else block.start
        half = MARKER / 2
        run = self.document.experiment.length
        x = min(max(self.x_of(start), self.x_of(0.0) + half), self.x_of(run) - half)
        y = self._changes_top() + DOSE_ROW / 2
        return QRectF(x - half, y - half, MARKER, MARKER)

    def block_rect(self, index: int, preview: tuple[float, float | None] | None = None) -> QRectF:
        if self.block_kind(index) == "dose":
            return self.dose_rect(index, preview)
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
        top = self._bars_top() + self.block_rows()[index] * BLOCK_ROW
        return QRectF(x0, top + BAR_GAP, x1 - x0, BLOCK_ROW - 2 * BAR_GAP)

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

    def ruler_labels(self) -> list[tuple[float, QRectF, str]]:
        metrics = QFontMetricsF(font("data"))
        start, end = self.span
        steps = self.document.scale.ruler
        step = next((s for s in steps if (end - start) / s <= 8), steps[-1])
        labels = []
        tick = (start // step) * step
        while tick <= end:
            x = self.x_of(tick)
            text = self.document.scale.text(tick)
            rect = QRectF(x + 4, self.ruler_rect().top(), metrics.horizontalAdvance(text),
                          RULER_HEIGHT - 4)
            if rect.right() > self.width():
                rect.moveRight(x - 4)
            if x >= LABEL_WIDTH and rect.left() >= LABEL_WIDTH:
                labels.append((x, rect, text))
            tick += step
        return labels

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

    def badge_rect(self) -> QRectF:
        ruler = self.ruler_rect()
        text = self.document.scale.text(self.document.playhead)
        width = QFontMetricsF(font("data")).horizontalAdvance(text) + 2 * BADGE_PAD
        left = self.x_of(self.document.playhead) - width / 2
        left = min(max(left, LABEL_WIDTH), LABEL_WIDTH + self._plot_width() - width)
        return QRectF(left, ruler.top() + BADGE_INSET, width, ruler.height() - 2 * BADGE_INSET)
