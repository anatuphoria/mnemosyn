from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from . import icons

ICON_SIZE = 32
KINDS = {"info": ("info", "accent_text"), "warning": ("triangle-alert", "edited"),
         "question": ("circle-help", "accent_text")}
Button = QMessageBox.StandardButton


def message_box(parent, kind: str, title: str, text: str, buttons=Button.Ok,
                default=None) -> QMessageBox:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)
    if default is not None:
        box.setDefaultButton(default)
    name, role = KINDS[kind]
    picture = icons.pixmap(name, role, ICON_SIZE * 2)
    picture.setDevicePixelRatio(2)
    box.setIconPixmap(picture)
    box.setProperty("kind", kind)
    return box


def ask(parent, title: str, text: str, buttons, default=None):
    return Button(message_box(parent, "question", title, text, buttons, default).exec())


def inform(parent, title: str, text: str) -> None:
    message_box(parent, "info", title, text).exec()


def warn(parent, title: str, text: str) -> QMessageBox:
    box = message_box(parent, "warning", title, text)
    box.open()
    return box
