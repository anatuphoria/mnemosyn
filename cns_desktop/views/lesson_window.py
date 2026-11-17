from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from cns_study.lessons import MAX_NOTE, MAX_STEPS, MAX_TITLE, MODES, Lesson, LessonError, Step, write

from ..design.theme import set_role
from ..design.tokens import GAP

KIND_NAMES = {"view": "View", "route": "Route", "lab": "Lab", "quiz": "Questions",
              "lesion": "Lesion"}
QUIZ_NAMES = {"structures": "structures", "groups": "groups", "tracts": "tracts",
              "routes": "routes", "lab": "the Lab"}
SIZE = (380, 560)
EMPTY = "No steps yet. Arrange the app as you want it, then press Add this view."
NO_NOTE = "No note for this step."
FULL = f"A lesson holds at most {MAX_STEPS} steps."
NO_FLASHCARDS = "Flashcards cannot be part of a lesson. Choose Name it or Find it."


class LessonWindow(QDialog):
    def __init__(self, window, lesson: Lesson, path: Path | None, editing: bool) -> None:
        super().__init__(window)
        self.window_ = window
        self.lesson = lesson
        self.path = path
        self.saved = lesson
        self.editing = editing
        self.index = -1
        self.setModal(False)
        self.resize(*SIZE)
        self.title = QLineEdit(lesson.title, placeholderText="Lesson title", maxLength=MAX_TITLE)
        self.author = QLineEdit(lesson.author, placeholderText="Made by (optional)",
                                maxLength=MAX_TITLE)
        self.steps = QListWidget()
        self.step_title = QLineEdit(placeholderText="Step title", maxLength=MAX_TITLE)
        self.note = QPlainTextEdit(placeholderText="A note for the student (optional)")
        self.shown_note = QLabel()
        self.shown_note.setWordWrap(True)
        self.shown_note.setTextFormat(Qt.TextFormat.PlainText)
        self.shown_note.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.report = QLabel()
        self.report.setWordWrap(True)
        set_role(self.report, "secondary")
        self.add_view = QPushButton("Add this view")
        self.add_view.setProperty("variant", "primary")
        self.add_quiz = QPushButton("Add questions…")
        self.up = QPushButton("Up")
        self.down = QPushButton("Down")
        self.delete = QPushButton("Delete")
        self.back = QPushButton("Back")
        self.forward = QPushButton("Next")
        self.again = QPushButton("Back to the step")
        self.edit_button = QPushButton("Edit")
        self.save_button = QPushButton("Save")
        for button in (self.again, self.edit_button):
            button.setProperty("variant", "ghost")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["large"], GAP["large"], GAP["large"], GAP["large"])
        layout.setSpacing(GAP["small"])
        for widget in (self.title, self.author, self.steps):
            layout.addWidget(widget)
        self._row(layout, self.add_view, self.add_quiz)
        self._row(layout, self.up, self.down, self.delete)
        for widget in (self.step_title, self.note, self.shown_note, self.report):
            layout.addWidget(widget)
        self._row(layout, self.back, self.forward, self.again)
        self._row(layout, self.edit_button, None, self.save_button)
        layout.setStretchFactor(self.steps, 3)
        layout.setStretchFactor(self.note, 2)
        layout.setStretchFactor(self.shown_note, 2)
        self.steps.currentRowChanged.connect(self._picked)
        self.title.textEdited.connect(lambda text: self._set(title=text))
        self.author.textEdited.connect(lambda text: self._set(author=text))
        self.step_title.textEdited.connect(lambda text: self._change_step(title=text))
        self.note.textChanged.connect(self._note_changed)
        self.add_view.clicked.connect(self.add_current)
        self.add_quiz.clicked.connect(self.add_questions)
        self.up.clicked.connect(lambda: self.shift_step(-1))
        self.down.clicked.connect(lambda: self.shift_step(1))
        self.delete.clicked.connect(self.remove)
        self.back.clicked.connect(lambda: self.go(self.index - 1))
        self.forward.clicked.connect(lambda: self.go(self.index + 1))
        self.again.clicked.connect(lambda: self.go(self.index))
        self.edit_button.clicked.connect(lambda: self.set_editing(True))
        self.save_button.clicked.connect(self.save)
        self._fill()
        self.set_editing(editing)

    @staticmethod
    def _row(layout, *widgets) -> None:
        row = QHBoxLayout()
        row.setSpacing(GAP["small"])
        for widget in widgets:
            if widget is None:
                row.addStretch(1)
            else:
                row.addWidget(widget)
        layout.addLayout(row)

    def modified(self) -> bool:
        return self.lesson != self.saved

    def _label(self, n: int, step: Step) -> str:
        return f"{n}. {step.title or KIND_NAMES[step.kind]}  ·  {KIND_NAMES[step.kind]}"

    def _fill(self) -> None:
        with QSignalBlocker(self.steps):
            self.steps.clear()
            for n, step in enumerate(self.lesson.steps, 1):
                self.steps.addItem(self._label(n, step))
            if 0 <= self.index < len(self.lesson.steps):
                self.steps.setCurrentRow(self.index)
        self._sync()

    def _sync(self) -> None:
        step = self.lesson.steps[self.index] if 0 <= self.index < len(self.lesson.steps) else None
        editing, count = self.editing, len(self.lesson.steps)
        name = self.lesson.title or "Lesson"
        self.setWindowTitle(f"{name}{' (changed)' if self.modified() else ''}")
        for widget in (self.title, self.author):
            widget.setReadOnly(not editing)
        self.author.setVisible(editing or bool(self.lesson.author))
        for widget in (self.add_view, self.add_quiz, self.up, self.down, self.delete,
                       self.save_button):
            widget.setVisible(editing)
        self.step_title.setVisible(editing and step is not None)
        self.note.setVisible(editing and step is not None)
        self.shown_note.setVisible(not editing or step is None)
        self.edit_button.setVisible(not editing)
        self.up.setEnabled(step is not None and self.index > 0)
        self.down.setEnabled(step is not None and self.index < count - 1)
        self.delete.setEnabled(step is not None)
        self.back.setEnabled(self.index > 0)
        self.forward.setEnabled(self.index < count - 1)
        self.again.setEnabled(step is not None)
        self.save_button.setEnabled(self.modified() or self.path is None)
        if step is None:
            self.shown_note.setText(EMPTY if editing else "This lesson has no steps.")
            return
        with QSignalBlocker(self.step_title), QSignalBlocker(self.note):
            if self.step_title.text() != step.title:
                self.step_title.setText(step.title)
            if self.note.toPlainText() != step.note:
                self.note.setPlainText(step.note)
        self.shown_note.setText(step.note or NO_NOTE)

    def set_editing(self, editing: bool) -> None:
        self.editing = editing
        self._sync()

    def _set(self, **fields) -> None:
        from dataclasses import replace

        self.lesson = replace(self.lesson, **fields)
        self._sync()

    def _change_step(self, **fields) -> None:
        if not 0 <= self.index < len(self.lesson.steps):
            return
        self.lesson = self.lesson.changed(self.index, **fields)
        item = self.steps.item(self.index)
        if item is not None:
            item.setText(self._label(self.index + 1, self.lesson.steps[self.index]))
        self._sync()

    def _note_changed(self) -> None:
        text = self.note.toPlainText()
        if len(text) > MAX_NOTE:
            with QSignalBlocker(self.note):
                self.note.setPlainText(text[:MAX_NOTE])
            text = text[:MAX_NOTE]
        self._change_step(note=text)

    def _picked(self, row: int) -> None:
        if row != self.index:
            self.go(row)

    def go(self, index: int) -> None:
        if not 0 <= index < len(self.lesson.steps):
            return
        self.index = index
        with QSignalBlocker(self.steps):
            self.steps.setCurrentRow(index)
        problems = self.window_.show_step(self.lesson.steps[index])
        self.report.setText(" ".join(problems))
        self.report.setVisible(bool(problems))
        self._sync()

    def _append(self, step: Step) -> None:
        if len(self.lesson.steps) >= MAX_STEPS:
            self.report.setText(FULL)
            self.report.setVisible(True)
            return
        at = self.index + 1 if self.index >= 0 else len(self.lesson.steps)
        self.lesson = self.lesson.with_step(step, at)
        self.index = at
        self.report.setVisible(False)
        self._fill()
        self.step_title.setFocus()
        self.step_title.selectAll()

    def add_current(self) -> None:
        from ..window_lessons import NOT_HERE

        step = self.window_.capture_step()
        if step is None:
            self.report.setText(NOT_HERE)
            self.report.setVisible(True)
            return
        self._append(step)

    def add_questions(self) -> None:
        setup = self.window_.open_quiz_setup()
        setup.accepted.connect(lambda: self._questions_chosen(setup.choice()))

    def _questions_chosen(self, choice) -> None:
        if choice.mode not in MODES:
            self.report.setText(NO_FLASHCARDS)
            self.report.setVisible(True)
            return
        title = f"Questions on {QUIZ_NAMES[choice.level]}"
        self._append(Step("quiz", title, data={"level": choice.level, "mode": choice.mode,
                                               "scope": choice.scope}))

    def shift_step(self, by: int) -> None:
        moved = self.lesson.moved(self.index, by)
        if moved is not self.lesson:
            self.lesson, self.index = moved, self.index + by
            self._fill()

    def remove(self) -> None:
        if not 0 <= self.index < len(self.lesson.steps):
            return
        self.lesson = self.lesson.without(self.index)
        self.index = min(self.index, len(self.lesson.steps) - 1)
        self._fill()

    def save(self) -> bool:
        path = self.path or self.window_.pick_lesson_save()
        if not path:
            return False
        try:
            self.path = write(Path(path), self.lesson)
        except (OSError, LessonError) as exc:
            self.window_.inform("Cannot save the lesson", str(exc))
            return False
        self.saved = self.lesson
        self._sync()
        return True

    def _may_close(self) -> bool:
        if not self.modified():
            return True
        buttons = (QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                   | QMessageBox.StandardButton.Cancel)
        answer = self.window_.ask("Unsaved lesson", "Save the changes to this lesson first?",
                                  buttons)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        if answer != QMessageBox.StandardButton.Discard:
            return False
        self.saved = self.lesson
        return True

    def closeEvent(self, event) -> None:
        if self._may_close():
            super().closeEvent(event)
        else:
            event.ignore()

    def reject(self) -> None:
        if self._may_close():
            super().reject()

    def done(self, result: int) -> None:
        if self.window_.lesson_window is self:
            self.window_.lesson_window = None
        super().done(result)
