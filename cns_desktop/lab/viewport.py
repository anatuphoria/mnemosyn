from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import SIZE
from cns_desktop.design.widgets import SegmentedControl

STRIP_WIDTH = 200


class StripCard(QFrame):
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        column = QVBoxLayout(self)
        column.setContentsMargins(12, 8, 12, 8)
        column.setSpacing(2)
        self.title = QLabel()
        set_role(self.title, "label")
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        set_role(self.detail, "secondary")
        column.addWidget(self.title)
        column.addWidget(self.detail)

    def setText(self, text: str) -> None:
        title, _, detail = text.partition("\n")
        self.title.setText(title)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))

    def text(self) -> str:
        detail = self.detail.text()
        return f"{self.title.text()}\n{detail}" if detail else self.title.text()

    def set_tone(self, tone: str) -> None:
        set_tone(self.detail, tone or "text2")

    def click(self) -> None:
        self.clicked.emit()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Strip(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(STRIP_WIDTH)
        self.setWidgetResizable(True)
        self.setProperty("strip", "true")
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(8, 12, 8, 12)
        column.setSpacing(8)
        self.heading = QLabel("OUTSIDE THE BRAIN")
        set_role(self.heading, "data")
        column.addWidget(self.heading)
        self.cards = QVBoxLayout()
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(8)
        column.addLayout(self.cards)
        column.addStretch(1)
        self.setWidget(body)

    def layout(self):
        return self.cards


class Viewport(QWidget):
    def __init__(self, view, parent=None) -> None:
        super().__init__(parent)
        self.view = view
        self.top_bar = QFrame()
        self.top_bar.setProperty("panelheader", "true")
        self.top_bar.setFixedHeight(SIZE["header"])
        bar = QHBoxLayout(self.top_bar)
        bar.setContentsMargins(SIZE["panel_pad"], 0, 8, 0)
        bar.setSpacing(4)
        self.view_switch = SegmentedControl([("brain", "Brain"), ("circuit", "Circuit")])
        self.view_switch.changed.connect(lambda key: self.show_circuit(key == "circuit"))
        self.tools = QWidget()
        tools = QHBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(2)
        bar.addStretch(1)
        bar.addWidget(self.view_switch)
        bar.addStretch(1)
        bar.addWidget(self.tools)
        self.stack = QStackedWidget()
        self.stack.addWidget(view)
        self.strip = Strip()
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.stack, 1)
        row.addWidget(self.strip)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.top_bar)
        layout.addLayout(row, 1)
        self.circuit = None
        self.showing_circuit = False
        self.lab_shown = False
        self.setMinimumWidth(SIZE["central_min"])
        self.show_lab_parts(False)

    def add_tool(self, button) -> None:
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tools.layout().addWidget(button)

    @staticmethod
    def minimum_width(workspace: str, window_width: int) -> int:
        if workspace != "Slices":
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
        self.view_switch.set_current("circuit" if self.showing_circuit else "brain")

    def show_lab_parts(self, shown: bool) -> None:
        self.lab_shown = shown
        if not shown and self.circuit is not None:
            self.stack.setCurrentWidget(self.view)
            self.showing_circuit = False
            self.view_switch.set_current("brain")
        self.view_switch.setVisible(shown)
        self.strip.setVisible(shown and self.stack.currentWidget() is self.view)
