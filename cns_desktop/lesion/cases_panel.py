from __future__ import annotations

import random
from datetime import UTC, datetime
from html import escape

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from cns_atlas.lesions import compare, new_case, signs_of
from cns_desktop.design.theme import set_role
from cns_desktop.design.tokens import GAP, SIZE

NO_CASES = "No route in this build has signs to build a case from."
PLACE_FIRST = "Place a lesion on the Place tab where you think the damage is, then press Check."
INTRO = "Press New case: you get a patient's signs, place the lesion you think explains them, then check."


class CasesPanel(QWidget):
    def __init__(self, document, workspace, parent=None) -> None:
        super().__init__(parent)
        self.document, self.workspace = document, workspace
        self.rng = random.Random()
        self.case = None
        self.revealed = False
        self.new_case_button = QPushButton("New case")
        self.check_button = QPushButton("Check")
        for button in (self.new_case_button, self.check_button):
            button.setFixedHeight(SIZE["control"])
        self.new_case_button.clicked.connect(self.start)
        self.check_button.clicked.connect(self.check)
        self.signs_label = self._text(INTRO)
        self.result_label = self._text("")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SIZE["panel_pad"], SIZE["panel_pad"], SIZE["panel_pad"],
                                  SIZE["panel_pad"])
        layout.setSpacing(GAP["small"])
        for widget in (self.new_case_button, self.signs_label, self.check_button,
                       self.result_label):
            layout.addWidget(widget)
        layout.addStretch(1)
        document.changed.connect(self._sync)
        self._sync()

    def _text(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        set_role(label, "body")
        return label

    def _sync(self) -> None:
        self.check_button.setEnabled(self.case is not None and not self.revealed
                                     and not self.document.lesion.is_empty)
        if self.case is not None and not self.revealed:
            self.result_label.setText(PLACE_FIRST if self.document.lesion.is_empty else "")

    def start(self) -> None:
        self.case = new_case(self.document.atlas, self.rng)
        self.revealed = False
        self.result_label.setText("")
        self.workspace.show_answer(None)
        if self.case is None:
            self.signs_label.setText(NO_CASES)
        else:
            items = "".join(f"<li>{escape(sign)}</li>" for sign in self.case.signs)
            self.signs_label.setText(f"<b>The patient has</b><ul>{items}</ul>")
            self.document.clear()
        self._sync()

    def check(self) -> None:
        if self.case is None:
            return
        matched, missed, extra = compare(self.case.signs, signs_of(self.document.report))
        self.revealed = True
        parts = []
        for title, signs in (("Matched", matched), ("Missed", missed), ("Extra", extra)):
            if signs:
                items = "".join(f"<li>{escape(s)}</li>" for s in signs)
                parts.append(f"<b>{title}</b><ul>{items}</ul>")
        parts.append(f"<p>The lesion was in the <b>{escape(self.case.label)}</b>.</p>")
        self.result_label.setText("".join(parts))
        self.workspace.window.progress_store().record_case(
            self.case.target_id, len(matched), len(missed), len(extra), datetime.now(UTC))
        self.workspace.show_answer(self.case.target)
        self.workspace.explain_case(self.case)
        self._sync()
