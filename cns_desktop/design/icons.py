from __future__ import annotations

from functools import cache
from pathlib import Path

from cns_desktop.design.tokens import COLOURS, ICON_STROKE

ICONS = Path(__file__).resolve().parents[1] / "resources" / "icons"
NAMES = tuple(sorted(path.stem for path in ICONS.glob("*.svg")))


@cache
def _svg(name: str, role: str) -> bytes:
    if name not in NAMES:
        raise KeyError(name)
    text = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    text = text.replace("currentColor", COLOURS.get(role, role))
    text = text.replace('stroke-width="2"', f'stroke-width="{ICON_STROKE}"')
    return text.encode("utf-8")


def _render(name: str, role: str, pixels: int):
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(_svg(name, role)))
    image = QPixmap(pixels, pixels)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


@cache
def pixmap(name: str, role: str = "text2", size: int = 16):
    return _render(name, role, size)


@cache
def icon(name: str, role: str = "text2", size: int = 16):
    from PySide6.QtGui import QIcon

    result = QIcon()
    for scale in (1, 2):
        result.addPixmap(_render(name, role, size * scale), QIcon.Mode.Normal)
        result.addPixmap(_render(name, "text3", size * scale), QIcon.Mode.Disabled)
    return result
