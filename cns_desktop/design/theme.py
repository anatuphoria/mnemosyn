from __future__ import annotations

from cns_desktop.design import fonts, stylesheet
from cns_desktop.design.tokens import COLOURS

PALETTE = {
    "Window": "s1", "WindowText": "text", "Base": "s0", "AlternateBase": "s2", "Text": "text",
    "Button": "s3", "ButtonText": "text", "Highlight": "accent", "ToolTipBase": "s3",
    "ToolTipText": "text", "PlaceholderText": "text3", "BrightText": "text", "Link": "accent_text",
    "Mid": "line", "Dark": "s0", "Light": "s3", "Midlight": "s2", "Shadow": "s0",
}


def apply_theme(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    if is_applied(app):
        return
    app.setStyle("Fusion")
    palette = QPalette()
    for role, name in PALETTE.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(COLOURS[name]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(COLOURS["text3"]))
    app.setPalette(palette)
    fonts.load_fonts()
    app.setFont(fonts.font("body"))
    app.setStyleSheet(stylesheet.build())


def is_applied(app) -> bool:
    return app.styleSheet() == stylesheet.build()


def set_role(widget, role: str) -> None:
    widget.setProperty("role", role)
    _repolish(widget)


def set_tone(widget, tone: str) -> None:
    widget.setProperty("tone", tone)
    _repolish(widget)


def set_flag(widget, name: str, on: bool) -> None:
    widget.setProperty(name, "true" if on else "false")
    _repolish(widget)


def _repolish(widget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
