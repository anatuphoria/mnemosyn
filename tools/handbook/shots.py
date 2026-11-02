from __future__ import annotations

import random
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

from tools.handbook.experiments import FILES, ROOT

SHOTS_DIR = ROOT / "site" / "handbook" / "shots"
SIZE = (1440, 900)
SETTLE_MS = 600
HOUR = 60.0
REVIEWED = 40


def _id(window, name: str) -> int:
    found = next((s.id for s in window.state.atlas.structures if s.name == name), None)
    if found is None:
        raise KeyError(f"no structure named {name!r}")
    return found


def _workspace(window, name: str) -> None:
    window.workspaces.switch(name)


def explore(window):
    _workspace(window, "Explore")
    window.state.select(_id(window, "Precentral gyrus (left)"))


def explore_isolate(window):
    _workspace(window, "Explore")
    window.state.select(_id(window, "Basal nuclei"))
    window.state.isolate(_id(window, "Basal nuclei"))
    window.frame()


def slices(window):
    _workspace(window, "Slices")
    window.state.select(_id(window, "Thalamus"))
    window.state.set_slice("coronal", -18.0)


def pathways(window):
    _workspace(window, "Pathways")


def pathways_route(window):
    _workspace(window, "Pathways")
    window.pathways.open("motor")
    window.pathways.go(2)


def quizzes(window):
    from cns_study.session import QuizChoice

    _workspace(window, "Explore")
    window.start_quiz(QuizChoice("name-choice", "structures", None, True), rng=random.Random(3))


def progress(window):
    from datetime import UTC, datetime, timedelta

    from fsrs import Card, Rating, Scheduler

    from cns_study.items import items

    store = window.progress_store()
    scheduler = Scheduler()
    now = datetime.now(UTC)
    ratings = (Rating.Good, Rating.Easy, Rating.Hard, Rating.Again)
    pool = items(window.state.atlas, "structures")
    for n, item in enumerate(pool[:REVIEWED]):
        for mode in ("name-typed", "find"):
            when = now - timedelta(days=n % 9)
            card, _log = scheduler.review_card(Card(), ratings[n % 4], when)
            store.record(item.id, mode, card, ratings[n % 4], n % 4 != 3, 4000, when)
    return window.show_progress()


def _lab(window, system: str) -> None:
    _workspace(window, "Lab")
    window.lab.choose_system(system)


def _lab_file(window, slug: str, file: str, playhead: float) -> None:
    _workspace(window, "Lab")
    window.lab.open(FILES / slug / file)
    window.lab.document.set_playhead(playhead)


def lab(window):
    _lab(window, "stress")
    window.lab.document.add_block("stalk_cut", 2 * HOUR)
    window.lab.document.set_playhead(26 * HOUR)


def lab_stress(window):
    _lab(window, "stress")
    window.lab.document.add_block("short_stressor", 6 * HOUR)
    window.lab.document.set_playhead(7 * HOUR)


def lab_water(window):
    _lab(window, "water")
    window.lab.document.add_block("stop_drinking", HOUR)
    window.lab.document.set_playhead(9 * HOUR)


def lesion(window):
    _workspace(window, "Lesion")


def lesion_territory(window):
    _workspace(window, "Lesion")
    place = window.lesion.place
    place.set_side("left")
    territory = _id(window, "Middle cerebral artery frontal territory (left)")
    concept = window.state.atlas.get(territory).parent
    place.choose_territory(concept)


SHOTS: dict[str, Callable] = {
    "explore": explore,
    "explore-isolate": explore_isolate,
    "slices": slices,
    "pathways": pathways,
    "pathways-route": pathways_route,
    "quizzes": quizzes,
    "progress": progress,
    "lab": lab,
    "lab-stress": lab_stress,
    "lab-water": lab_water,
    "lesion": lesion,
    "lesion-territory": lesion_territory,
    "exp-central-or-nephrogenic": lambda w: _lab_file(
        w, "central-or-nephrogenic", "central.mnemolab", 18 * HOUR),
    "exp-a-night-without-water": lambda w: _lab_file(
        w, "a-night-without-water", "healthy.mnemolab", 8 * HOUR),
    "exp-two-kinds-of-low-sodium": lambda w: _lab_file(
        w, "two-kinds-of-low-sodium", "siadh.mnemolab", 4 * 24 * HOUR),
    "exp-dexamethasone-tests": lambda w: _lab_file(
        w, "dexamethasone-tests", "cushing-disease.mnemolab", 48 * HOUR),
    "exp-addisons-disease": lambda w: _lab_file(
        w, "addisons-disease", "addison.mnemolab", 24 * HOUR),
    "exp-stopping-a-steroid-course": lambda w: _lab_file(
        w, "stopping-a-steroid-course", "course.mnemolab", 30 * 24 * HOUR),
}


def _check_shareable(atlas_path: Path):
    from cns_atlas import Atlas

    atlas = Atlas.open(atlas_path)
    if atlas.local_only:
        raise ValueError("screenshots need a shareable atlas, not a local build")
    return atlas


def take(atlas_path: Path, out: Path = SHOTS_DIR, names: Iterable[str] | None = None
         ) -> list[Path]:
    atlas = _check_shareable(Path(atlas_path))
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from cns_desktop.design.theme import apply_theme
    from cns_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    out.mkdir(parents=True, exist_ok=True)
    taken = []
    with tempfile.TemporaryDirectory() as scratch:
        for name in names or SHOTS:
            settings = QSettings(str(Path(scratch) / f"{name}.ini"), QSettings.Format.IniFormat)
            window = MainWindow(atlas, progress_path=Path(scratch) / f"{name}.sqlite",
                                settings=settings)
            window.setWindowFlag(Qt.WindowType.X11BypassWindowManagerHint)
            window.resize(*SIZE)
            window.show()
            QTest.qWait(SETTLE_MS)
            target = SHOTS[name](window) or window
            if target is not window:
                target.setWindowFlag(Qt.WindowType.X11BypassWindowManagerHint)
            target.show()
            QTest.qWait(SETTLE_MS)
            window.view.render()
            QTest.qWait(SETTLE_MS)
            path = out / f"{name}.png"
            target.grab().save(str(path))
            taken.append(path)
            if target is not window:
                target.close()
            window.close()
    return taken
