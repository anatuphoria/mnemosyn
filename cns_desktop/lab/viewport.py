from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import GAP, SIZE
from cns_desktop.design.widgets import SegmentedControl


class StripCard(QFrame):
    clicked = Signal()
    hover_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", "true")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compact = False
        self._full = ""
        self._short = ""
        self._tone = ""
        column = QVBoxLayout(self)
        column.setContentsMargins(GAP["medium"], GAP["small"], GAP["medium"], GAP["small"])
        column.setSpacing(GAP["tight"])
        self.title = QLabel()
        self.title.setWordWrap(True)
        set_role(self.title, "label")
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        set_role(self.detail, "secondary")
        column.addWidget(self.title)
        column.addWidget(self.detail)

    def setText(self, text: str, short: str = "") -> None:
        self._full, self._short = text, short
        self._show(self._compact and not self.underMouse())

    def _show(self, compact: bool) -> None:
        title, _, detail = self._full.partition("\n")
        if compact and detail:
            self.title.setText(self._short or f"{title} · {detail}")
            set_tone(self.title, self._tone)
            self.detail.setText(detail)
            self.detail.hide()
        else:
            set_tone(self.title, "")
            self.title.setText(title)
            self.detail.setText(detail)
            self.detail.setVisible(bool(detail))

    def text(self) -> str:
        return self._full

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self._show(compact and not self.underMouse())

    def enterEvent(self, event) -> None:
        self._show(False)
        super().enterEvent(event)
        if self._compact:
            self.hover_changed.emit()

    def leaveEvent(self, event) -> None:
        self._show(self._compact)
        super().leaveEvent(event)
        if self._compact:
            self.hover_changed.emit()

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        set_tone(self.detail, tone or "text2")
        if self._compact and not self.underMouse():
            set_tone(self.title, tone)

    def click(self) -> None:
        self.clicked.emit()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Strip(QScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(SIZE["panel_min"])
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setProperty("strip", "true")
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(GAP["small"], GAP["medium"], GAP["small"], GAP["medium"])
        column.setSpacing(GAP["small"])
        self.heading = QLabel("OUTSIDE THE BRAIN")
        set_role(self.heading, "data")
        column.addWidget(self.heading)
        self.cards = QVBoxLayout()
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(GAP["small"])
        column.addLayout(self.cards)
        column.addStretch(1)
        self.setWidget(body)

    def layout(self):
        return self.cards

    def cards_list(self) -> list[StripCard]:
        return [self.cards.itemAt(i).widget() for i in range(self.cards.count())
                if isinstance(self.cards.itemAt(i).widget(), StripCard)]

    def set_compact(self, compact: bool) -> None:
        for card in self.cards_list():
            card.set_compact(compact)

    def content_height(self) -> int:
        column = self.widget().layout()
        margins = column.contentsMargins()
        inner = self.width() - margins.left() - margins.right()
        cards = self.cards_list()
        heights = [card.heightForWidth(inner) if card.hasHeightForWidth()
                   else card.sizeHint().height() for card in cards]
        gaps = column.spacing() + self.cards.spacing() * max(len(cards) - 1, 0)
        return (margins.top() + self.heading.sizeHint().height() + gaps + sum(heights)
                + margins.bottom())


class Viewport(QWidget):
    def __init__(self, view, parent=None) -> None:
        super().__init__(parent)
        self.view = view
        self.top_bar = QFrame()
        self.top_bar.setProperty("panelheader", "true")
        self.top_bar.setFixedHeight(SIZE["header"])
        bar = QHBoxLayout(self.top_bar)
        bar.setContentsMargins(SIZE["panel_pad"], 0, GAP["small"], 0)
        bar.setSpacing(GAP["tight"])
        self.view_switch = SegmentedControl([("brain", "Brain"), ("circuit", "Circuit")])
        self.view_switch.changed.connect(lambda key: self.show_circuit(key == "circuit"))
        self.tools = QWidget()
        tools = QHBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(GAP["tight"])
        bar.addStretch(1)
        bar.addWidget(self.view_switch)
        bar.addStretch(1)
        bar.addWidget(self.tools)
        self.stack = QStackedWidget()
        self.stack.addWidget(view)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.top_bar)
        layout.addWidget(self.stack, 1)
        self.strip = Strip(self)
        self.circuit = None
        self.showing_circuit = False
        self.lab_shown = False
        self.setMinimumWidth(SIZE["central_min"])
        self.show_lab_parts(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.place_strip()

    def cards_compact(self) -> bool:
        if self.window().width() < SIZE["narrow"]:
            return True
        self.strip.set_compact(False)
        return self.strip.content_height() > self.stack.height() / 4

    def place_strip(self) -> None:
        compact = self.cards_compact()
        self.strip.set_compact(compact)
        area = self.stack.geometry()
        margin = GAP["medium"]
        width = self.strip.width()
        height = max(min(self.strip.content_height(), area.height() - 2 * margin), 0)
        self.strip.setGeometry(area.right() - margin - width + 1, area.top() + margin, width, height)
        self.strip.raise_()

    def strip_reserve(self) -> int:
        return self.strip.width() + 2 * GAP["medium"] if self.strip.isVisible() else 0

    def add_tool(self, button) -> None:
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tools.layout().addWidget(button)

    @staticmethod
    def minimum_width(workspace: str, window_width: int) -> int:
        if workspace not in ("Slices", "Lesion"):
            return SIZE["central_min"]
        return SIZE["central_min_slices"] if window_width >= SIZE["narrow"] else 0

    def fit(self, workspace: str, window_width: int) -> None:
        minimum = self.minimum_width(workspace, window_width)
        self.setMinimumWidth(minimum)
        self.setVisible(minimum > 0)

    def add_circuit(self, circuit) -> None:
        self.circuit = circuit
        self.stack.addWidget(circuit)

    def show_circuit(self, shown: bool) -> None:
        self.showing_circuit = bool(shown and self.circuit is not None)
        self.stack.setCurrentWidget(self.circuit if self.showing_circuit else self.view)
        self.strip.setVisible(self.lab_shown and not self.showing_circuit)
        self.place_strip()
        self.view_switch.set_current("circuit" if self.showing_circuit else "brain")

    def show_lab_parts(self, shown: bool) -> None:
        self.lab_shown = shown
        if not shown and self.circuit is not None:
            self.stack.setCurrentWidget(self.view)
            self.showing_circuit = False
            self.view_switch.set_current("brain")
        self.view_switch.setVisible(shown)
        self.strip.setVisible(shown and self.stack.currentWidget() is self.view)
        self.place_strip()
