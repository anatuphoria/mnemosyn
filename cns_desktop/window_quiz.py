from __future__ import annotations

import random
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox

from cns_study.answers import AnswerIndex
from cns_study.items import (group_items, structure_items, tract_items,
                             with_reviewed_entries)
from cns_study.progress import ProgressStore
from cns_study.questions import pool_for
from cns_study.session import QuizChoice, Session, utc_now

from .design.tokens import SIZE
from .views.progress_dialog import ProgressDialog
from .views.quiz_setup import QuizSetup

RESET_QUESTION = ("This starts your quiz progress again from nothing. Your progress so far is "
                  "kept as a file in the data folder, so you can put it back by hand.")
RESET_DONE = "Your progress was reset. The old progress is kept as:\n{path}"
BACKUP_DONE = "A copy of your progress was saved to:\n{path}"
BACKUP_FAILED = "The copy could not be saved to:\n{path}"
QUIZ_LOCKED = ("Hide", "Isolate", "Show all", "Start quiz", "Tracts")
QUIZ_ROOM_MM = 80.0
RECOVERED = {
    "damaged": ("Progress file damaged", "Your progress file could not be read. It was kept as "
                "{path} and a new one was started."),
    "newer": ("Progress file from a newer version", "Your progress file was written by a newer "
              "version of Mnemosyn. It was kept as {path} and a new one was started."),
}


class QuizMode:
    def progress_store(self) -> ProgressStore:
        if self._store is None:
            name = str(self.state.atlas.metadata.get("name", "atlas"))
            self._store = ProgressStore(self.progress_path, name)
            if self._store.recovered_from is not None:
                title, text = RECOVERED[self._store.recovery_reason]
                self.recovery_box = QMessageBox(
                    QMessageBox.Icon.Warning, title, text.format(path=self._store.recovered_from),
                    QMessageBox.StandardButton.Ok, self)
                self.recovery_box.open()
        return self._store

    def answer_index(self) -> AnswerIndex:
        if self._answers is None:
            atlas = self.state.atlas
            pool = structure_items(atlas) + group_items(atlas) + tract_items(atlas)
            self._answers = AnswerIndex(pool)
        return self._answers

    def open_quiz_setup(self) -> QuizSetup:
        self._out_of_lab()
        self.slices.label_centres()
        dialog = QuizSetup(self.state.atlas, self.progress_store(), self)
        dialog.accepted.connect(lambda: self.start_quiz(dialog.choice()))
        dialog.open()
        return dialog

    def backup_progress(self, to: Path) -> bool:
        try:
            self.progress_store().backup(Path(to))
        except (OSError, sqlite3.Error):
            return False
        return True

    def ask_backup(self) -> None:
        name = f"mnemosyn-progress-{datetime.now():%Y-%m-%d}.sqlite"
        chosen, _kind = QFileDialog.getSaveFileName(
            self, "Back up progress", str(Path.home() / name), "Progress file (*.sqlite)")
        if not chosen:
            return
        text = BACKUP_DONE if self.backup_progress(Path(chosen)) else BACKUP_FAILED
        QMessageBox.information(self, "Back up progress", text.format(path=chosen))

    def reset_progress(self) -> Path | None:
        if self.quiz_active:
            return None
        return self.progress_store().reset()

    def ask_reset(self) -> None:
        if self.quiz_active:
            return
        answer = QMessageBox.question(
            self, "Reset progress", RESET_QUESTION,
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Reset:
            return
        kept = self.reset_progress()
        if kept is not None:
            QMessageBox.information(self, "Reset progress", RESET_DONE.format(path=kept))

    def show_progress(self) -> ProgressDialog:
        dialog = ProgressDialog(self.state.atlas, self.progress_store(), self)
        dialog.open()
        return dialog

    def start_quiz(self, choice: QuizChoice, rng: random.Random | None = None,
                   now: Callable[[], datetime] = utc_now) -> None:
        atlas = self.state.atlas
        pool = pool_for(atlas, choice.level)
        chosen = pool_for(atlas, choice.level, choice.scope)
        if choice.mode == "flashcard":
            chosen = with_reviewed_entries(atlas, chosen)
        rng = rng or random.Random()
        session = Session(chosen, choice.mode, self.progress_store(), choice.practice, now=now,
                          rng=rng)
        if self.pathway_active:
            self.pathways.leave()
        self._out_of_lab()
        self.enter_quiz()
        shown = choice.level == "tracts" and choice.mode == "find"
        self.state.set_hidden(self.state.tract_ids, not shown)
        self.quiz.start(session, choice.mode, self.answer_index(), pool, rng)

    def open_quiz_in_lab(self, item) -> None:
        if self.lab is not None and item.source:
            self.lab.show_check(*item.source)

    def _quiz_locked(self) -> list[QAction]:
        docks = (self.tree_dock, self.pathway_dock, self.info_dock, self.chart_dock,
                 self.step_group)
        return [*(self.shortcuts[name] for name in QUIZ_LOCKED), self.reset_action,
                *(dock.toggleViewAction() for dock in docks)]

    def enter_quiz(self) -> None:
        if self.quiz_active:
            return
        state = self.state
        before = self.size()
        self._saved = (self.saveState(), *self._snapshot(),
                       [(w, w.focusPolicy()) for w in (self.view, self.slices.view)],
                       self.workspaces.joins(), self.view.camera_position.to_list())
        self.workspaces.release_joins()
        self.quiz_active = True
        self.workspaces.set_locked(True)
        if self.lab is not None:
            self.lab.set_files_enabled(False)
        for action in self._quiz_locked():
            action.setEnabled(False)
        state.set_hidden([i for i in state.geometry_ids if not state.is_tract(i)], False)
        for widget, _ in self._saved[6]:
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree_dock.hide()
        self.pathway_dock.hide()
        self.info_dock.hide()
        self.chart_dock.hide()
        self.step_group.hide()
        self.quiz_dock.show()
        self._arrange_quiz(before.width())
        self.resize(before)
        QTimer.singleShot(0, lambda: self.quiz_active and self.resize(before))
        QTimer.singleShot(0, self.fit_quiz_column)
        self.statusBar().clearMessage()
        self._update_status()

    def _arrange_quiz(self, width: int | None = None) -> None:
        side = SIZE["panel_left"]
        width = self.width() if width is None else width
        if width < SIZE["narrow"]:
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.slice_dock)
            self.splitDockWidget(self.quiz_dock, self.slice_dock, Qt.Orientation.Vertical)
            self.resizeDocks([self.quiz_dock], [side], Qt.Orientation.Horizontal)
            self.fit_quiz_column()
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.slice_dock)
            room = width - side - SIZE["central_min"]
            self.resizeDocks([self.quiz_dock, self.slice_dock], [side, max(room // 2, side)],
                             Qt.Orientation.Horizontal)
        self.slice_dock.show()

    def fit_quiz_column(self) -> None:
        if (not self.quiz_active or self.dockWidgetArea(self.slice_dock)
                != Qt.DockWidgetArea.LeftDockWidgetArea):
            return
        chrome = self.quiz_dock.height() - self.quiz.parentWidget().height()
        needed = self.quiz.layout().totalHeightForWidth(self.quiz.width())
        want = max(needed, self.quiz.sizeHint().height()) + max(chrome, 0)
        shared = self.quiz_dock.height() + self.slice_dock.height()
        self.resizeDocks([self.quiz_dock, self.slice_dock], [want, max(shared - want, 1)],
                         Qt.Orientation.Vertical)

    def _frame_quiz_target(self, ids) -> None:
        if ids:
            self.view.frame_around(ids, QUIZ_ROOM_MM)
        elif self.quiz_active:
            self._put_camera(self._saved[-1])

    def _put_camera(self, camera) -> None:
        self.view.camera_position = camera
        self.view.renderer.ResetCameraClippingRange()

    def leave_quiz(self) -> None:
        if not self.quiz_active:
            return
        layout, hidden, selected, axis, mm, volume, focus, joins, camera = self._saved
        size = self.size()
        self.quiz_active = False
        self.workspaces.set_locked(False)
        if self.lab is not None:
            self.lab.set_files_enabled(True)
        for action in self._quiz_locked():
            action.setEnabled(True)
        for widget, policy in focus:
            widget.setFocusPolicy(policy)
        self.workspaces.release_joins()
        self.restoreState(layout)
        self.workspaces.apply_joins(joins)
        self._restore(hidden, selected, axis, mm, volume)
        self._put_camera(camera)
        self.resize(size)
        QTimer.singleShot(0, lambda: self.quiz_active or self.resize(size))
        self._sync_chart()
        self._update_status()

    def _snapshot(self) -> tuple:
        state = self.state
        hidden = [i for i in state.geometry_ids if state.is_hidden(i)]
        return hidden, state.selected, state.slice_axis, state.slice_mm, state.slice_volume

    def _restore(self, hidden, selected, axis, mm, volume="") -> None:
        self.state.select(selected)
        kept = set(hidden)
        self.state.set_hidden([i for i in self.state.geometry_ids if i not in kept], False)
        self.state.set_hidden(hidden, True)
        if volume:
            self.state.set_slice_volume(volume)
        self.state.set_slice(axis, mm)
