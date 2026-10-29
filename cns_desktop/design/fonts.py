from __future__ import annotations

from pathlib import Path

from cns_desktop.design.tokens import TYPE

FONTS = Path(__file__).resolve().parents[1] / "resources" / "fonts"
FILES = ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf")
FAMILY = "Inter"
_loaded = False


def load_fonts() -> str:
    global _loaded
    if not _loaded:
        from PySide6.QtGui import QFontDatabase

        for name in FILES:
            QFontDatabase.addApplicationFont(str(FONTS / name))
        _loaded = True
    return FAMILY


def font(role: str = "body"):
    from PySide6.QtGui import QFont

    load_fonts()
    size, _line, weight = TYPE[role]
    result = QFont(FAMILY)
    result.setPixelSize(size)
    result.setWeight(QFont.Weight(weight))
    result.setFeature(QFont.Tag("tnum"), 1)
    if role == "data":
        result.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100)
    return result
