from __future__ import annotations

COLOURS = {
    "s0": "#000000",
    "s1": "#0a0a0c",
    "s2": "#131317",
    "s3": "#1c1c21",
    "line": "#202026",
    "control": "#6a6a75",
    "text": "#f2f2f2",
    "text2": "#b4b4bc",
    "text3": "#6e6e78",
    "accent": "#3d6fd6",
    "accent_text": "#6d98f2",
    "edited": "#e4b04e",
    "raised": "#f0955f",
    "lowered": "#7cb0ff",
    "normal": "#8a8a95",
    "danger": "#ec6f62",
    "success": "#5fbf8f",
}

DATA_PALETTE = ("#6d98f2", "#e4b04e", "#5fbf8f", "#c58af0", "#ef7f9c", "#4fc3c9")

TYPE = {
    "title": (22, 28, 600),
    "heading": (15, 20, 600),
    "body": (13, 20, 400),
    "label": (13, 20, 500),
    "secondary": (12, 16, 400),
    "data": (11, 14, 500),
}

SPACE = (4, 8, 12, 16, 24, 32)
GAP = dict(zip(("tight", "small", "medium", "large", "wide", "widest"), SPACE, strict=True))

SIZE = {
    "control": 28,
    "row": 28,
    "header": 40,
    "status": 24,
    "lane": 44,
    "chart_row": 56,
    "chart_name": 150,
    "icon": 16,
    "icon_header": 14,
    "icon_empty": 20,
    "panel_left": 248,
    "panel_right": 320,
    "panel_min": 200,
    "panel_pad": 12,
    "indent": 12,
    "central_min": 480,
    "central_min_slices": 240,
    "narrow": 1100,
    "note_max": 90,
    "window": (1500, 900),
    "dialog": (720, 480),
}

RADIUS = {"small": 4, "control": 6, "panel": 8}

ICON_STROKE = 1.75


def _luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(name: str) -> tuple[int, int, int]:
    value = COLOURS[name].lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def color(name: str, alpha: float = 1.0):
    from PySide6.QtGui import QColor

    colour = QColor(COLOURS.get(name, name))
    colour.setAlphaF(alpha)
    return colour
