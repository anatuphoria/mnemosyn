from __future__ import annotations

import struct
import tomllib
from functools import cache
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "brand" / "fonts"
INK, LIGHT, BLUE, GOLD, GREY = "#16161d", "#e8e6df", "#3d6fd6", "#d9a441", "#9a9aa8"
NAME, MARK = "ΜΝΗΜΟΣΥΝΗ", "\U0001684e"
KEY = "M{x},13 h20 M{end},13 v-12 h-14 v8 h8 v-4 h-4"
MARK_WEIGHT = 600


class BrandError(Exception):
    pass


@cache
def font(name: str) -> TTFont:
    return TTFont(FONTS / name)


def glyph_set(face: TTFont, weight: float | None):
    return face.getGlyphSet(location={"wght": weight}) if weight else face.getGlyphSet()


def text_path(face: TTFont, text: str, size: float, tracking: float = 0.0,
              weight: float | None = None) -> tuple[str, float]:
    cmap, glyphs = face.getBestCmap(), glyph_set(face, weight)
    scale = size / face["head"].unitsPerEm
    pen, x = SVGPathPen(glyphs), 0.0
    for char in text:
        if ord(char) not in cmap:
            raise BrandError(f"{char!r} is not in {Path(face.reader.file.name).stem}")
        glyph = glyphs[cmap[ord(char)]]
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        x += glyph.width * scale + tracking
    return pen.getCommands(), x - tracking if text else 0.0


def glyph_bounds(face: TTFont, char: str, size: float,
                 weight: float | None = None) -> tuple[float, float, float, float]:
    glyphs, cmap = glyph_set(face, weight), face.getBestCmap()
    if ord(char) not in cmap:
        raise BrandError(f"{char!r} is not in {Path(face.reader.file.name).stem}")
    scale = size / face["head"].unitsPerEm
    pen = BoundsPen(glyphs)
    glyphs[cmap[ord(char)]].draw(TransformPen(pen, (scale, 0, 0, -scale, 0, 0)))
    return pen.bounds


def meander(width: float, colour: str, y: float = 0.0, scale: float = 1.0) -> str:
    steps = max(1, int(width // (20 * scale)))
    start = (width - steps * 20 * scale) / 2
    left = start / scale
    path = "".join(KEY.format(x=left + 20 * i, end=left + 20 * i + 18) for i in range(steps))
    return (f'<path d="{path}" transform="translate(0 {y}) scale({scale})" fill="none" '
            f'stroke="{colour}" stroke-width="1.6" stroke-linejoin="miter"/>')


def svg(width: float, height: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.1f} {height:.1f}">{body}</svg>\n')


def wordmark(ink: str) -> str:
    path, width = text_path(font("GFSDidot-Regular.ttf"), NAME, 64, tracking=22)
    total, height = width + 80, 172
    letters = f'<path d="{path}" transform="translate(40 116)" fill="{ink}"/>'
    return svg(total, height, meander(total, BLUE, 6, 1.5) + letters + meander(total, BLUE, 142, 1.5))


def mark(background: bool) -> str:
    face = font("NotoSansBamum.ttf")
    x0, y0, x1, y1 = glyph_bounds(face, MARK, 100, MARK_WEIGHT)
    size = 100 * (176 if background else 200) / max(x1 - x0, y1 - y0)
    path, _ = text_path(face, MARK, size, weight=MARK_WEIGHT)
    x0, y0, x1, y1 = glyph_bounds(face, MARK, size, MARK_WEIGHT)
    if background:
        dx, dy = 128 - (x0 + x1) / 2, 128 - (y0 + y1) / 2
        square = f'<rect width="256" height="256" rx="52" fill="{INK}"/>'
        return svg(256, 256, square + f'<path d="{path}" transform="translate({dx:.1f} {dy:.1f})" '
                   f'fill="{LIGHT}"/>')
    width, height = x1 - x0 + 16, y1 - y0 + 16
    return svg(width, height, f'<path d="{path}" transform="translate({8 - x0:.1f} {8 - y0:.1f})" '
               f'fill="{BLUE}"/>')


def divider(colour: str) -> str:
    return svg(800, 16, meander(800, colour, 1, 1.0))


def badges(version: str) -> dict[str, tuple[str, str]]:
    release = f"{version} test" if version.split(".")[0] == "0" else version
    return {"release": ("RELEASE", release), "licence": ("LICENCE", "GPL 3.0"),
            "platforms": ("FOR", "Windows · Linux"), "website": ("WEBSITE", "mnemo.saeed.cool"),
            "review": ("REVIEW", "open to specialists")}


def badge(label: str, value: str, rule: str) -> str:
    face = font("GFSDidot-Regular.ttf")
    label_path, label_width = text_path(face, label, 13, tracking=2.6)
    value_path, value_width = text_path(face, value, 15, tracking=0.4)
    width, height = label_width + value_width + 40, 32
    body = (f'<rect width="{width:.1f}" height="{height}" rx="3" fill="{INK}"/>'
            f'<path d="M8,5 H{width - 8:.1f} M8,27 H{width - 8:.1f}" stroke="{rule}" '
            'stroke-width="1"/>'
            f'<path d="{label_path}" transform="translate(13 21)" fill="{GREY}"/>'
            f'<path d="{value_path}" transform="translate({width - 13 - value_width:.1f} 21.5)" '
            f'fill="{LIGHT}"/>')
    return svg(width, height, body)


def ico(images: dict[int, bytes]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset, entries, data = 6 + 16 * len(images), b"", b""
    for size, png in sorted(images.items()):
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png),
                               offset + len(data))
        data += png
    return header + entries + data


def raster(svg_text: str, size: int) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(QByteArray(svg_text.encode())).render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def project_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def write_all(root: Path, version: str) -> list[Path]:
    icon = mark(background=True)
    files = {"brand/wordmark-dark.svg": wordmark(LIGHT), "brand/wordmark-light.svg": wordmark(INK),
             "brand/mark.svg": icon, "brand/mark-blue.svg": mark(background=False),
             "brand/divider.svg": divider(BLUE), "brand/divider-gold.svg": divider(GOLD),
             "cns_desktop/resources/wordmark.svg": wordmark(LIGHT),
             "site/assets/mark.svg": mark(background=False),
             "site/assets/divider.svg": divider(BLUE)}
    for name, (label, value) in badges(version).items():
        files[f"brand/badge-{name}.svg"] = badge(label, value, GOLD if name == "review" else BLUE)
    binaries = {"cns_desktop/resources/mark.png": raster(icon, 256),
                "tools/package/mnemosyn.png": raster(icon, 256),
                "site/assets/favicon.png": raster(icon, 64),
                "tools/package/mnemosyn.ico": ico({s: raster(icon, s) for s in (16, 32, 48, 256)})}
    written = []
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
        written.append(root / name)
    for name, data in binaries.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
        written.append(root / name)
    return written
