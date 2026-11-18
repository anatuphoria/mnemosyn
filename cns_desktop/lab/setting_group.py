from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from cns_desktop.design.icons import icon
from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import GAP, SIZE


class _Title(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SettingGroup(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title.upper()
        self.open = True
        self.forced = False
        self.header = QToolButton()
        self.header.setAutoRaise(True)
        self.header.setIconSize(QSize(SIZE["icon_header"], SIZE["icon_header"]))
        self.header.setFixedSize(SIZE["icon"] + GAP["tight"], SIZE["icon"] + GAP["tight"])
        self.header.clicked.connect(lambda: self.set_open(not self.open, by_hand=True))
        self.name = _Title(self.title)
        self.name.setWordWrap(True)
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name.setCursor(Qt.CursorShape.PointingHandCursor)
        set_role(self.name, "data")
        self.name.clicked.connect(lambda: self.set_open(not self.open, by_hand=True))
        self.count = QLabel()
        set_role(self.count, "data")
        set_tone(self.count, "edited")
        self.count.hide()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        top = QHBoxLayout()
        column.addLayout(top)
        top.setContentsMargins(SIZE["panel_pad"] - GAP["tight"], GAP["medium"], SIZE["panel_pad"],
                               0)
        top.setSpacing(GAP["small"])
        top.addWidget(self.header, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(self.name, 1)
        top.addWidget(self.count, 0, Qt.AlignmentFlag.AlignTop)
        self.body = QWidget()
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        column.addWidget(self.body)
        self._sync()

    def add(self, widget: QWidget) -> None:
        self.rows.addWidget(widget)

    def set_open(self, open_: bool, by_hand: bool = False) -> None:
        self.open = open_
        self._sync()
        if by_hand:
            self.toggled.emit(open_)

    def force_open(self, forced: bool) -> None:
        self.forced = forced
        self._sync()

    def is_shown_open(self) -> bool:
        return self.open or self.forced

    def _sync(self) -> None:
        shown = self.is_shown_open()
        self.body.setVisible(shown)
        self.header.setIcon(icon("chevron-down" if shown else "chevron-right"))
        self.header.setToolTip("Fold this group" if shown else "Unfold this group")

    def set_changed(self, count: int) -> None:
        self.count.setText(f"{count} changed")
        self.count.setVisible(count > 0)
