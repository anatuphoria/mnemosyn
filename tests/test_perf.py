import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from atlas_package import tetra, write_package
from cns_atlas import Atlas
from cns_atlas.meshes import MeshData
from cns_atlas.model import Structure

pytestmark = pytest.mark.perf
REAL_ATLAS = Path(__file__).resolve().parent.parent / "atlases" / "cns"
GREY = (170, 170, 180)


def large_structures(groups: int = 50, per_group: int = 99) -> list[Structure]:
    out = [Structure(1, "ROOT", "Root", (1,), GREY, kind="group")]
    next_id = 1000
    for g in range(groups):
        group_id = 2 + g
        out.append(Structure(group_id, f"G{g}", f"Group {g}", (1, group_id), GREY, kind="group"))
        for _ in range(per_group):
            out.append(Structure(next_id, f"R{next_id}", f"Region {next_id} of group {g}",
                                 (1, group_id, next_id), GREY, synonyms=(f"syn {next_id}",),
                                 xrefs={"src": f"Label_{next_id}"}, sources=("src",)))
            next_id += 1
    return out


def best_of(fn, runs: int = 5) -> float:
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


@pytest.fixture(scope="module")
def large_atlas(tmp_path_factory):
    structures = large_structures()
    meshes = {s.id: tetra(float(i)) for i, s in enumerate(structures) if s.kind != "group"}
    return write_package(tmp_path_factory.mktemp("large") / "pkg", structures, meshes=meshes,
                         lods=("lod0", "lod1", "lod2"))


def test_open_5000_structures_under_200ms(large_atlas):
    assert len(Atlas.open(large_atlas).structures) == 5001
    assert best_of(lambda: Atlas.open(large_atlas)) < 0.200


@pytest.mark.parametrize("query", ["r", "region 4", "syn 4999", "group 7", "label_3000", "zzz"])
def test_search_5000_structures_under_10ms(large_atlas, query):
    atlas = Atlas.open(large_atlas)
    assert best_of(lambda: atlas.search(query)) < 0.010


def real_atlas_or_skip() -> Path:
    if not (REAL_ATLAS / "structures.json").exists():
        pytest.skip("real atlas not built; run python -m tools.build_atlas")
    return REAL_ATLAS


@pytest.mark.slow
def test_real_atlas_memory_under_500mb():
    atlas_path = real_atlas_or_skip()
    code = (
        "import numpy as np\n"
        "from cns_atlas import Atlas\n"
        f"atlas = Atlas.open({str(atlas_path)!r})\n"
        "for s in atlas.structures:\n"
        "    for lod in (0, 1, 2):\n"
        "        m = atlas.mesh(s.id, lod)\n"
        "        if m is not None:\n"
        "            np.asarray(m.vertices).sum()\n"
        "            np.asarray(m.faces).sum()\n"
        "atlas.volumes[0].data.sum()\n"
        "peak = [l for l in open('/proc/self/status') if l.startswith('VmHWM')][0]\n"
        "print(peak.split()[1])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            check=True)
    assert int(result.stdout.strip()) < 500 * 1024


@pytest.mark.slow
def test_desktop_first_frame_under_2s_and_own_memory_under_400mb():
    pytest.importorskip("pyvistaqt")
    real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    runs, output = [], ""
    for _ in range(2):
        start = time.perf_counter()
        result = subprocess.run([sys.executable, "-m", "cns_desktop", "--first-frame"], env=env,
                                check=True, capture_output=True, text=True, timeout=120)
        runs.append(time.perf_counter() - start)
        output = result.stdout
    assert runs[-1] < 2.0
    own = [line for line in output.splitlines() if line.startswith("own memory:")]
    assert own and float(own[0].split()[2]) < 400


@pytest.mark.slow
def test_selection_on_the_real_atlas_under_7ms(tmp_path):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    from PySide6.QtWidgets import QApplication

    from cns_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(Atlas.open(atlas_path), progress_path=tmp_path / "progress.sqlite")
    window.resize(1500, 900)
    window.show()
    app.processEvents()
    window.view.render()
    def timed(structure_id):
        start = time.perf_counter()
        window.state.select(structure_id)
        step = time.perf_counter() - start
        app.processEvents()
        window.view.ren_win.WaitForCompletion()
        return step, time.perf_counter() - start

    def median(values):
        return sorted(values)[len(values) // 2]

    singles = [timed(i) for i in list(window.state.geometry_ids)[:60]]
    groups = {}
    for group in (1, 2, 3, 70, 80):
        if group in window.state.atlas:
            timed(1000)
            timed(group)
            runs = [timed(i) for i in (1000, group, 1000, group, 1000, group)][1::2]
            groups[group] = (median([r[0] for r in runs]), median([r[1] for r in runs]))
    window.close()
    assert median([s[0] for s in singles]) < 0.007
    assert median([s[1] for s in singles]) < 0.016
    tract_groups = {70, 80}
    assert all(step < 0.010 and whole < 0.020 for g, (step, whole) in groups.items()
               if g not in tract_groups), groups
    assert all(whole < 0.050 for g, (_, whole) in groups.items() if g in tract_groups), groups


@pytest.mark.slow
def test_real_atlas_quiz_levels():
    from cns_study.items import group_items, structure_items

    atlas = Atlas.open(real_atlas_or_skip())
    groups = {item.name for item in group_items(atlas)}
    assert {"Thalamus", "Frontal lobe", "Vermis", "Hypothalamus", "Diencephalon", "Pons"} <= groups
    assert not {"Central nervous system", "Tracts"} & groups
    assert len(structure_items(atlas)) > 80


@pytest.mark.slow
def test_answer_check_on_the_real_atlas_under_1ms():
    from cns_study.answers import AnswerIndex
    from cns_study.items import group_items, structure_items

    atlas = Atlas.open(real_atlas_or_skip())
    pool = structure_items(atlas) + group_items(atlas)
    index = AnswerIndex(pool)
    target = next(item for item in pool if item.name == "Middle temporal gyrus")
    assert index.check("midle temporal gyrus", target).correct
    times = []
    for _ in range(50):
        start = time.perf_counter()
        index.check("midle temporal gyrus", target)
        times.append(time.perf_counter() - start)
    times.sort()
    assert times[len(times) // 2] < 0.001


QUIZ_TIMING = """
import sys
import time
from pathlib import Path

from fsrs import Rating
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_study.session import QuizChoice

app = QApplication([])
window = MainWindow(Atlas.open(sys.argv[1]), progress_path=Path(sys.argv[2]))
window.resize(1500, 900)
window.show()
app.processEvents()
window.view.render()
window.slices.label_centres()
window.progress_store()
start = time.perf_counter()
window.start_quiz(QuizChoice("name-typed", "structures", None, False))
app.processEvents()
started = time.perf_counter() - start
quiz = window.quiz
times = []
for _ in range(20):
    quiz.submit_text(quiz.item.name)
    start = time.perf_counter()
    quiz.go_on(Rating.Easy)
    app.processEvents()
    times.append(time.perf_counter() - start)
window.close()
times.sort()
print(started, times[len(times) // 2])
"""


@pytest.mark.slow
def test_quiz_on_the_real_atlas_starts_under_100ms_and_moves_on_under_50ms(tmp_path):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run([sys.executable, "-c", QUIZ_TIMING, str(atlas_path),
                             str(tmp_path / "progress.sqlite")], env=env, check=True,
                            capture_output=True, text=True, timeout=120)
    started, moved_on = map(float, result.stdout.split()[-2:])
    assert started < 0.100
    assert moved_on < 0.050


TRACT_TIMING = """
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow

app = QApplication([])
window = MainWindow(Atlas.open(sys.argv[1]), progress_path=Path(sys.argv[2]))
window.resize(1500, 900)
window.show()
app.processEvents()
window.view.render()
toggle = window.shortcuts["Tracts"]
start = time.perf_counter()
toggle.trigger()
app.processEvents()
first = time.perf_counter() - start
toggles = []
for _ in range(6):
    start = time.perf_counter()
    toggle.trigger()
    app.processEvents()
    toggles.append(time.perf_counter() - start)
window.state.set_slice("axial", 0.0)
redraws = []
for _ in range(10):
    start = time.perf_counter()
    window.slices.redraw()
    redraws.append(time.perf_counter() - start)
lookups = []
for row in range(40, 180, 10):
    start = time.perf_counter()
    window.slices.structure_at_pixel(row, 90)
    lookups.append(time.perf_counter() - start)
window.close()
median = lambda values: sorted(values)[len(values) // 2]
print(first, median(toggles), median(redraws), median(lookups))
"""


@pytest.mark.slow
def test_tracts_on_the_real_atlas_meet_their_budgets(tmp_path):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run([sys.executable, "-c", TRACT_TIMING, str(atlas_path),
                             str(tmp_path / "progress.sqlite")], env=env, check=True,
                            capture_output=True, text=True, timeout=180)
    first, toggle, redraw, lookup = map(float, result.stdout.split()[-4:])
    assert first < 0.500
    assert toggle < 0.050
    assert redraw < 0.010
    assert lookup < 0.001


PATHWAY_TIMING = """
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow

app = QApplication([])
window = MainWindow(Atlas.open(sys.argv[1]), progress_path=Path(sys.argv[2]))
window.resize(1500, 900)
window.show()
app.processEvents()
window.view.render()
window.pathway_dock.raise_()
app.processEvents()
panel = window.pathways
start = time.perf_counter()
panel.open("cerebellar")
app.processEvents()
entered = time.perf_counter() - start
start = time.perf_counter()
panel.set_side("right")
app.processEvents()
switched = time.perf_counter() - start
stations = [n for n, ids in enumerate(panel.lights) if ids]
steps = []
for index in stations + stations:
    start = time.perf_counter()
    panel.go(index)
    app.processEvents()
    steps.append(time.perf_counter() - start)
panel.open("stress")
panel.play()
ticks = []
for _ in range(40):
    start = time.perf_counter()
    panel.advance(0.05)
    app.processEvents()
    ticks.append(time.perf_counter() - start)
panel.pause()
window.close()
print(entered, switched, sorted(steps)[int(len(steps) * 0.9)], sorted(ticks)[len(ticks) // 2])
"""


@pytest.mark.slow
def test_pathways_on_the_real_atlas_meet_their_budgets(tmp_path):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run([sys.executable, "-c", PATHWAY_TIMING, str(atlas_path),
                             str(tmp_path / "progress.sqlite")], env=env, check=True,
                            capture_output=True, text=True, timeout=180)
    entered, switched, step, tick = map(float, result.stdout.split()[-4:])
    assert entered < 0.130
    assert switched < 0.130
    assert step < 0.030
    assert tick < 0.005


def sphere_scene(count: int):
    import pyvista as pv

    structures = [Structure(1, "ROOT", "Root", (1,), GREY, kind="group")]
    levels = {"lod0": {}, "lod1": {}, "lod2": {}}
    side = int(np.ceil(count ** (1 / 3)))
    for k in range(count):
        structure_id = 1000 + k
        structures.append(Structure(structure_id, f"S{k}", f"Sphere {k}", (1, structure_id), GREY))
        centre = 10.0 * np.array([k % side, (k // side) % side, k // (side * side)])
        for name, resolution in (("lod0", 40), ("lod1", 20), ("lod2", 10)):
            sphere = pv.Sphere(radius=4.0, center=centre, theta_resolution=resolution,
                               phi_resolution=resolution).compute_normals()
            levels[name][structure_id] = MeshData(
                np.asarray(sphere.points, dtype=np.float32),
                np.asarray(sphere.point_data["Normals"], dtype=np.float16),
                np.asarray(sphere.regular_faces, dtype=np.uint32))
    return structures, levels


@pytest.mark.slow
def test_generated_3500_structure_scene_at_60_fps(tmp_path):
    pytest.importorskip("pyvistaqt")
    from PySide6.QtWidgets import QApplication

    from cns_desktop.state import AppState
    from cns_desktop.views.brain_view import BrainView

    structures, levels = sphere_scene(3500)
    root = write_package(tmp_path / "pkg", structures, meshes_by_lod=levels)
    app = QApplication.instance() or QApplication([])
    view = BrainView(AppState(Atlas.open(root)))
    view.resize(1400, 850)
    view.show()
    app.processEvents()
    assert view.lod == 1
    view.render()
    start = time.perf_counter()
    for _ in range(30):
        view.camera.Azimuth(3)
        view.render()
        view.screenshot(return_img=True)
    fps = 30 / (time.perf_counter() - start)
    view.close()
    assert fps >= 60
