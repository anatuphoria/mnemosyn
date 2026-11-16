from __future__ import annotations

from .design.tokens import DEFAULT_THEME, THEMES

THEME_KEY = "appearance/theme"
TIMELINE = {"compare": "lab/normal_line", "show_guides": "lab/change_guides",
            "show_hover": "lab/hover_values", "show_overview": "lab/overview"}


def stored_theme(settings) -> str:
    if settings is None:
        return DEFAULT_THEME
    name = settings.value(THEME_KEY, DEFAULT_THEME, type=str)
    return name if name in THEMES else DEFAULT_THEME


def store_theme(settings, name: str) -> None:
    if settings is not None and name in THEMES:
        settings.setValue(THEME_KEY, name)


def load_timeline(settings, timeline) -> None:
    if settings is None:
        return
    for name, key in TIMELINE.items():
        setattr(timeline, name, settings.value(key, getattr(timeline, name), type=bool))
    timeline.update()


def save_timeline(settings, timeline) -> None:
    if settings is None:
        return
    for name, key in TIMELINE.items():
        settings.setValue(key, bool(getattr(timeline, name)))
