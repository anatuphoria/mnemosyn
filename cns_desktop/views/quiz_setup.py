from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QVBoxLayout)

from cns_atlas import Atlas
from cns_study.items import items, with_reviewed_entries
from cns_study.progress import ProgressStore
from cns_study.session import QuizChoice, due_and_new, utc_now

from ..design.theme import set_role
from ..design.tokens import GAP

MODES = (("Name it", "name"), ("Find it", "find"), ("Flashcards", "flashcard"))
STYLES = (("Type the name", "name-typed"), ("Choose from 4", "name-choice"))
LEVELS = (("Structures", "structures"), ("Groups", "groups"), ("Tracts", "tracts"))
SESSIONS = (("Due now", False), ("Practice", True))
NO_ITEMS = "Nothing to ask in this scope at this level."
NO_REVIEWED = "No reviewed descriptions yet."
NOTHING_DUE = "Nothing due now and no new items left today. Choose Practice to study anyway."


def _combo(entries) -> QComboBox:
    box = QComboBox()
    for label, data in entries:
        box.addItem(label, data)
    return box


class QuizSetup(QDialog):
    def __init__(self, atlas: Atlas, store: ProgressStore, parent=None,
                 now: Callable[[], datetime] = utc_now) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start quiz")
        self.atlas, self.store, self.now = atlas, store, now
        groups = [("    " * (s.depth - 1) + s.name, s.id) for s in atlas.structures
                  if s.kind == "group" and s.depth > 0]
        self.mode = _combo(MODES)
        self.answer_style = _combo(STYLES)
        self.level = _combo(LEVELS)
        self.scope = _combo([("Whole atlas", None), *groups])
        self.session = _combo(SESSIONS)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                        | QDialogButtonBox.StandardButton.Cancel)
        start = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        start.setText("Start")
        start.setProperty("variant", "primary")
        set_role(self.note, "secondary")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        form = QFormLayout()
        for label, box in (("Mode", self.mode), ("Answer", self.answer_style),
                           ("Level", self.level), ("Scope", self.scope),
                           ("Session", self.session)):
            form.addRow(label, box)
            box.currentIndexChanged.connect(self.refresh)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["wide"], GAP["wide"], GAP["wide"], GAP["large"])
        layout.setSpacing(GAP["large"])
        layout.addLayout(form)
        layout.addWidget(self.note)
        layout.addWidget(self.buttons)
        self.refresh()

    def choice(self) -> QuizChoice:
        mode = self.mode.currentData()
        if mode == "name":
            mode = self.answer_style.currentData()
        return QuizChoice(mode, self.level.currentData(), self.scope.currentData(),
                          self.session.currentData())

    def refresh(self) -> None:
        self.answer_style.setEnabled(self.mode.currentData() == "name")
        choice = self.choice()
        pool = items(self.atlas, choice.level, choice.scope)
        if pool and choice.mode == "flashcard":
            pool = with_reviewed_entries(self.atlas, pool)
            text = NO_REVIEWED
        else:
            text = NO_ITEMS
        ok = bool(pool)
        if pool and choice.practice:
            text = f"{len(pool)} to practise, shuffled. Your schedule will not change."
        elif pool:
            due, new = due_and_new(pool, choice.mode, self.store, self.now())
            ok = bool(due or new)
            text = f"{len(due)} due, {len(new)} new" if ok else NOTHING_DUE
        self.note.setText(text)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)
