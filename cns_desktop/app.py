from __future__ import annotations

import argparse
import sys
import time


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
    n = len(window.state.atlas.structures)
    tris = sum(s.mesh.n_cells for s in window.state.atlas.structures.values())
    print(f"{n} structures, {tris:,} triangles, 3D view {view.width()}x{view.height()} px")
    print(f"{frames / wall:.0f} fps on screen | render median {times[len(times) // 2]:.2f} ms, "
          f"p95 {times[int(len(times) * 0.95)]:.2f} ms, max {times[-1]:.2f} ms "
          "(fps is capped by the display refresh rate when vsync is on)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNS Atlas desktop prototype")
    parser.add_argument("--manifest", help="atlas manifest (default: bundled AAL116)")
    parser.add_argument("--knowledge", help="knowledge JSON (default: data/knowledge.json)")
    parser.add_argument("--bench", action="store_true", help="measure on-screen fps, then exit")
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setApplicationName("CNS Atlas")
    apply_dark_theme(app)

    t0 = time.perf_counter()
    from .atlas_data import load_atlas
    from .main_window import MainWindow

    window = MainWindow(load_atlas(args.manifest), args.knowledge)
    if args.bench:
        window.showFullScreen()
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            app.processEvents()
    else:
        window.show()
    app.processEvents()
    print(f"startup: {time.perf_counter() - t0:.2f} s (imports + atlas + window)")
    if args.bench:
        run_benchmark(window)
        window.close()
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
