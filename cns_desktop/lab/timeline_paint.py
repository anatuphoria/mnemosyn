from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap

from cns_desktop.design import icons
from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import RADIUS, SIZE, color

from .lane_values import lane_scale
from .timeline_metrics import (BACKGROUND, BADGE_INSET, BADGE_PAD, BAR, BAR_INSET, BLOCK,
                               GUIDE_ALPHA, INK, LABEL_WIDTH,
                               LANE_COLORS, LINE, MARK_BACKING,
                               MARK_INSET, MUTED, NORMAL, PAD,
                               PLAYHEAD, TAG_PAD, WINDOW, time_text)


class TimelinePaint:
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
