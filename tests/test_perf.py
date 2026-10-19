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
from timing_baseline import best_of

pytestmark = pytest.mark.perf
REAL_ATLAS = Path(__file__).resolve().parent.parent / "atlases" / "cns"
GREY = (170, 170, 180)
ONCE_RUNS = 7


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


def run_timing(script: str, atlas_path, tmp_path, runs: int = 3) -> list[float]:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    rows = []
    for run in range(runs):
        result = subprocess.run([sys.executable, "-c", script, str(atlas_path),
                                 str(tmp_path / f"progress{run}.sqlite")], env=env, check=True,
                                capture_output=True, text=True, timeout=600)
        rows.append([float(v) for v in result.stdout.split("\n")[-2].split()])
    return [sorted(column)[len(column) // 2] for column in zip(*rows)]


PRELUDE = """
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
deadline = time.perf_counter() + 10
while not getattr(window, "warm_up_done", True) and time.perf_counter() < deadline:
    app.processEvents()
app.processEvents()
window.view.ren_win.WaitForCompletion()
state, view = window.state, window.view


def timed(action):
    start = time.perf_counter()
    action()
    app.processEvents()
    view.ren_win.WaitForCompletion()
    return time.perf_counter() - start


def median(values):
    return sorted(values)[len(values) // 2]
"""


@pytest.fixture(scope="module")
def large_atlas(tmp_path_factory):
    structures = large_structures()
    meshes = {s.id: tetra(float(i)) for i, s in enumerate(structures) if s.kind != "group"}
    return write_package(tmp_path_factory.mktemp("large") / "pkg", structures, meshes=meshes,
                         lods=("lod0", "lod1", "lod2"))


def test_open_5000_structures_under_200ms(large_atlas, timing):
    assert len(Atlas.open(large_atlas).structures) == 5001
    timing.assert_within({"open 5000 structures": (best_of(lambda: Atlas.open(large_atlas)),
                                                   0.200)})


@pytest.mark.parametrize("query", ["r", "region 4", "syn 4999", "group 7", "label_3000", "zzz"])
def test_search_5000_structures_under_10ms(large_atlas, query, timing):
    atlas = Atlas.open(large_atlas)
    timing.assert_within({f"search {query!r}": (best_of(lambda: atlas.search(query)), 0.010)})


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
def test_desktop_first_frame_under_2s_and_own_memory_under_400mb(timing):
    pytest.importorskip("pyvistaqt")
    real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUNBUFFERED": "1"}
    runs, output = [], ""
    for _ in range(3):
        start = time.perf_counter()
        app = subprocess.Popen([sys.executable, "-m", "cns_desktop", "--first-frame"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        output = app.stdout.readline()
        runs.append(time.perf_counter() - start)
        output += app.stdout.read()
        assert app.wait(timeout=120) == 0 and output.startswith("first frame:")
    timing.assert_within({"first frame": (sorted(runs)[1], 2.0)})
    own = [line for line in output.splitlines() if line.startswith("own memory:")]
    assert own and float(own[0].split()[2]) < 400
    warmed = [line for line in output.splitlines()
              if line.startswith("own memory after warm-up:")]
    assert warmed and float(warmed[0].split()[4]) < 400


SELECTION_TIMING = PRELUDE + """
def split(structure_id):
    start = time.perf_counter()
    state.select(structure_id)
    step = time.perf_counter() - start
    app.processEvents()
    view.ren_win.WaitForCompletion()
    return step, time.perf_counter() - start


singles = [split(i) for i in list(state.geometry_ids)[:60]]
groups = []
for group in (1, 2, 3, 70, 80):
    split(1000)
    split(group)
    runs = [split(i) for i in (1000, group) * 7][1::2]
    groups += [median([r[0] for r in runs]), median([r[1] for r in runs])]
window.close()
print(median([s[0] for s in singles]), median([s[1] for s in singles]), *groups)
"""


@pytest.mark.slow
def test_selection_on_the_real_atlas_under_7ms(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    values = run_timing(SELECTION_TIMING, real_atlas_or_skip(), tmp_path)
    single_step, single_whole, *groups = values
    cns, brain, cord, tracts, spinal_tracts = zip(groups[0::2], groups[1::2])
    timings = {"select a structure": (single_step, 0.007),
               "select a structure with its redraw": (single_whole, 0.016),
               "select Tracts with its redraw": (tracts[1], 0.040),
               "select spinal tracts with its redraw": (spinal_tracts[1], 0.050)}
    for name, (step, whole) in (("CNS", cns), ("Brain", brain), ("Spinal cord", cord)):
        timings[f"select {name}"] = (step, 0.010)
        timings[f"select {name} with its redraw"] = (whole, 0.020)
    timing.assert_within(timings)


@pytest.mark.slow
def test_real_atlas_quiz_levels():
    from cns_study.items import group_items, structure_items

    atlas = Atlas.open(real_atlas_or_skip())
    groups = {item.name for item in group_items(atlas)}
    assert {"Thalamus", "Frontal lobe", "Vermis", "Hypothalamus", "Diencephalon", "Pons"} <= groups
    assert not {"Central nervous system", "Tracts"} & groups
    assert len(structure_items(atlas)) > 80


@pytest.mark.slow
def test_answer_check_on_the_real_atlas_under_1ms(timing):
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
    timing.assert_within({"check a typed answer": (times[len(times) // 2], 0.001)})


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
deadline = time.perf_counter() + 10
while not getattr(window, "warm_up_done", True) and time.perf_counter() < deadline:
    app.processEvents()
app.processEvents()
window.view.ren_win.WaitForCompletion()
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
def test_quiz_on_the_real_atlas_starts_under_100ms_and_moves_on_under_50ms(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    started, moved_on = run_timing(QUIZ_TIMING, atlas_path, tmp_path, runs=ONCE_RUNS)
    timing.assert_within({"start a quiz": (started, 0.100), "move on in a quiz": (moved_on, 0.050)})


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
deadline = time.perf_counter() + 10
while not getattr(window, "warm_up_done", True) and time.perf_counter() < deadline:
    app.processEvents()
app.processEvents()
window.view.ren_win.WaitForCompletion()
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
def test_tracts_on_the_real_atlas_meet_their_budgets(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    first, toggle, redraw, lookup = run_timing(TRACT_TIMING, atlas_path, tmp_path,
                                               runs=ONCE_RUNS)
    timing.assert_within({"show tracts the first time": (first, 0.500),
                          "show or hide tracts": (toggle, 0.050),
                          "redraw a slice with tracts": (redraw, 0.010),
                          "look up a tract in a slice": (lookup, 0.001)})


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
deadline = time.perf_counter() + 10
while not getattr(window, "warm_up_done", True) and time.perf_counter() < deadline:
    app.processEvents()
app.processEvents()
window.view.ren_win.WaitForCompletion()
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
def test_pathways_on_the_real_atlas_meet_their_budgets(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    entered, switched, step, tick = run_timing(PATHWAY_TIMING, atlas_path, tmp_path,
                                               runs=ONCE_RUNS)
    timing.assert_within({"enter a pathway": (entered, 0.100),
                          "switch a pathway's side": (switched, 0.100),
                          "cerebellar pathway step, 90th percentile": (step, 0.030),
                          "timeline tick": (tick, 0.005)})


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
def test_generated_3500_structure_scene_at_60_fps(tmp_path, timing):
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
        view.ren_win.WaitForCompletion()
    frame = (time.perf_counter() - start) / 30
    view.close()
    timing.assert_within({"frame of a 3,500-structure scene": (frame, 1 / 60)})


ROUTE_TIMING = PRELUDE + """
panel = window.pathways
window.pathway_dock.raise_()
app.processEvents()
panel.open("motor")
app.processEvents()
for index in range(len(panel.lights) - 1):
    panel.go(index)
    app.processEvents()
first_cord = timed(lambda: panel.go(len(panel.lights) - 1))
window.leave_pathway()
steps = []
for pathway in state.atlas.pathways:
    for side in (("left", "right") if pathway.sides == "one" else ("left",)):
        panel.open(pathway.key)
        panel.set_side(side)
        app.processEvents()
        steps += [timed(lambda index=index: panel.go(index)) for index in range(len(panel.lights))]
        window.leave_pathway()
        app.processEvents()
window.close()
print(first_cord, sorted(steps)[int(len(steps) * 0.9)])
"""


@pytest.mark.slow
def test_every_route_step_meets_30ms_including_the_first_into_the_cord(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    first_cord, step90 = run_timing(ROUTE_TIMING, real_atlas_or_skip(), tmp_path)
    timing.assert_within({"first route step into the cord": (first_cord, 0.030),
                          "route step, 90th percentile": (step90, 0.030)})


GROUP_TIMING = PRELUDE + """
cns = timed(lambda: state.select(1))
timed(lambda: state.select(1000))
brain = timed(lambda: state.select(2))
timed(lambda: state.select(1000))
cord = timed(lambda: state.select(3))
window.close()
print(cns, brain, cord)
"""


@pytest.mark.slow
def test_first_large_group_selections_meet_20ms_after_warm_up(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    values = run_timing(GROUP_TIMING, real_atlas_or_skip(), tmp_path, runs=ONCE_RUNS)
    timing.assert_within({f"first selection of {name}": (value, 0.020)
                          for name, value in zip(("CNS", "Brain", "Spinal cord"), values)})


VISIBILITY_TIMING = PRELUDE + """
worst = []
for group in (2, 3, 70, 30):
    ids = state.geometry_in(group)
    hides, shows, isolates = [], [], []
    for _ in range(7):
        hides.append(timed(lambda: state.set_hidden(ids, True)))
        shows.append(timed(lambda: state.set_hidden(ids, False)))
        isolates.append(timed(lambda: state.isolate(group)))
        timed(state.show_all)
    worst += [median(hides), median(shows), median(isolates)]
window.close()
print(*worst)
"""


@pytest.mark.slow
def test_hiding_showing_and_isolating_groups_meet_30ms(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    values = iter(run_timing(VISIBILITY_TIMING, atlas_path, tmp_path))
    names = {s.id: s.name for s in Atlas.open(atlas_path).structures}
    timing.assert_within({f"{action} {names[group]}": (next(values), 0.030)
                          for group in (2, 3, 70, 30) for action in ("hide", "show", "isolate")})


SLIDER_TIMING = PRELUDE + """
results = []
for volume in [v.name for v in state.atlas.volumes]:
    state.set_slice_volume(volume)
    state.set_slice("axial", state.slice_mm)
    app.processEvents()
    results.append(median([timed(lambda: state.set_slice("axial", state.slice_mm + 1.0))
                           for _ in range(15)]))
    panel = window.slices
    rows, cols = panel.layer.shape[:2]
    results.append(median([timed(lambda k=k: panel.wheel_zoom(1 if k % 2 else -1, rows / 2,
                                                             cols / 2)) for k in range(1, 16)]))
    results.append(median([timed(lambda k=k: panel.pan_by(1.0 if k % 2 else -1.0, 1.0))
                           for k in range(15)]))
    panel.fit_volume()
window.close()
print(*results)
"""


@pytest.mark.slow
def test_one_slider_step_meets_16ms(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    atlas_path = real_atlas_or_skip()
    values = iter(run_timing(SLIDER_TIMING, atlas_path, tmp_path))
    timing.assert_within({f"{action} step, {volume.name}": (next(values), 0.016)
                          for volume in Atlas.open(atlas_path).volumes
                          for action in ("slider", "zoom", "pan")})


TRACTS_GROUP_TIMING = PRELUDE + """
state.select(70)
app.processEvents()
times = []
for _ in range(7):
    timed(lambda: state.select(1000))
    times.append(timed(lambda: state.select(70)))
window.close()
print(median(times))
"""


@pytest.mark.slow
def test_tracts_group_selection_meets_40ms(tmp_path, timing):
    pytest.importorskip("pyvistaqt")
    value = run_timing(TRACTS_GROUP_TIMING, real_atlas_or_skip(), tmp_path)[0]
    timing.assert_within({"select Tracts after warm-up": (value, 0.040)})
