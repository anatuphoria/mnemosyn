from __future__ import annotations

from html import escape

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from cns_atlas import DISCLAIMER, Crossing, Pathway, Relay
from cns_atlas.pathways import PathwayText, resolve, side_of

from ..state import AppState
from .info_panel import references_html

NO_PATHWAYS = "This atlas has no pathways yet."
RELAY_COLOR = QColor("#8a8a99")
KEY_ROLE = Qt.ItemDataRole.UserRole


def _column(*widgets) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        if isinstance(widget, QHBoxLayout):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    return page


class PathwayPanel(QWidget):
    entered = Signal()
    left = Signal()
    centre_requested = Signal()

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pathway: Pathway | None = None
        self.side = "left"
        self.index = 0
        self.lights: list[tuple[int, ...]] = []
        self.route: frozenset[int] = frozenset()
        self.text: PathwayText | None = None
        self._applying = False

        self.choices = QListWidget()
        for pathway in state.atlas.pathways:
            item = QListWidgetItem(pathway.name)
            item.setData(KEY_ROLE, pathway.key)
            self.choices.addItem(item)
        self.empty = QLabel(NO_PATHWAYS)
        self.empty.setVisible(not state.atlas.pathways)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.start = QLabel()
        sides = QHBoxLayout()
        group = QButtonGroup(self)
        self.side_buttons: dict[str, QPushButton] = {}
        for side in ("left", "right"):
            button = QPushButton(side.capitalize())
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, s=side: self.set_side(s))
            group.addButton(button)
            sides.addWidget(button)
            self.side_buttons[side] = button
        self.draft = QLabel("<b>Draft</b>: not yet reviewed.")
        self.steps = QListWidget()
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.back_button = QPushButton("Back (Left)")
        self.next_button = QPushButton("Next (Right)")
        self.leave_button = QPushButton("Leave pathway (Esc)")
        nav = QHBoxLayout()
        nav.addWidget(self.back_button)
        nav.addWidget(self.next_button)
        for widget in (*self.side_buttons.values(), self.steps, self.details, self.back_button,
                       self.next_button, self.leave_button):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.pages = QStackedWidget()
        self.pages.addWidget(_column(self.choices, self.empty))
        self.pages.addWidget(_column(self.title, self.start, sides, self.draft, self.steps,
                                     self.details, nav, self.leave_button))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pages)

        self.choices.itemClicked.connect(lambda item: self.open(item.data(KEY_ROLE)))
        self.steps.currentRowChanged.connect(self._on_row)
        self.back_button.clicked.connect(self.back)
        self.next_button.clicked.connect(self.next)
        self.leave_button.clicked.connect(self.leave)
        state.selection_changed.connect(self._on_selection)

    def open(self, key: str, side: str = "left") -> None:
        pathway = {p.key: p for p in self.state.atlas.pathways}[key]
        if self.pathway is None:
            self.entered.emit()
        self.pathway, self.index = pathway, 0
        self.title.setText(f"<b>{escape(pathway.name)}</b>")
        self.pages.setCurrentIndex(1)
        self.set_side(side)
        self.setFocus()

    def set_side(self, side: str) -> None:
        if self.pathway is None:
            return
        atlas = self.state.atlas
        self.side = side
        self.side_buttons[side].setChecked(True)
        self.lights = [resolve(atlas, step, side) for step in self.pathway.steps]
        self.route = frozenset(i for ids in self.lights for i in ids)
        self.text = atlas.pathway_text(self.pathway.key, side)
        self.start.setText(f"Start: {side} {self.pathway.start}")
        self.draft.setVisible(self.text is not None and self.text.status == "draft")
        with QSignalBlocker(self.steps):
            self.steps.clear()
            for n, step in enumerate(self.pathway.steps, 1):
                item = QListWidgetItem(self.label(n, step))
                if isinstance(step, Relay):
                    item.setForeground(RELAY_COLOR)
                self.steps.addItem(item)
        self.state.set_focus(self.route)
        self.state.set_hidden([i for i in self.state.tract_ids if i not in self.route], True)
        self.state.set_hidden(self.route, False)
        self.go(self.index)

    def label(self, n: int, step) -> str:
        if isinstance(step, Crossing):
            return f"{n} ✕ {step.name}"
        where = side_of(step.side, self.side)
        if isinstance(step, Relay):
            return f"{n} {step.name} ({where})"
        names = " and ".join(self.state.atlas.get(i).name for i in step.structures)
        return f"{n} {names} ({where})"

    def go(self, index: int, chosen: int | None = None) -> None:
        if self.pathway is None:
            return
        self.index = max(0, min(index, len(self.pathway.steps) - 1))
        ids = self.lights[self.index]
        selected = chosen if chosen in ids else (ids[0] if ids else None)
        self._applying = True
        try:
            self.state.select(selected, emphasis=ids)
        finally:
            self._applying = False
        if ids:
            self.centre_requested.emit()
        with QSignalBlocker(self.steps):
            self.steps.setCurrentRow(self.index)
        self.back_button.setEnabled(self.index > 0)
        self.next_button.setEnabled(self.index < len(self.pathway.steps) - 1)
        self.details.setHtml(self._details_html())

    def next(self) -> None:
        self.go(self.index + 1)

    def back(self) -> None:
        self.go(self.index - 1)

    def leave(self) -> None:
        if self.pathway is None:
            return
        self.pathway, self.lights, self.route, self.text = None, [], frozenset(), None
        self.pages.setCurrentIndex(0)
        self.left.emit()

    def _on_row(self, row: int) -> None:
        if row >= 0:
            self.go(row)

    def _on_selection(self, structure_id: int | None) -> None:
        if self._applying or self.pathway is None or structure_id is None:
            return
        found = [n for n, ids in enumerate(self.lights) if structure_id in ids]
        if found:
            self.go(self.index if self.index in found else found[0], chosen=structure_id)

    def _details_html(self) -> str:
        parts = [f"<h3>{escape(self.steps.item(self.index).text())}</h3>"]
        if self.text is None:
            parts.append("<p><i>No description yet.</i></p>")
        else:
            step = self.text.steps[self.index]
            parts.append(f"<p><b>Role</b>: {escape(step.role)}</p>")
            parts.append(f"<p><b>Lesion</b>: {escape(step.lesion)}</p>")
            parts.append(f"<h4>Overview</h4><p>{escape(self.text.overview)}</p>")
            parts += references_html(self.text.references)
        parts.append(f"<p style='color:#c55'><small>{escape(DISCLAIMER)}</small></p>")
        return "".join(parts)

    def keyPressEvent(self, event) -> None:
        if self.pathway is not None and event.key() == Qt.Key.Key_Right:
            self.next()
        elif self.pathway is not None and event.key() == Qt.Key.Key_Left:
            self.back()
        else:
            super().keyPressEvent(event)
