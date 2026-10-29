from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from cns_desktop.design.tokens import color

BOX = 40.0
KEY = ((6, 34), (6, 6), (34, 6), (34, 30), (14, 30), (14, 14), (26, 14), (26, 22), (20, 22))
STROKE = 3.2


def key_path(size: float) -> QPainterPath:
    scale = size / BOX
    first, *rest = KEY
    path = QPainterPath(QPointF(first[0] * scale, first[1] * scale))
    for x, y in rest:
        path.lineTo(x * scale, y * scale)
    return path


class KeyMark(QWidget):
    def __init__(self, size: int = 20, role: str = "accent", parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.role = role
        self.setToolTip("Mnemosyn")

    def set_role(self, role: str) -> None:
        self.role = role
        self.update()

    def paintEvent(self, _event) -> None:
        size = self.width()
        pen = QPen(color(self.role), STROKE * size / BOX)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(pen)
        painter.drawPath(key_path(size))
        painter.end()
