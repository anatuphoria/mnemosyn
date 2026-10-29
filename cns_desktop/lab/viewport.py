from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget


class Viewport(QWidget):
    def __init__(self, view, parent=None) -> None:
        super().__init__(parent)
        self.view = view
        self.top_bar = QWidget()
        self.top_bar.setLayout(QHBoxLayout())
        self.top_bar.layout().setContentsMargins(4, 2, 4, 2)
        self.stack = QStackedWidget()
        self.stack.addWidget(view)
        self.strip = QWidget()
        self.strip.setLayout(QVBoxLayout())
        self.strip.layout().setContentsMargins(4, 4, 4, 4)
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
        self.show_lab_parts(False)

    def show_lab_parts(self, shown: bool) -> None:
        self.top_bar.setVisible(shown)
        self.strip.setVisible(shown and self.stack.currentWidget() is self.view)
