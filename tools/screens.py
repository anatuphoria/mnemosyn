from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "brand"
WINDOW = (1600, 1000)
SETTLE_MS = 900
HOUR = 60.0
TERRITORY = "Middle cerebral artery frontal territory (left)"


def _id(window, name: str) -> int:
    found = next((s.id for s in window.state.atlas.structures if s.name == name), None)
    if found is None:
        raise KeyError(f"no structure named {name!r}")
    return found


def _action(window, text: str):
    from PySide6.QtGui import QAction

    return next(a for a in window.findChildren(QAction) if a.text() == text)


def slices(window) -> None:
    window.workspaces.switch("Slices")
    window.state.set_slice("axial", 0.0)
    window.state.select(_id(window, "Hippocampus (left)"))
    _action(window, "Centre slice").trigger()


def activity(window) -> None:
    window.workspaces.switch("Pathways")
    window.pathways.open("stress")
    window.pathways.go(2)


def _stalk_cut(window) -> None:
    window.workspaces.switch("Lab")
    window.lab.choose_system("stress")
    window.lab.document.add_block("stalk_cut", 2 * HOUR)
    window.lab.document.set_playhead(26 * HOUR)


def lab(window) -> None:
    _stalk_cut(window)


def circuit(window) -> None:
    _stalk_cut(window)
    _action(window, "Switch Brain and Circuit").trigger()


def lesion(window) -> None:
    window.workspaces.switch("Lesion")
    place = window.lesion.place
    place.set_side("left")
    place.choose_territory(window.state.atlas.get(_id(window, TERRITORY)).parent)


SCREENS: dict[str, Callable] = {
    "screenshot-slices": slices,
    "screenshot-activity": activity,
    "screenshot-lab": lab,
    "screenshot-circuit": circuit,
    "screenshot-lesion": lesion,
}


def take(atlas_path: Path, out: Path = OUT, names=None) -> list[Path]:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from cns_atlas import Atlas
    from cns_desktop.design.theme import apply_theme
    from cns_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    atlas = Atlas.open(atlas_path)
    taken = []
    with tempfile.TemporaryDirectory() as scratch:
        for name in names or SCREENS:
            settings = QSettings(str(Path(scratch) / f"{name}.ini"), QSettings.Format.IniFormat)
            window = MainWindow(atlas, progress_path=Path(scratch) / f"{name}.sqlite",
                                settings=settings)
            window.setWindowFlag(Qt.WindowType.X11BypassWindowManagerHint)
            window.setFixedSize(*WINDOW)
            window.show()
            QTest.qWait(SETTLE_MS)
            SCREENS[name](window)
            QTest.qWait(SETTLE_MS)
            window.view.render()
            QTest.qWait(SETTLE_MS)
            path = out / f"{name}.png"
            window.grab().save(str(path))
            taken.append(path)
            if hasattr(window, "lab"):
                window.lab.document.undo.setClean()
            window.close()
    return taken


def main(argv: list[str] | None = None) -> int:
    from cns_desktop.app import DEFAULT_ATLAS

    parser = argparse.ArgumentParser(prog="python -m tools.screens",
                                     description="Take the README and home page screenshots "
                                                 "from the real app (needs a display)")
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    for path in take(args.atlas, names=args.only):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
