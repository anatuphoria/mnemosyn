from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QScrollBar, QWidget

from .timeline_metrics import (BAR_GAP, BLOCK, CHANGES_HEIGHT, HIGHLIGHT_MS, LABEL_WIDTH, LANE_COLORS,
                               LANE_HEIGHT, MIN_SPAN, RULER_HEIGHT,
                               time_text)
from .timeline_input import TimelineInput
from .timeline_layout import TimelineLayout
from .timeline_paint import TimelinePaint

__all__ = ["BLOCK", "CHANGES_HEIGHT", "LABEL_WIDTH", "LANE_COLORS", "LANE_HEIGHT", "MIN_SPAN",
           "RULER_HEIGHT", "Timeline", "time_text"]


class Timeline(TimelineInput, TimelinePaint, TimelineLayout, QWidget):
    edit_requested = Signal(int)
    hint_changed = Signal(str)

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
        self.hint = ""
        self._cache: QPixmap | None = None
        self._cache_key = None
        self._length = document.experiment.length
        self._changes_offset = 0
        self._known = tuple(document.experiment.blocks)
        self.scroll = QScrollBar(Qt.Orientation.Vertical, self)
        self.scroll.hide()
        self.scroll.valueChanged.connect(lambda _v: self.update())
        document.changed.connect(self._on_changed)
        self._fit_height()
        self._sync_scroll()
        document.model_changed.connect(self._on_model)
        document.playhead_moved.connect(lambda _t: self.update())
        document.selection_changed.connect(self._on_selection)

    @property
    def changes_offset(self) -> int:
        return min(self._changes_offset, self.changes_room())

    def scroll_changes(self, pixels: int) -> None:
        offset = min(max(self.changes_offset + pixels, 0), self.changes_room())
        if offset != self._changes_offset:
            self._changes_offset = offset
            self.update()

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
        self._changes_offset = 0
        self._known = tuple(self.document.experiment.blocks)
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
        self._changes_offset = self.changes_offset
        blocks = tuple(self.document.experiment.blocks)
        added = Counter(blocks) - Counter(self._known)
        self._known = blocks
        if sum(added.values()) == 1:
            self.reveal(blocks.index(next(iter(added))))
        self._sync_scroll()
        self.update()

    def _on_selection(self, selection) -> None:
        if selection and selection[0] == "block":
            self.reveal(selection[1])
        self.update()

    def reveal(self, index: int) -> None:
        if index >= len(self.document.experiment.blocks) or self.block_kind(index) == "dose":
            return
        rect, area = self.block_rect(index), self.bars_rect()
        if rect.top() < area.top():
            self.scroll_changes(round(rect.top() - area.top()) - BAR_GAP)
        elif rect.bottom() > area.bottom():
            self.scroll_changes(round(rect.bottom() - area.bottom()) + BAR_GAP)

    def _set_span(self, start: float, end: float) -> None:
        length = self.document.experiment.length
        width = min(max(end - start, self.document.scale.min_span), length)
        start = min(max(start, 0.0), length - width)
        self.span = (start, start + width)
        self.update()

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

    def show_whole_run(self) -> None:
        self.span = (0.0, self.document.experiment.length)
        self.update()

    def zoom(self, factor: float, around: float) -> None:
        length = self.document.experiment.length
        start, end = self.span
        width = min(max((end - start) * factor, self.document.scale.min_span), length)
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
