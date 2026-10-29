from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fsrs import Scheduler
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from cns_atlas import Atlas
from cns_study.items import LEVELS, items
from cns_study.progress import MODES, ProgressStore, mode_stats, weakest
from cns_study.session import utc_now

from ..design.theme import set_role
from ..design.tokens import GAP, SIZE

MODE_LABELS = {"name-typed": "Name it (typed)", "name-choice": "Name it (choice)",
               "find": "Find it", "flashcard": "Flashcards"}
COLUMNS = ("Mode", "Level", "New", "Learning", "Known", "Due today", "Due this week")


class ProgressDialog(QDialog):
    def __init__(self, atlas: Atlas, store: ProgressStore, parent=None,
                 now: Callable[[], datetime] = utc_now) -> None:
        super().__init__(parent)
        self.setWindowTitle("Progress")
        moment = now()
        scheduler = Scheduler()
        pools = {level: items(atlas, level) for level in LEVELS}
        names = {item.id: item.name for pool in pools.values() for item in pool}
        self.table = QTableWidget(len(MODES) * len(LEVELS), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        weak = []
        row = 0
        for mode in MODES:
            cards = store.cards(mode)
            for level in LEVELS:
                ids = [item.id for item in pools[level]]
                stats = mode_stats(cards, ids, moment)
                values = (MODE_LABELS[mode], level.capitalize(), stats.new, stats.learning,
                          stats.known, stats.due_today, stats.due_week)
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(str(value)))
                row += 1
                weak += [(recall, names[i], MODE_LABELS[mode])
                         for i, recall in weakest(cards, ids, scheduler, moment)]
        self.weakest = QListWidget()
        for recall, name, label in sorted(weak)[:10]:
            self.weakest.addItem(f"{name} · {label}: {round(100 * recall)}% likely to recall")
        if not weak:
            self.weakest.addItem("Nothing reviewed yet")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.heading = QLabel("Weakest 10")
        set_role(self.heading, "heading")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["wide"], GAP["wide"], GAP["wide"], GAP["large"])
        layout.setSpacing(GAP["medium"])
        layout.addWidget(self.table)
        layout.addWidget(self.heading)
        layout.addWidget(self.weakest)
        layout.addWidget(buttons)
        self.resize(*SIZE["dialog"])
