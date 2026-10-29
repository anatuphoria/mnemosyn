from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from cns_desktop.design import icons
from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import SIZE

SEGMENT = SIZE["control"] - 4
HEADER_BUTTON = 24


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], icons: dict[str, str] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setProperty("segmented", "true")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._keys: list[str] = []
        self._buttons: dict[str, QToolButton] = {}
        self._current = ""
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        self.setFixedHeight(SIZE["control"])
        for key, label in options:
            self.add_option(key, label, (icons or {}).get(key))

    def keys(self) -> list[str]:
        return list(self._keys)

    def button(self, key: str) -> QToolButton:
        return self._buttons[key]

    def current(self) -> str:
        return self._current

    def set_current(self, key: str) -> None:
        if key not in self._buttons:
            raise KeyError(key)
        self._buttons[key].setChecked(True)
        if key == self._current:
            return
        self._current = key
        self.changed.emit(key)

    def add_option(self, key: str, label: str, icon: str | None = None) -> None:
        button = QToolButton()
        button.setProperty("segment", "true")
        button.setText(label)
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedHeight(SEGMENT)
        if icon:
            button.setIcon(button_icon(icon))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.clicked.connect(lambda _checked=False, k=key: self.set_current(k))
        self._group.addButton(button)
        self._buttons[key] = button
        self._keys.append(key)
        self.layout().addWidget(button)
        if len(self._keys) == 1:
            self._current = key
            button.setChecked(True)

    def remove_option(self, key: str) -> None:
        button = self._buttons.pop(key)
        self._keys.remove(key)
        self._group.removeButton(button)
        button.deleteLater()
        if self._current == key and self._keys:
            self.set_current(self._keys[0])

    def keyPressEvent(self, event) -> None:
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step is None or not self._keys:
            super().keyPressEvent(event)
            return
        index = min(max(self._keys.index(self._current) + step, 0), len(self._keys) - 1)
        self.set_current(self._keys[index])


def button_icon(name: str, size: int = SIZE["icon"]):
    from PySide6.QtGui import QIcon

    result = QIcon()
    for mode, role in ((QIcon.Mode.Normal, "text2"), (QIcon.Mode.Active, "text"),
                       (QIcon.Mode.Disabled, "text3")):
        for scale in (1, 2):
            result.addPixmap(icons.pixmap(name, role, size * scale), mode, QIcon.State.Off)
            result.addPixmap(icons.pixmap(name, "text", size * scale), mode, QIcon.State.On)
    return result


def plain_name(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", text.replace("&&", "\0").replace("&", "")
                  ).replace("\0", "&").replace("…", "").strip()


def tooltip_for(action: QAction) -> str:
    name = plain_name(action.text())
    keys = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return f"{name}  {keys}" if keys else name


def icon_button(action: QAction, icon: str) -> QToolButton:
    action.setIconVisibleInMenu(False)
    action.setIcon(button_icon(icon))
    action.setToolTip(tooltip_for(action))
    action.changed.connect(lambda: action.toolTip() != tooltip_for(action)
                           and action.setToolTip(tooltip_for(action)))
    button = QToolButton()
    button.setDefaultAction(action)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setFixedSize(SIZE["control"], SIZE["control"])
    button.setIconSize(_size(SIZE["icon"]))
    button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    return button


def _size(pixels: int):
    from PySide6.QtCore import QSize

    return QSize(pixels, pixels)


class PanelHeader(QFrame):
    def __init__(self, title: str | None = None, tabs: SegmentedControl | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setProperty("panelheader", "true")
        self.setFixedHeight(SIZE["header"])
        self.tabs = tabs
        self.title = QLabel((title or "").upper())
        set_role(self.title, "data")
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(SIZE["panel_pad"], 0, 8, 0)
        self._row.setSpacing(4)
        self._row.addWidget(self.title)
        if tabs is not None:
            self.title.hide()
            self._row.addWidget(tabs)
        self._row.addStretch(1)

    def set_title(self, title: str) -> None:
        self.title.setText(title.upper())

    def add_widget(self, widget: QWidget) -> None:
        self._row.addWidget(widget)

    def add_button(self, icon: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setIcon(button_icon(icon, SIZE["icon_header"]))
        button.setIconSize(_size(SIZE["icon_header"]))
        button.setFixedSize(HEADER_BUTTON, HEADER_BUTTON)
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        button.clicked.connect(lambda _checked=False: slot())
        self._row.addWidget(button)
        return button

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(SIZE["header"])
        return hint


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.addAction(icons.icon("search", "text3", SIZE["icon"]),
                       QLineEdit.ActionPosition.LeadingPosition)
        self.setClearButtonEnabled(True)


class Card(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("card", "true")
        self.setAutoFillBackground(True)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(SIZE["panel_pad"], 8, SIZE["panel_pad"], 8)
        self.layout_.setSpacing(4)


def chip(text: str, role: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("chip", "true")
    set_tone(label, role)
    return label


def key_cap(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("keycap", "true")
    set_role(label, "data")
    return label


class _Elider(QObject):
    def __init__(self, label: QLabel, text: str) -> None:
        super().__init__(label)
        self.label = label
        self.text = text
        label.installEventFilter(self)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, label.sizePolicy().verticalPolicy())
        self.apply()

    def apply(self) -> None:
        metrics = self.label.fontMetrics()
        width = self.label.contentsRect().width()
        shown = metrics.elidedText(self.text, Qt.TextElideMode.ElideRight, max(width, 0))
        self.label.setText(shown)
        self.label.setToolTip("" if shown == self.text else self.text)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange,
                            QEvent.Type.StyleChange):
            self.apply()
        return False


def elided(label: QLabel, text: str) -> None:
    elider = label.findChild(_Elider)
    if elider is None:
        _Elider(label, text)
        return
    elider.text = text
    elider.apply()
