from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from cns_atlas import DISCLAIMER

from ..design import rich
from ..design.theme import set_role
from ..design.tokens import GAP, SIZE

IDLE = ("Pick a route to walk it step by step. Each step says what it does and what a lesion "
        "there causes.")


class StepPanel(QWidget):
    rendered = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.heading = QLabel()
        set_role(self.heading, "data")
        self.name = QLabel()
        self.name.setWordWrap(True)
        set_role(self.name, "heading")
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.details.document().setDefaultStyleSheet(rich.document_css())
        self._body = ""
        self._note = ""
        layout = QVBoxLayout(self)
        pad = SIZE["panel_pad"]
        layout.setContentsMargins(pad, pad, pad, 0)
        layout.setSpacing(GAP["tight"])
        layout.addWidget(self.heading)
        layout.addWidget(self.name)
        layout.addWidget(self.details, 1)
        self.set_idle()

    def set_idle(self) -> None:
        self.heading.hide()
        self.name.hide()
        self._body, self._note = rich.secondary(escape(IDLE)), ""
        self._render()

    def show_step(self, index: int, total: int, name: str, html: str) -> None:
        self.heading.setText(f"STEP {index + 1} OF {total}")
        self.name.setText(name)
        self.heading.show()
        self.name.show()
        self._body = html
        self._render()

    def set_timeline_note(self, html: str) -> None:
        self._note = html
        self._render()

    def html(self) -> str:
        parts = [self._body]
        if self._note:
            parts.append(rich.heading("Timeline") + self._note)
        parts.append("<p></p>" + rich.card(escape(DISCLAIMER)))
        return "".join(parts)

    def _render(self) -> None:
        html = self.html()
        self.details.setHtml(html)
        self.rendered.emit(html)
