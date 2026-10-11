from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

STARTED = time.perf_counter()
DEFAULT_ATLAS = Path(__file__).resolve().parent.parent / "atlases" / "cns"
DISCLAIMER_KEY = "disclaimer_shown"


def apply_dark_theme(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    app.setStyle("Fusion")
    p = QPalette()
    roles = QPalette.ColorRole
    for role, color in {
        roles.Window: "#16161d", roles.WindowText: "#d8d8e0", roles.Base: "#0f0f15",
        roles.AlternateBase: "#1c1c25", roles.Text: "#d8d8e0", roles.Button: "#22222c",
        roles.ButtonText: "#d8d8e0", roles.Highlight: "#3d6fd6", roles.HighlightedText: "#ffffff",
        roles.ToolTipBase: "#22222c", roles.ToolTipText: "#d8d8e0", roles.PlaceholderText: "#7a7a88",
    }.items():
        p.setColor(role, QColor(color))
    app.setPalette(p)


def disclaimer_due(settings) -> bool:
    return not settings.value(DISCLAIMER_KEY, False, type=bool)


def mark_disclaimer_shown(settings) -> None:
    settings.setValue(DISCLAIMER_KEY, True)
    settings.sync()


def run_benchmark(window, frames: int = 300) -> None:
    from PySide6.QtWidgets import QApplication

    view = window.view
    times = []
    t0 = time.perf_counter()
    for _ in range(frames):
        view.camera.azimuth += 1.2
        view.render()
        QApplication.processEvents()
        times.append(view.last_render_ms)
    wall = time.perf_counter() - t0
    times.sort()
    ids = window.state.geometry_ids
    tris = sum(len(window.state.atlas.mesh(i).faces) for i in ids)
    print(f"{len(ids)} structures, {tris:,} triangles, 3D view {view.width()}x{view.height()} px")
    print(f"{frames / wall:.0f} fps on screen | render median {times[len(times) // 2]:.2f} ms, "
          f"p95 {times[int(len(times) * 0.95)]:.2f} ms, max {times[-1]:.2f} ms "
          "(fps is capped by the display refresh rate when vsync is on)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNS Atlas desktop app")
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS, help="atlas package directory")
    parser.add_argument("--bench", action="store_true", help="measure on-screen fps, then exit")
    parser.add_argument("--first-frame", action="store_true",
                        help="print the time to the first frame, then exit")
    args = parser.parse_args(argv)

    from cns_atlas import Atlas, AtlasError

    try:
        atlas = Atlas.open(args.atlas)
    except AtlasError as exc:
        print(f"{exc}\nBuild the atlas first: python -m tools.build_atlas", file=sys.stderr)
        return 1

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("CNS Atlas")
    apply_dark_theme(app)

    from .main_window import MainWindow

    window = MainWindow(atlas)
    if args.bench:
        window.showFullScreen()
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            app.processEvents()
    else:
        window.show()
    app.processEvents()
    window.view.render()
    print(f"first frame: {time.perf_counter() - STARTED:.2f} s")
    if args.first_frame:
        window.close()
        return 0
    if args.bench:
        run_benchmark(window)
        window.close()
        return 0
    settings = QSettings("cns-atlas", "cns-atlas")
    if disclaimer_due(settings):
        window.show_disclaimer()
        mark_disclaimer_shown(settings)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
