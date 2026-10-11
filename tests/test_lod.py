from atlas_package import tetra, tiny_structures, write_package
from cns_atlas import Atlas
from cns_desktop.lod import DEFAULT_FACE_BUDGET, choose_lod, face_totals


def test_choose_lod_picks_the_finest_level_within_budget():
    assert DEFAULT_FACE_BUDGET == 3_000_000
    assert choose_lod([1_000, 500, 100], budget=2_000) == 0
    assert choose_lod([5_000, 1_500, 300], budget=2_000) == 1
    assert choose_lod([9_000, 8_000, 7_000], budget=2_000) == 2


def test_face_totals_per_level(tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra(0), 102: tetra(1)},
                         lods=("lod0", "lod1", "lod2"))
    assert face_totals(Atlas.open(root), [101, 102]) == [8, 8, 8]
