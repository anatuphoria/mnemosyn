from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FPS, WIDTH, HEIGHT, FADE = 30, 1280, 800, 9
WINDOW = (1600, 1000)
SCENES = (("intro", 2.6), ("explore", 3.0), ("slices", 2.6), ("pathway", 3.2), ("lab", 3.6),
          ("end", 2.6))
CAPTIONS = {"explore": "The brain and spinal cord, in 3D.", "slices": "Read it like an atlas.",
            "pathway": "Follow a pathway, station by station.", "lab": "Change the body. See why."}
TAGLINE, ADDRESS = "Free  ·  open data  ·  every source cited", "mnemo.saeed.cool"
ROUTE, CHANGE = "cerebellar", "stalk_cut"


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 3 * x * x - 2 * x * x * x


def encode_commands(frames: Path, out: Path) -> list[tuple[str, list[str]]]:
    source = ["-framerate", str(FPS), "-i", str(frames / "f%05d.png")]
    base = ["ffmpeg", "-loglevel", "error", "-y"]
    return [
        ("mp4", [*base, *source, "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "teaser.mp4")]),
        ("avif", [*base, *source, "-c:v", "libsvtav1", "-crf", "30", "-preset", "6",
                  "-pix_fmt", "yuv420p", "-f", "avif", str(out / "teaser.avif")]),
        ("webp", [*base, *source, "-vf", "fps=15", "-c:v", "libwebp_anim", "-loop", "0",
                  "-quality", "90", "-compression_level", "6", "-preset", "picture",
                  str(out / "teaser.webp")]),
    ]


class Recorder:
    def __init__(self, frames: Path) -> None:
        from PySide6.QtWidgets import QApplication

        from cns_atlas import Atlas
        from cns_desktop.app import DEFAULT_ATLAS
        from cns_desktop.design.theme import apply_theme
        from cns_desktop.main_window import MainWindow

        self.app = QApplication.instance() or QApplication([])
        apply_theme(self.app)
        self.frames = frames
        self.count = 0
        self.previous = None
        self.window = MainWindow(Atlas.open(DEFAULT_ATLAS),
                                 progress_path=Path(tempfile.mkdtemp()) / "progress.sqlite")
        self.window.setFixedSize(*WINDOW)
        self.window.show()
        self.wait(3000)
        self.camera = self.window.view.renderer.GetActiveCamera()

    def wait(self, ms: int) -> None:
        from PySide6.QtCore import QTimer

        timer = QTimer()
        timer.setSingleShot(True)
        timer.start(ms)
        while timer.isActive():
            self.app.processEvents()

    def font(self, size: int, weight: int):
        from PySide6.QtGui import QFont

        from cns_desktop.design.fonts import font

        result = QFont(font("label"))
        result.setPixelSize(size)
        result.setWeight(QFont.Weight(weight))
        return result

    def canvas(self):
        from PySide6.QtGui import QColor, QImage

        image = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
        image.fill(QColor("#000000"))
        return image

    def save(self, image, frame: int) -> None:
        from PySide6.QtGui import QPainter

        if self.previous is not None and frame < FADE:
            painter = QPainter(image)
            painter.setOpacity(1 - frame / FADE)
            painter.drawImage(0, 0, self.previous)
            painter.end()
        image.save(str(self.frames / f"f{self.count:05d}.png"))
        self.count += 1

    def finish(self, image) -> None:
        self.previous = image

    def caption(self, painter, text: str, alpha: float) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QLinearGradient

        band = QLinearGradient(QPointF(0, HEIGHT - 190), QPointF(0, HEIGHT))
        band.setColorAt(0, QColor(0, 0, 0, 0))
        band.setColorAt(1, QColor(0, 0, 0, int(215 * alpha)))
        painter.fillRect(QRectF(0, HEIGHT - 190, WIDTH, 190), band)
        painter.setOpacity(alpha)
        painter.setPen(QColor("#f2f2f2"))
        painter.setFont(self.font(34, 600))
        painter.drawText(QPointF(64, HEIGHT - 62), text)
        painter.setOpacity(1.0)

    def seal(self, painter, t: float, width: int = 560, top: float | None = None) -> float:
        from PySide6.QtCore import QPointF

        from tools.brand import gif

        image = gif.render(gif.logo_frame("seal", "dark", t), width, "#000000")
        y = (HEIGHT - image.height()) / 2 if top is None else top
        painter.drawImage(QPointF((WIDTH - image.width()) / 2, y), image)
        return y + image.height()

    def card(self, seconds: float, draw) -> None:
        from PySide6.QtGui import QPainter

        image = None
        for n in range(round(seconds * FPS)):
            image = self.canvas()
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw(painter, n / FPS)
            painter.end()
            self.save(image, n)
        self.finish(image)

    def scene(self, name: str, seconds: float, setup, update) -> None:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter

        setup()
        self.wait(900)
        frames = round(seconds * FPS)
        image = None
        for n in range(frames):
            update(n / max(frames - 1, 1))
            self.app.processEvents()
            self.window.view.render()
            self.app.processEvents()
            shot = self.window.grab().toImage()
            image = self.canvas()
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(QRectF(0, 0, WIDTH, HEIGHT), shot)
            self.caption(painter, CAPTIONS[name], ease(n / FADE) if n < FADE * 2 else 1.0)
            painter.end()
            self.save(image, n)
        self.finish(image)

    def end_card(self, painter, t: float) -> None:
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QColor

        bottom = self.seal(painter, 10.0, 460, top=210)
        painter.setOpacity(ease(t / 0.6))
        for text, colour, size, gap in ((TAGLINE, "#b4b4bc", 26, 40), (ADDRESS, "#6d98f2", 24, 96)):
            painter.setPen(QColor(colour))
            painter.setFont(self.font(size, 500))
            painter.drawText(QRectF(0, bottom + gap, WIDTH, 40), Qt.AlignmentFlag.AlignHCenter,
                             text)
        painter.setOpacity(1.0)

    def record(self) -> int:
        window, camera = self.window, self.camera
        seconds = dict(SCENES)
        self.card(seconds["intro"], lambda p, t: self.seal(p, t))

        def explore():
            window.workspaces.switch("Explore")
            window.view.reset_view()
            camera.Zoom(1.35)

        self.scene("explore", seconds["explore"], explore,
                   lambda f: (camera.Azimuth(0.9), camera.Zoom(1.0025)))

        def slices():
            window.workspaces.switch("Slices")
            window.state.set_slice("axial", -36.0)

        self.scene("slices", seconds["slices"], slices,
                   lambda f: window.state.set_slice("axial", -36.0 + 86.0 * ease(f)))
        steps = len(next(p for p in window.state.atlas.pathways if p.key == ROUTE).steps)

        def pathway():
            window.workspaces.switch("Pathways")
            window.info_group.show_page("slices")
            window.pathways.open(ROUTE)
            window.pathways.go(0)

        def walk(f):
            step = min(int(f * steps), steps - 1)
            if step != window.pathways.index:
                window.pathways.go(step)
            camera.Azimuth(0.35)

        self.scene("pathway", seconds["pathway"], pathway, walk)

        def lab():
            window.pathways.leave()
            window.workspaces.switch("Lab")
            window.lab.document.add_block(CHANGE, 120.0)
            window.lab.document.set_playhead(0.0)
            window.view.reset_view()
            camera.Zoom(1.5)

        self.scene("lab", seconds["lab"], lab,
                   lambda f: (window.lab.document.set_playhead(1380.0 * ease(f)),
                              camera.Azimuth(0.25)))
        self.card(seconds["end"], self.end_card)
        window.lab.document.undo.setClean()
        window.close()
        return self.count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.teaser",
                                     description="Record the README teaser from the real app "
                                                 "(needs a display and the built atlas)")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "teaser")
    args = parser.parse_args(argv)
    if shutil.which("ffmpeg") is None:
        print("ffmpeg is needed", file=sys.stderr)
        return 1
    frames = args.out / "frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    print(Recorder(frames).record(), "frames")
    for name, command in encode_commands(frames, args.out):
        subprocess.run(command, check=True)
        print(args.out / f"teaser.{name}")
    for name in ("teaser.avif", "teaser.webp"):
        shutil.copy(args.out / name, ROOT / "brand" / name)
        print(ROOT / "brand" / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
