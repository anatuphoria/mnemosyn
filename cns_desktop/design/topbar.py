from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QMenuBar, QToolButton, QWidget

from cns_desktop.design.tokens import SIZE
from cns_desktop.design.widgets import button_icon

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
        self.menu_button = QToolButton()
        self.menu_button.setIcon(button_icon("menu"))
        self.menu_button.setToolTip("Menu")
        self.menu_button.setFixedSize(SIZE["control"], SIZE["control"])
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setMenu(QMenu(self.menu_button))
        for menu in self._menus.values():
            self.menu_button.menu().addMenu(menu)
        self.menu_button.hide()
        self.compact = False
        self.level = 0
        self._fitting = False
        self._fitted: tuple = ()
        self._shown = ""
        self._groups: dict[str, QWidget] = {}
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(SIZE["panel_pad"], 0, 8, 0)
        self._row.setSpacing(8)
        self._row.addWidget(self.wordmark)
        self._row.addWidget(self.menu_button)
        self._row.addWidget(self.menus)
        self._groups_row = QHBoxLayout()
        self._groups_row.setContentsMargins(0, 0, 0, 0)
        self._groups_row.setSpacing(0)
        self._row.addLayout(self._groups_row)
        self._row.addStretch(1)
        self.switch: QWidget | None = None

    def minimumSizeHint(self):
        return QSize(0, SIZE["header"])

    def menu(self, name: str) -> QMenu:
        return self._menus[name]

    def tidy_menus(self) -> None:
        for name, menu in self._menus.items():
            if name != "Experiment":
                menu.menuAction().setVisible(bool(menu.actions()))

    def set_compact(self, compact: bool) -> None:
        self._set_level(2 if compact else 0)

    def _set_level(self, level: int) -> None:
        self.level = level
        self.compact = level >= 2
        self.menus.setVisible(level < 2)
        self.menu_button.setVisible(level >= 2)
        self.wordmark.setVisible(level < 2)
        if self.switch is not None and hasattr(self.switch, "set_compact"):
            self.switch.set_compact(level >= 1)

    def _signature(self, width: int) -> tuple:
        return width, self._shown, self.level, self._row.sizeHint().width()

    def fit(self, width: int | None = None) -> None:
        width = self.width() if width is None else width
        for level in range(3):
            self._set_level(level)
            self._row.invalidate()
            if self._row.sizeHint().width() <= width:
                break
        self._row.activate()
        self._fitted = self._signature(width)

    def event(self, event) -> bool:
        if (event.type() == QEvent.Type.LayoutRequest and not self._fitting
                and self._signature(self.width()) != self._fitted):
            self._fitting = True
            QTimer.singleShot(0, self._refit)
        return super().event(event)

    def _refit(self) -> None:
        self._fitting = False
        if self._signature(self.width()) != self._fitted:
            self.fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.fit(event.size().width())

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
        self._shown = workspace
        for name, group in self._groups.items():
            group.setVisible(name == workspace)
            if name == workspace:
                for child in group.findChildren(QWidget):
                    child.updateGeometry()
                group.layout().invalidate()
        self.fit()
