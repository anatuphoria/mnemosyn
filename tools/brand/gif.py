from __future__ import annotations

import math
import shutil
from itertools import pairwise
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import (BLUE, DRAW_SECONDS, INK, KEY_BOX, KEY_POINTS, KEY_STROKE, LETTER_START, LETTER_STEP,
               LIGHT, NAME, NAME_SIZE, NAME_TRACKING, TRACE_BEZIER, TRACE_DELAY, TRACE_LENGTH,
               TRACE_SECONDS, font, geometry, svg, text_path)

BACKGROUND = {"dark": "#0a0a0c", "light": "#ffffff"}
INKS = {"dark": LIGHT, "light": INK}
DRAW_DELAY, RISE_SECONDS, RISE_PIXELS = 0.2, 0.7, 8.0
HOLD = {"seal": 2.0, "line": 2.0, "icon": 1.6}
WIDTH = {"seal": 720, "line": 840, "icon": 256}


def bezier(x1: float, y1: float, x2: float, y2: float):
    def at(a: float, b: float, t: float) -> float:
        return 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3

    def ease(x: float) -> float:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        low, high = 0.0, 1.0
        for _ in range(40):
            mid = (low + high) / 2
            low, high = (mid, high) if at(x1, x2, mid) < x else (low, mid)
        return at(y1, y2, (low + high) / 2)

    return ease


DRAW_EASE = bezier(.65, 0, .35, 1)
RISE_EASE = bezier(.2, .7, .2, 1)
TRACE_EASE = bezier(*TRACE_BEZIER)


def progress(t: float, delay: float, seconds: float) -> float:
    return min(max((t - delay) / seconds, 0.0), 1.0)


@dataclass(frozen=True)
class LogoState:
    key_opacity: float
    key_drawn: float
    letter_opacity: tuple[float, ...]
    letter_rise: tuple[float, ...]


@dataclass(frozen=True)
class IconState:
    trace_opacity: float
    trace_start: float


def seal_state(t: float) -> LogoState:
    raw = progress(t, DRAW_DELAY, DRAW_SECONDS)
    eased = [RISE_EASE(progress(t, LETTER_START + LETTER_STEP * n, RISE_SECONDS))
             for n in range(len(NAME))]
    return LogoState(1.0 if raw > 0 else 0.0, DRAW_EASE(raw), tuple(eased),
                     tuple(RISE_PIXELS * (1 - e) for e in eased))


line_state = seal_state


def icon_state(t: float) -> IconState:
    raw = progress(t, TRACE_DELAY, TRACE_SECONDS)
    if raw <= 0 or raw >= 1:
        opacity = 0.0
    elif raw < 0.08:
        opacity = TRACE_EASE(raw / 0.08)
    elif raw < 0.85:
        opacity = 1.0
    else:
        opacity = 1 - TRACE_EASE((raw - 0.85) / 0.15)
    offset = TRACE_LENGTH + (-1 - TRACE_LENGTH) * TRACE_EASE(raw)
    return IconState(opacity, -offset)


def key_length(size: float) -> float:
    scale = size / KEY_BOX
    return scale * sum(math.dist(a, b) for a, b in pairwise(KEY_POINTS))


def key_path(size: float, x: float, y: float, colour: str, dashes: str, opacity: float,
             offset: float = 0.0) -> str:
    scale = size / KEY_BOX
    points = " L".join(f"{x + px * scale:.2f},{y + py * scale:.2f}" for px, py in KEY_POINTS)
    return (f'<path d="M{points}" fill="none" stroke="{colour}" '
            f'stroke-width="{KEY_STROKE * scale:.2f}" stroke-linecap="square" '
            f'stroke-linejoin="miter" stroke-dasharray="{dashes}" stroke-dashoffset="{offset:.2f}" '
            f'opacity="{opacity:.3f}"/>')


def logo_frame(kind: str, theme: str, t: float) -> str:
    g = geometry(kind)
    state = seal_state(t)
    length = key_length(g["key"])
    drawn = max(state.key_drawn * length, 0.01)
    body = key_path(g["key"], g["key_x"], g["key_y"], BLUE, f"{drawn:.2f} {length * 2:.2f}",
                    state.key_opacity)
    face, left = font("GFSDidot-Regular.ttf"), g["name_x"]
    for n, char in enumerate(NAME):
        path, width = text_path(face, char, NAME_SIZE)
        body += (f'<g transform="translate({left:.1f} {g["baseline"] + state.letter_rise[n]:.2f})">'
                 f'<path d="{path}" fill="{INKS[theme]}" opacity="{state.letter_opacity[n]:.3f}"/></g>')
        left += width + NAME_TRACKING
    return svg(g["width"], g["height"], body)


def icon_frame(t: float) -> str:
    inset = 256 * 6 / KEY_BOX
    size = 256 - 2 * inset
    length = key_length(size)
    state = icon_state(t)
    start = max(state.trace_start, 0.0)
    shown = state.trace_start + TRACE_LENGTH - start
    body = f'<rect width="256" height="256" rx="52" fill="{INK}"/>'
    body += key_path(size, inset, inset, BLUE, f"{length * 2:.2f} 0", 1.0)
    if shown > 0 and state.trace_opacity > 0:
        dashes = f"{shown * length:.2f} {length * 3:.2f}"
        body += key_path(size, inset, inset, LIGHT, dashes, state.trace_opacity, -start * length)
    return svg(256, 256, body)


def frame_svg(kind: str, theme: str, t: float) -> str:
    return icon_frame(t) if kind == "icon" else logo_frame(kind, theme, t)


def duration(kind: str) -> float:
    if kind == "icon":
        return TRACE_DELAY + TRACE_SECONDS + HOLD["icon"]
    last = LETTER_START + LETTER_STEP * (len(NAME) - 1) + RISE_SECONDS
    return max(DRAW_DELAY + DRAW_SECONDS, last) + HOLD[kind]


def render(svg_text: str, width: int, background: str):
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    renderer = QSvgRenderer(QByteArray(svg_text.encode()))
    natural = renderer.defaultSize()
    height = round(width * natural.height() / natural.width())
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def write_gif(kind: str, theme: str, out: Path, fps: int = 30, size: int | None = None) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is needed to write GIFs")
    out.mkdir(parents=True, exist_ok=True)
    target = out / (f"icon-{theme}.gif" if kind == "icon" else f"logo-{kind}-{theme}.gif")
    width = size or WIDTH[kind]
    with tempfile.TemporaryDirectory() as folder:
        frames = round(duration(kind) * fps)
        for n in range(frames):
            image = render(frame_svg(kind, theme, n / fps), width, BACKGROUND[theme])
            image.save(str(Path(folder) / f"f{n:04d}.png"))
        palette = "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-i",
                        str(Path(folder) / "f%04d.png"), "-vf", palette, "-loop", "0",
                        str(target)], check=True)
    return target


def write_gifs(out: Path) -> list[Path]:
    return [write_gif(kind, theme, out) for kind in ("seal", "line", "icon")
            for theme in ("dark", "light")]
