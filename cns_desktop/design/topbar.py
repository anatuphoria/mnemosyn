from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QMenuBar, QWidget

from cns_desktop.design.tokens import SIZE

WORDMARK = Path(__file__).resolve().parents[1] / "resources" / "wordmark.svg"
WORDMARK_HEIGHT = 20
MENUS = ("File", "Edit", "View", "Study", "Experiment", "Window", "Help")


def separator() -> QFrame:
    line = QFrame()
    line.setProperty("vline", "true")
    line.setFixedSize(13, SIZE["header"])
    return line


class TopBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("topbar", "true")
        self.setFixedHeight(SIZE["header"])
        self.wordmark = QSvgWidget(str(WORDMARK))
        natural = self.wordmark.renderer().defaultSize()
        self.wordmark.setFixedSize(round(WORDMARK_HEIGHT * natural.width() / natural.height()),
                                   WORDMARK_HEIGHT)
        self.menus = QMenuBar()
        self.menus.setNativeMenuBar(False)
        self._menus: dict[str, QMenu] = {}
        for name in MENUS:
            self._menus[name] = self.menus.addMenu(name)
        self._groups: dict[str, QWidget] = {}
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(SIZE["panel_pad"], 0, 8, 0)
        self._row.setSpacing(8)
        self._row.addWidget(self.wordmark)
        self._row.addWidget(self.menus)
        self._groups_row = QHBoxLayout()
        self._groups_row.setContentsMargins(0, 0, 0, 0)
        self._groups_row.setSpacing(0)
        self._row.addLayout(self._groups_row)
        self._row.addStretch(1)
        self.switch: QWidget | None = None

    def menu(self, name: str) -> QMenu:
        return self._menus[name]

    def tidy_menus(self) -> None:
        for name, menu in self._menus.items():
            if name != "Experiment":
                menu.menuAction().setVisible(bool(menu.actions()))

    def set_switch(self, widget: QWidget) -> None:
        self.switch = widget
        self._row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_group(self, workspace: str, items: list) -> QWidget:
        group = QWidget()
        row = QHBoxLayout(group)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(separator())
        for item in items:
            row.addWidget(separator() if item is None else item)
        group.setVisible(False)
        self._groups[workspace] = group
        self._groups_row.addWidget(group)
        return group

    def group(self, workspace: str) -> QWidget | None:
        return self._groups.get(workspace)

    def show_group(self, workspace: str) -> None:
        for name, group in self._groups.items():
            group.setVisible(name == workspace)
