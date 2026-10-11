from __future__ import annotations

import random
import sqlite3
import time
from html import escape

from fsrs import Rating
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from cns_study.answers import AnswerIndex
from cns_study.choices import choices
from cns_study.items import Item, item_for
from cns_study.session import Session

from ..state import AppState
from .info_panel import entry_html

ENTER = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
CHOICE_KEYS = {Qt.Key.Key_1: 0, Qt.Key.Key_2: 1, Qt.Key.Key_3: 2, Qt.Key.Key_4: 3}
RATING_KEYS = {Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4}
RIGHT = "<span style='color:#5c5'><b>Correct</b></span>"
WRONG = "<span style='color:#e66'><b>Wrong</b></span>"
RATINGS = ("1 Again", "2 Hard", "3 Good", "4 Easy")
WHAT = {"structures": "structure", "groups": "group", "tracts": "tract"}
SAVE_FAILED = {"feedback": "Could not save this answer. Press Enter to try again.",
               "revealed": "Could not save this answer. Please rate it again."}


class AnswerBox(QLineEdit):
    submitted = Signal(str)

    def keyPressEvent(self, event) -> None:
        if event.key() in ENTER:
            event.accept()
            self.submitted.emit(self.text())
            return
        super().keyPressEvent(event)


def _rich_label() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


class QuizPanel(QWidget):
    finished = Signal()
    centre_requested = Signal()
    find_target = Signal(object)
    dim_grey = Signal(bool)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.session: Session | None = None
        self.index: AnswerIndex | None = None
        self.pool: list[Item] = []
        self.rng = random.Random()
        self.mode = ""
        self.phase = "idle"
        self.item: Item | None = None
        self.options: list[Item] = []
        self.correct = False
        self.answer_ms = 0
        self._shown_at = 0.0
        self._selecting = False

        self.counter = QLabel()
        self.prompt = _rich_label()
        self.answer_box = AnswerBox(placeholderText="Type the name, then press Enter")
        self.choice_buttons = [QPushButton() for _ in range(4)]
        self.feedback = _rich_label()
        self.back = QTextBrowser()
        self.reveal_button = QPushButton("Show the description (Space)")
        self.rate_buttons = [QPushButton(label) for label in RATINGS]
        self.next_button = QPushButton("Next")
        self.hint = QLabel()
        self.end_button = QPushButton("End quiz (Esc)")
        layout = QVBoxLayout(self)
        for widget in (self.counter, self.prompt, self.answer_box, *self.choice_buttons,
                       self.feedback, self.back, self.reveal_button):
            layout.addWidget(widget)
        ratings = QHBoxLayout()
        for button in self.rate_buttons:
            ratings.addWidget(button)
        layout.addLayout(ratings)
        layout.addWidget(self.next_button)
        layout.addStretch(1)
        layout.addWidget(self.hint)
        layout.addWidget(self.end_button)
        for index, button in enumerate(self.choice_buttons):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, i=index: self.choose(i))
        for value, button in enumerate(self.rate_buttons, 1):
            button.clicked.connect(lambda _checked=False, v=value: self.rate(v))
        self.reveal_button.clicked.connect(self.reveal)
        self.next_button.clicked.connect(self._advance)
        for button in (*self.rate_buttons, self.reveal_button, self.next_button, self.end_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.end_button.clicked.connect(self.stop)
        self.answer_box.submitted.connect(self.submit_text)
        state.selection_changed.connect(self._on_selection)
        self._layout()

    def start(self, session: Session, mode: str, index: AnswerIndex, pool: list[Item],
              rng: random.Random) -> None:
        self.session, self.mode, self.index, self.pool, self.rng = session, mode, index, pool, rng
        self._ask()

    def _layout(self) -> None:
        asking = self.phase == "asking"
        self.answer_box.setVisible(asking and self.mode == "name-typed")
        for n, button in enumerate(self.choice_buttons):
            button.setVisible(asking and self.mode == "name-choice" and n < len(self.options))
        self.feedback.setVisible(self.phase == "feedback")
        self.back.setVisible(self.phase == "revealed")
        self.reveal_button.setVisible(asking and self.mode == "flashcard")
        for button in self.rate_buttons:
            button.setVisible(self.phase == "revealed")
        self.next_button.setVisible(self.phase in ("feedback", "summary"))
        self.next_button.setText("Close" if self.phase == "summary" else "Next")

    def _advance(self) -> None:
        if self.phase == "summary":
            self.stop()
        else:
            self.go_on()

    def _hold(self, item_id: int, centre: bool = False) -> None:
        QTimer.singleShot(0, lambda: self._restore(item_id, centre))

    def _restore(self, item_id: int, centre: bool) -> None:
        if self.item is None or self.item.id != item_id:
            return
        if self.state.selected != item_id:
            self._select(item_id)
        if centre:
            self.centre_requested.emit()

    def _focus(self) -> None:
        if self.phase == "asking" and self.mode == "name-typed":
            self.answer_box.setFocus()
        else:
            self.setFocus()

    def _select(self, structure_id: int | None) -> None:
        self._selecting = True
        try:
            self.state.select(structure_id)
        finally:
            self._selecting = False

    def _ask(self) -> None:
        item = self.session.next()
        if item is None:
            self._show_summary()
            return
        self.item, self.phase = item, "asking"
        self.counter.setText(f"{self.session.remaining() + 1} left")
        self._present(item)
        self._layout()
        self._focus()
        self._shown_at = time.perf_counter()

    def _present(self, item: Item) -> None:
        self.options = []
        self.dim_grey.emit(item.level == "tracts" and self.mode != "find")
        if item.level == "tracts" and self.mode != "find":
            self.state.set_hidden([i for i in self.state.tract_ids if i not in item.geometry],
                                  True)
        if self.mode == "find":
            self._select(None)
            self.find_target.emit(frozenset(item.geometry))
            self.prompt.setText(f"<b>Find:</b> {escape(item.name)}<br>"
                                "<small>Click it in the 3D view or in the slice.</small>")
            self.hint.setText("Click a structure")
            return
        self._select(item.id)
        self.centre_requested.emit()
        if self.mode == "flashcard":
            self.prompt.setText(f"<b>{escape(item.name)}</b> ({escape(item.acronym)})")
            self.hint.setText("Space shows the description")
            return
        what = WHAT[item.level]
        self.prompt.setText(f"<b>Which {what} is highlighted?</b>")
        if self.mode == "name-choice":
            self.options = choices(item, self.pool, self.rng)
            for n, (button, option) in enumerate(zip(self.choice_buttons, self.options), 1):
                button.setText(f"{n}. {option.name}")
            self.hint.setText("Keys 1 to 4 choose")
        else:
            self.answer_box.clear()
            self.hint.setText("Enter submits")

    def submit_text(self, text: str) -> None:
        if self.phase != "asking" or self.mode != "name-typed":
            return
        verdict = self.index.check(text, self.item)
        note = ""
        if verdict.correct and not verdict.exact:
            note = f"You typed \"{text.strip()}\"."
        self._judge(verdict.correct, note)

    def choose(self, index: int) -> None:
        if self.phase != "asking" or self.mode != "name-choice":
            return
        if 0 <= index < len(self.options):
            self._judge(self.options[index].id == self.item.id, "")

    def _judge(self, correct: bool, note: str) -> None:
        self.answer_ms = round((time.perf_counter() - self._shown_at) * 1000)
        self.correct, self.phase = correct, "feedback"
        item = self.item
        lines = [f"<b>{escape(item.name)}</b> ({escape(item.acronym)})"]
        others = [a for a in item.answers if a not in (item.name, item.acronym)]
        if others:
            lines.append(f"Also: {escape(', '.join(others))}")
        if note:
            lines.append(escape(note))
        self.feedback.setText(f"<p>{RIGHT if correct else WRONG}</p><p>{'<br>'.join(lines)}</p>")
        self.hint.setText("Enter: next   H: hard   E: easy" if correct else "Enter: next")
        self._layout()
        self.setFocus()

    def _save(self, rating: Rating) -> bool:
        try:
            self.session.answer(rating, self.correct, self.answer_ms)
        except sqlite3.Error:
            self.hint.setText(SAVE_FAILED[self.phase])
            return False
        return True

    def _record(self, rating: Rating | None) -> bool:
        if not self.correct:
            rating = Rating.Again
        return self._save(rating or Rating.Good)

    def go_on(self, rating: Rating | None = None) -> None:
        if self.phase == "feedback" and self._record(rating):
            self._ask()

    def reveal(self) -> None:
        if self.phase != "asking" or self.mode != "flashcard":
            return
        self.answer_ms = round((time.perf_counter() - self._shown_at) * 1000)
        self.phase = "revealed"
        self.back.setHtml("".join(entry_html(self.state.atlas.knowledge(self.item.id))))
        self.hint.setText("Rate: 1 again   2 hard   3 good   4 easy")
        self._layout()
        self.setFocus()

    def rate(self, value: int) -> None:
        if self.phase != "revealed" or value not in (1, 2, 3, 4):
            return
        self.correct = value > 1
        if self._save(Rating(value)):
            self._ask()

    def _show_summary(self) -> None:
        summary = self.session.summary()
        self.item, self.phase, self.options = None, "summary", []
        self._select(None)
        missed = ", ".join(item.name for item in summary.most_missed) or "none"
        lines = [f"{summary.answered} answered, {summary.percent}% correct",
                 f"Most missed: {escape(missed)}"]
        lines.append("Practice: your schedule did not change." if self.session.practice
                     else f"Due by the end of tomorrow: {summary.due_tomorrow}")
        self.prompt.setText(f"<b>Done</b><br>{'<br>'.join(lines)}")
        self.counter.clear()
        self.hint.setText("Enter closes the quiz")
        self._layout()
        self.setFocus()

    def stop(self) -> None:
        if self.phase == "idle":
            return
        if self.phase == "feedback" and not self._record(None):
            return
        self.phase, self.item, self.session, self.options = "idle", None, None, []
        self.find_target.emit(frozenset())
        self.dim_grey.emit(False)
        self._layout()
        self.finished.emit()

    def _on_selection(self, structure_id: int | None) -> None:
        if self._selecting or self.item is None:
            return
        if self.mode != "find" or self.phase != "asking":
            self._hold(self.item.id)
            return
        if structure_id is None:
            return
        clicked = item_for(self.pool, structure_id)
        name = clicked.name if clicked else self.state.atlas.get(structure_id).name
        correct = structure_id in self.item.geometry
        self._hold(self.item.id, centre=True)
        self._judge(correct, "" if correct else f"You clicked: {name}.")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.stop()
        elif self.phase == "feedback" and key in ENTER:
            self.go_on()
        elif self.phase == "feedback" and key == Qt.Key.Key_H and self.correct:
            self.go_on(Rating.Hard)
        elif self.phase == "feedback" and key == Qt.Key.Key_E and self.correct:
            self.go_on(Rating.Easy)
        elif self.phase == "summary" and key in ENTER:
            self.stop()
        elif self.phase == "asking" and self.mode == "name-choice" and key in CHOICE_KEYS:
            self.choose(CHOICE_KEYS[key])
        elif self.phase == "asking" and self.mode == "flashcard" and key == Qt.Key.Key_Space:
            self.reveal()
        elif self.phase == "revealed" and key in RATING_KEYS:
            self.rate(RATING_KEYS[key])
        else:
            super().keyPressEvent(event)
