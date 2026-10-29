from __future__ import annotations

import struct
import tomllib
from functools import cache
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from cns_desktop.design.tokens import KEY as KEY_POINTS
from cns_desktop.design.tokens import KEY_BOX, KEY_STROKE

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "brand" / "fonts"
INTER = ROOT / "cns_desktop" / "resources" / "fonts" / "Inter-Medium.ttf"
INK, LIGHT, BLUE, GOLD, GREY = "#16161d", "#e8e6df", "#3d6fd6", "#d9a441", "#9a9aa8"
RULE = {INK: "#d8d8e0", LIGHT: "#2a2a33"}
LATIN = {INK: "#5a5a68", LIGHT: "#b4b4bc"}
NAME, LATIN_NAME = "ΜΝΗΜΟΣΥΝΗ", "MNEMOSYN"
NAME_SIZE, NAME_TRACKING = 64, 22
PAD = 16


class BrandError(Exception):
    pass


@cache
def font(name: str) -> TTFont:
    return TTFont(INTER if name == INTER.name else FONTS / name)


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


def svg(width: float, height: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.1f} {height:.1f}">{body}</svg>\n')


def key(size: float, x: float, y: float, colour: str = BLUE) -> str:
    scale = size / KEY_BOX
    points = " L".join(f"{x + px * scale:.2f},{y + py * scale:.2f}" for px, py in KEY_POINTS)
    return (f'<path d="M{points}" fill="none" stroke="{colour}" '
            f'stroke-width="{KEY_STROKE * scale:.2f}" stroke-linecap="square" '
            'stroke-linejoin="miter"/>')


def name(ink: str, x: float, baseline: float, size: float = NAME_SIZE,
         tracking: float = NAME_TRACKING) -> tuple[str, float, float]:
    face = font("GFSDidot-Regular.ttf")
    path, width = text_path(face, NAME, size, tracking=tracking)
    cap = -glyph_bounds(face, "Μ", size)[1]
    return f'<path d="{path}" transform="translate({x:.1f} {baseline:.1f})" fill="{ink}"/>', width, cap


def lockup(kind: str, ink: str) -> str:
    _, width, cap = name(ink, 0, 0)
    visible = (KEY_POINTS[2][0] - KEY_POINTS[0][0]) / KEY_BOX
    if kind == "line":
        size = cap / visible
        height = cap * 2 + 2 * PAD
        text, _, _ = name(ink, PAD + size + 28, (height + cap) / 2)
        return svg(PAD * 2 + size + 28 + width, height, key(size, PAD, (height - size) / 2) + text)
    if kind == "signature":
        size, gap = cap / visible, 20
        height = cap * 2 + 2 * PAD
        rule_x = PAD + size + gap
        text, _, _ = name(ink, rule_x + gap, (height + cap) / 2)
        rule = (f'<path d="M{rule_x:.1f},{(height - cap * 1.3) / 2:.1f} v{cap * 1.3:.1f}" '
                f'stroke="{RULE[ink]}" stroke-width="1.5"/>')
        return svg(rule_x + gap + width + PAD, height,
                   key(size, PAD, (height - size) / 2) + rule + text)
    if kind == "seal":
        size, gap = cap * 1.6, cap * 0.9
        total = width + 2 * PAD
        height = PAD + size + gap + cap + PAD
        text, _, _ = name(ink, PAD, PAD + size + gap + cap)
        return svg(total, height, key(size, (total - size) / 2, PAD) + text)
    if kind == "latin":
        latin_path, latin_width = text_path(font(INTER.name), LATIN_NAME, 18, tracking=7)
        size = cap * 2.1
        height = size + 2 * PAD
        left = PAD + size + 30
        top = (height - size) / 2
        text, _, _ = name(ink, left, top + cap)
        latin = (f'<path d="{latin_path}" transform="translate({left + 3:.1f} '
                 f'{top + size - 2:.1f})" fill="{LATIN[ink]}"/>')
        return svg(left + max(width, latin_width) + PAD, height, key(size, PAD, top) + text + latin)
    raise BrandError(f"unknown lockup {kind!r}")


LOCKUPS = ("line", "latin", "seal", "signature")


def mark(background: bool) -> str:
    if background:
        inset = 256 * 6 / KEY_BOX
        square = f'<rect width="256" height="256" rx="52" fill="{INK}"/>'
        return svg(256, 256, square + key(256 - 2 * inset, inset, inset))
    return svg(200, 200, key(200, 0, 0))


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
    files = {"brand/mark.svg": icon, "brand/mark-blue.svg": mark(background=False),
             "brand/key.svg": svg(KEY_BOX * 4, KEY_BOX * 4, key(KEY_BOX * 4, 0, 0)),
             "cns_desktop/resources/logo.svg": lockup("line", LIGHT),
             "site/assets/mark.svg": mark(background=False),
             "site/assets/logo-seal-dark.svg": lockup("seal", LIGHT),
             "site/assets/logo-seal-light.svg": lockup("seal", INK)}
    for kind in LOCKUPS:
        files[f"brand/logo-{kind}-dark.svg"] = lockup(kind, LIGHT)
        files[f"brand/logo-{kind}-light.svg"] = lockup(kind, INK)
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
