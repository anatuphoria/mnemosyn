from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fsrs import Scheduler
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from cns_atlas import Atlas
from cns_study.items import LEVELS, items
from cns_study.progress import MODES, ModeStats, ProgressStore, mode_stats, weakest
from cns_study.session import utc_now

from ..design.theme import set_flag, set_role, set_tone
from ..design.tokens import GAP, SIZE, color
from ..design.widgets import ElidedLabel, SegmentedControl

MODE_LABELS = {"name-typed": "Name it (typed)", "name-choice": "Name it (choice)",
               "find": "Find it", "flashcard": "Flashcards"}
WEAK_COUNT = 10


def _label(text: str, tone: str = "", role: str = "") -> QLabel:
    label = QLabel(text)
    if tone:
        set_tone(label, tone)
    if role:
        set_role(label, role)
    return label


def _panel() -> tuple[QFrame, QVBoxLayout]:
    panel = QFrame()
    panel.setProperty("panel", "true")
    column = QVBoxLayout(panel)
    column.setContentsMargins(0, GAP["tight"], 0, GAP["tight"])
    column.setSpacing(0)
    return panel, column


def recall_tone(recall: float) -> str:
    if recall < 0.6:
        return "danger"
    return "edited" if recall < 0.85 else "success"


class StackBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parts = (0, 0, 0)
        self.setFixedHeight(SIZE["bar"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_parts(self, known: int, learning: int, total: int) -> None:
        self.parts = (known, learning, total)
        new = max(total - known - learning, 0)
        self.setToolTip(f"{known} known, {learning} learning, {new} new")
        self.update()

    def paintEvent(self, _event) -> None:
        known, learning, total = self.parts
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = SIZE["bar"] / 2
        painter.setBrush(color("s3"))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        if total > 0:
            width = self.width()
            left = 0.0
            for count, role in ((known, "success"), (learning, "edited")):
                span = width * count / total
                if count and span < SIZE["bar"]:
                    span = SIZE["bar"]
                if span:
                    painter.setBrush(color(role))
                    painter.drawRoundedRect(QRectF(left, 0, span, SIZE["bar"]), radius, radius)
                left += span
        painter.end()


class RecallBar(QWidget):
    def __init__(self, recall: float, parent=None) -> None:
        super().__init__(parent)
        self.recall = recall
        self.setFixedSize(SIZE["recall_bar"], SIZE["bar"])

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = SIZE["bar"] / 2
        painter.setBrush(color("s3"))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        span = max(self.width() * min(max(self.recall, 0.0), 1.0), SIZE["bar"])
        painter.setBrush(color(recall_tone(self.recall)))
        painter.drawRoundedRect(QRectF(0, 0, span, SIZE["bar"]), radius, radius)
        painter.end()


def _count_cell(caption: str) -> tuple[QWidget, QLabel]:
    cell = QWidget()
    cell.setFixedWidth(SIZE["count_column"])
    column = QVBoxLayout(cell)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    number = _label("0", role="label")
    number.setAlignment(Qt.AlignmentFlag.AlignRight)
    word = _label(caption, "text3", "secondary")
    word.setAlignment(Qt.AlignmentFlag.AlignRight)
    column.addWidget(number)
    column.addWidget(word)
    return cell, number


class LevelRow(QFrame):
    def __init__(self, level: str, first: bool, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelrow", "true")
        set_flag(self, "first", first)
        self.setFixedHeight(SIZE["stat_row"])
        self.name = _label(level.capitalize())
        self.name.setFixedWidth(SIZE["label_column"])
        self.bar = StackBar()
        learning_cell, self.learning = _count_cell("learning")
        due_cell, self.due = _count_cell("due")
        row = QHBoxLayout(self)
        row.setContentsMargins(GAP["large"], 0, GAP["large"], 0)
        row.setSpacing(GAP["large"])
        row.addWidget(self.name)
        row.addWidget(self.bar, 1)
        row.addWidget(learning_cell)
        row.addWidget(due_cell)

    def show_stats(self, stats: ModeStats) -> None:
        total = stats.new + stats.learning + stats.known
        self.bar.set_parts(stats.known, stats.learning, total)
        self.learning.setText(str(stats.learning))
        self.due.setText(str(stats.due_today))
        set_tone(self.due, "accent_text" if stats.due_today else "text")


class WeakRow(QFrame):
    def __init__(self, name: str, level: str, recall: float, first: bool, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelrow", "true")
        set_flag(self, "first", first)
        self.setFixedHeight(SIZE["row"])
        self.recall = recall
        self.name = ElidedLabel(name)
        self.level = _label(level.capitalize(), "text3", "secondary")
        self.level.setFixedWidth(SIZE["label_column"])
        self.bar = RecallBar(recall)
        self.percent = _label(f"{round(100 * recall)}%", "text2")
        self.percent.setFixedWidth(SIZE["percent_column"])
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QHBoxLayout(self)
        row.setContentsMargins(GAP["large"], 0, GAP["large"], 0)
        row.setSpacing(GAP["medium"])
        row.addWidget(self.name, 1)
        row.addWidget(self.level)
        row.addWidget(self.bar)
        row.addWidget(self.percent)


def _tile(caption: str) -> tuple[QFrame, QLabel, QHBoxLayout]:
    tile, column = _panel()
    column.setContentsMargins(GAP["large"], GAP["medium"], GAP["large"], GAP["medium"])
    column.setSpacing(0)
    number = _label("0", role="title")
    line = QHBoxLayout()
    line.setSpacing(GAP["small"])
    line.addWidget(number)
    line.addStretch(1)
    column.addLayout(line)
    column.addWidget(_label(caption, "text3", "secondary"))
    return tile, number, line


def default_mode(stats: dict[tuple[str, str], ModeStats]) -> str:
    due = {mode: sum(stats[mode, level].due_today for level in LEVELS) for mode in MODES}
    return max(MODES, key=lambda mode: due[mode])


class ProgressDialog(QDialog):
    def __init__(self, atlas: Atlas, store: ProgressStore, parent=None,
                 now: Callable[[], datetime] = utc_now) -> None:
        super().__init__(parent)
        self.setWindowTitle("Progress")
        moment = now()
        scheduler = Scheduler()
        pools = {level: items(atlas, level) for level in LEVELS}
        names = {item.id: item.name for pool in pools.values() for item in pool}
        self.stats: dict[tuple[str, str], ModeStats] = {}
        self.weak: dict[str, list[tuple[float, str, str]]] = {}
        for mode in MODES:
            cards = store.cards(mode)
            found = []
            for level in LEVELS:
                ids = [item.id for item in pools[level]]
                self.stats[mode, level] = mode_stats(cards, ids, moment)
                found += [(recall, names[i], level)
                          for i, recall in weakest(cards, ids, scheduler, moment)]
            self.weak[mode] = sorted(found)[:WEAK_COUNT]

        tiles = QHBoxLayout()
        tiles.setSpacing(GAP["medium"])
        self.tiles: dict[str, QLabel] = {}
        due_today = sum(s.due_today for s in self.stats.values())
        due_week = sum(s.due_week for s in self.stats.values())
        known = sum(s.known for s in self.stats.values())
        total = sum(s.new + s.learning + s.known for s in self.stats.values())
        for key, caption, value in (("due_today", "Due today", due_today),
                                    ("due_week", "Due this week", due_week),
                                    ("known", "Known", known)):
            tile, number, line = _tile(caption)
            number.setText(f"{value:,}")
            self.tiles[key] = number
            if key == "due_today" and value:
                set_tone(number, "accent_text")
            if key == "known":
                self.known_of = _label(f"of {total:,}", "text3")
                line.insertWidget(1, self.known_of, 0, Qt.AlignmentFlag.AlignBottom)
            tiles.addWidget(tile, 1)

        self.modes = SegmentedControl([(mode, MODE_LABELS[mode]) for mode in MODES])
        level_panel, level_column = _panel()
        self.levels = {level: LevelRow(level, n == 0) for n, level in enumerate(LEVELS)}
        for row in self.levels.values():
            level_column.addWidget(row)

        self.weak_heading = _label("", role="heading")
        weak_body = QWidget()
        self._weak_column = QVBoxLayout(weak_body)
        self._weak_column.setContentsMargins(0, GAP["tight"], 0, GAP["tight"])
        self._weak_column.setSpacing(0)
        self.empty = _label("Nothing reviewed in this mode yet", "text3")
        self.empty.setContentsMargins(GAP["large"], GAP["small"], GAP["large"], GAP["small"])
        self._weak_column.addWidget(self.empty)
        self._weak_column.addStretch(1)
        self.weak_rows: list[WeakRow] = []
        scroll = QScrollArea()
        scroll.setProperty("panel", "true")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(weak_body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["wide"], GAP["large"] + GAP["tight"], GAP["wide"],
                                  GAP["large"])
        layout.setSpacing(GAP["medium"])
        layout.addLayout(tiles)
        layout.addSpacing(GAP["tight"])
        layout.addWidget(self.modes, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(level_panel)
        layout.addSpacing(GAP["tight"])
        layout.addWidget(self.weak_heading)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        self.resize(*SIZE["dialog_progress"])

        start = default_mode(self.stats)
        self.modes.set_current(start)
        self._show_mode(start)
        self.modes.changed.connect(self._show_mode)

    def _show_mode(self, mode: str) -> None:
        for level, row in self.levels.items():
            row.show_stats(self.stats[mode, level])
        self.weak_heading.setText(f"Weakest in {MODE_LABELS[mode]}")
        for row in self.weak_rows:
            self._weak_column.removeWidget(row)
            row.deleteLater()
        self.weak_rows = [WeakRow(name, level, recall, n == 0)
                          for n, (recall, name, level) in enumerate(self.weak[mode])]
        for n, row in enumerate(self.weak_rows):
            self._weak_column.insertWidget(n, row)
        self.empty.setVisible(not self.weak_rows)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.close_button.setFocus()
