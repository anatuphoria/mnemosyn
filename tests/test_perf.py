import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from atlas_package import tetra, write_package
from cns_atlas import Atlas
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
def test_desktop_first_frame_under_2s():
    pytest.importorskip("pyvistaqt")
    real_atlas_or_skip()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    runs = []
    for _ in range(2):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-m", "cns_desktop", "--first-frame"], env=env,
                       check=True, capture_output=True, timeout=120)
        runs.append(time.perf_counter() - start)
    assert runs[-1] < 2.0
