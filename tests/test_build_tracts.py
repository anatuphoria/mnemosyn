import json

import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import AFFINE, SHAPE, build_extended_toy_atlas, write_extended_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import (LabelRef, RawStructure, build_tree, load_structures,
                                         with_xrefs)
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.tracts import place
from tools.build_atlas.validate import check_sources

RECIPE = """\
name = "t"
version = "0"
species = "Homo sapiens"
licence = "CC BY 4.0"
lod0_max_faces = 2000
lod_fractions = [1.0]
min_faces = 4
smoothing_iterations = 0
smoothing_pass_band = 0.1

[[volumes]]
name = "brain"
space = "MNI152"
grid_source = "lab"

[[sources]]
id = "lab"
title = "Labels"
authors = "A"
year = 2020
version = "1"
licence = "CC0"
redistribution = true
download = "file:///x/lab.nii.gz"
sha256 = "AA"
volume = "brain"
priority = 1
drop = [4]
mesh_grid = "native"

[[tracts]]
id = "fib"
title = "Fibres"
authors = "B"
year = 2021
version = "1"
licence = "CC BY-SA 4.0"
redistribution = true
download = "file:///x/{name}.nii.gz"
labels = "brain"
drop = ["Extra"]

[tracts.files]
Long_L = "BB"
Short = "CC"
Extra = "DD"
"""


def recipe(tmp_path, text=RECIPE):
    path = tmp_path / "recipe.toml"
    path.write_text(text)
    return load_recipe(path)


def raw(sid, refs, kind="tract"):
    return RawStructure(id=sid, parent=1, acronym=f"S{sid}", name=f"S{sid}", kind=kind,
                        side="midline", concept=None, color=None, synonyms=(), xrefs={},
                        sources=tuple(sorted({ref.source for ref in refs})), labels=tuple(refs))


GOOD = [raw(10, [LabelRef("fib", "Long_L")]), raw(11, [LabelRef("fib", "Short")]),
        raw(12, [LabelRef("lab", 1)], kind="nucleus")]


def test_recipe_reads_drops_native_meshing_and_tracts(tmp_path):
    loaded = recipe(tmp_path)
    assert loaded.sources[0].drop == (4,) and loaded.sources[0].mesh_grid == "native"
    tracts = loaded.tracts[0]
    assert tracts.names == ("Extra", "Long_L", "Short")
    assert tracts.drop == ("Extra",) and tracts.labels == "brain"
    spec = tracts.file_spec("Short")
    assert spec.download == "file:///x/Short.nii.gz" and spec.sha256 == "cc"
    assert spec.source.id == "fib" and spec.member == ""


def test_valid_sources_have_no_problems(tmp_path):
    assert check_sources(GOOD, recipe(tmp_path), tmp_path) == []


def test_every_tract_file_needs_a_structure_or_a_drop(tmp_path):
    problems = check_sources(GOOD[:1] + GOOD[2:], recipe(tmp_path), tmp_path)
    assert problems == ["tracts fib: file 'Short' has no structure and is not dropped"]


def test_unknown_drops_and_unknown_masks_are_reported(tmp_path):
    text = RECIPE.replace('drop = ["Extra"]', 'drop = ["Extra", "Ghost"]')
    problems = check_sources([*GOOD, raw(13, [LabelRef("fib", "Nope")])], recipe(tmp_path, text),
                             tmp_path)
    assert "tracts fib: dropped file 'Ghost' is not listed" in problems
    assert "structure 13: tracts fib has no file 'Nope'" in problems


def test_masks_and_label_numbers_must_match_their_source(tmp_path):
    wrong = [raw(13, [LabelRef("lab", "Long_L")]), raw(14, [LabelRef("fib", 3)])]
    problems = check_sources([*GOOD, *wrong], recipe(tmp_path), tmp_path)
    assert "structure 13: mask 'Long_L' needs a tracts source, not 'lab'" in problems
    assert "structure 14: tracts fib needs a file name, not 3" in problems


def test_tract_download_needs_a_name_slot_and_a_licence(tmp_path):
    text = (RECIPE.replace('file:///x/{name}.nii.gz', 'file:///x/all.nii.gz')
            .replace('licence = "CC BY-SA 4.0"\n', ""))
    problems = check_sources(GOOD, recipe(tmp_path, text), tmp_path)
    assert "tracts fib: download must contain {name}" in problems
    assert "tracts fib: licence is missing" in problems


def test_mesh_grid_and_drop_values_are_checked(tmp_path):
    text = RECIPE.replace('mesh_grid = "native"', 'mesh_grid = "fine"').replace(
        "drop = [4]", 'drop = ["four"]')
    problems = check_sources(GOOD, recipe(tmp_path, text), tmp_path)
    assert "source lab: mesh_grid must be one of ('label', 'native')" in problems
    assert "source lab: drop value 'four' is not a label number" in problems


def test_string_label_refs_load_and_become_xrefs(tmp_path):
    path = tmp_path / "structures.toml"
    path.write_text(
        'groups = [{ id = 1, acronym = "CNS", name = "CNS" }]\n'
        'concepts = [{ id = 10, parent = 1, acronym = "LT", name = "Long tract", kind = "tract",'
        ' source = "fib", left = "Long_L", right = "Long_R" }]\n')
    raws = load_structures(path)
    left = next(r for r in raws if r.id == 11)
    assert left.labels == (LabelRef("fib", "Long_L"),)
    planned = {p.structure.id: p.structure for p in with_xrefs(build_tree(raws), {})}
    assert planned[11].xrefs == {"fib": "Long_L"}


@pytest.fixture(scope="module")
def hyp_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    return Atlas.open(build_extended_toy_atlas(tmp_path_factory.mktemp("hyp"), tracts=False))


def test_native_labels_are_resampled_and_the_older_source_wins(hyp_atlas):
    data = np.asarray(hyp_atlas.volumes[0].data)
    assert data[12, 36, 20] == 101
    assert data[12, 39, 20] == 131
    assert data[28, 39, 20] == 132


def test_dropped_labels_leave_no_voxels(hyp_atlas):
    present = set(np.unique(np.asarray(hyp_atlas.volumes[0].data)).tolist())
    assert present <= {0, 101, 102, 111, 112, 120, 131, 132}


def test_a_nucleus_lost_at_label_resolution_keeps_its_native_shape(hyp_atlas):
    assert 140 not in np.unique(np.asarray(hyp_atlas.volumes[0].data))
    assert hyp_atlas.has_mesh(140) and hyp_atlas.has_mesh(131)
    report = (hyp_atlas.root / "build-report.md").read_text()
    assert "3D shape only, no voxels at label resolution: Tiny nucleus" in report
    assert "dropped from toyhyp: 4" in report


def test_native_meshes_follow_the_finer_grid(hyp_atlas):
    vertices = np.asarray(hyp_atlas.mesh(140).vertices, dtype=float)
    assert np.ptp(vertices, axis=0).max() < 3.0
    assert np.allclose(vertices.mean(axis=0), (2.0, -14.0, 22.0), atol=1.0)


def test_unknown_drop_values_and_unmapped_values_fail(tmp_path):
    pytest.importorskip("pyvista")
    src = write_extended_source_tree(tmp_path, tracts=False)
    recipe = src / "recipe.toml"
    recipe.write_text(recipe.read_text().replace("drop = [4]", "drop = [9]"))
    with pytest.raises(BuildError) as error:
        build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    text = str(error.value)
    assert "source toyhyp: label 4 has no structure" in text
    assert "source toyhyp: drop value 9 is not in the source" in text


def offset_image(mask, voxels=(1, 1, 1)):
    affine = AFFINE.copy()
    affine[:3, 3] += 4.0 * np.array(voxels)
    return nib.Nifti1Image(mask, affine)


def test_place_returns_sorted_flat_indices_on_the_label_grid():
    mask = np.zeros((3, 3, 3), dtype=np.uint8)
    mask[0, 0, 0] = mask[2, 1, 0] = 1
    expected = sorted(np.ravel_multi_index(([1, 3], [1, 2], [1, 1]), SHAPE).tolist())
    assert place(offset_image(mask), SHAPE, AFFINE, "t").tolist() == expected


def test_place_needs_a_whole_voxel_offset():
    image = nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8),
                            AFFINE + np.array([[0, 0, 0, 1.0]] + [[0, 0, 0, 0]] * 3))
    with pytest.raises(BuildError, match="whole-voxel offset"):
        place(image, SHAPE, AFFINE, "t")


def test_place_rejects_voxels_outside_the_grid():
    with pytest.raises(BuildError, match="outside the label grid"):
        place(offset_image(np.ones((2, 2, 2), dtype=np.uint8), (39, 0, 0)), SHAPE, AFFINE, "t")


def test_tract_layer_is_written_on_the_label_grid(toy_tract_atlas):
    folder = toy_tract_atlas / "tracts"
    assert np.load(folder / "ids.npy").tolist() == [151, 152, 160]
    assert np.load(folder / "offsets.npy").tolist() == [0, 384, 768, 840]
    voxels = np.load(folder / "voxels.npy")
    long_left = np.array(np.unravel_index(voxels[:384], SHAPE))
    assert long_left.min(axis=1).tolist() == [8, 12, 4]
    assert long_left.max(axis=1).tolist() == [11, 15, 27]
    assert np.all(np.diff(voxels[:384].astype(np.int64)) > 0)
    metadata = json.loads((toy_tract_atlas / "metadata.json").read_text())
    assert {"file": "tracts", "role": "tracts", "labels": "brain"} in metadata["volumes"]


def test_tracts_get_meshes_sources_xrefs_and_a_report(toy_tract_atlas):
    atlas = Atlas.open(toy_tract_atlas)
    assert all(atlas.has_mesh(i) for i in (151, 152, 160))
    assert atlas.get(151).xrefs == {"toytracts": "Long_Tract_L"}
    assert {"toytracts", "toyhyp"} <= set(atlas.sources)
    report = (toy_tract_atlas / "build-report.md").read_text()
    assert "- tracts: 3, voxels 840" in report
    assert "dropped from toytracts: Extra" in report


def test_builds_with_tracts_are_identical(tmp_path):
    pytest.importorskip("pyvista")
    src = write_extended_source_tree(tmp_path / "a", tracts=True)
    first = build(src, tmp_path / "one", cache=tmp_path / "cache", log=lambda *_: None)
    second = build(src, tmp_path / "two", cache=tmp_path / "cache", log=lambda *_: None)
    meshes = [f"meshes/{lod}/{part}.npy" for lod in ("lod0", "lod1", "lod2")
              for part in ("index", "vertices", "normals", "faces")]
    for name in ("tracts/ids.npy", "tracts/offsets.npy", "tracts/voxels.npy", *meshes,
                 "volumes/brain.nii.gz", "build-report.md"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_a_dropped_entry_cannot_also_be_mapped(tmp_path):
    both = [*GOOD, raw(13, [LabelRef("fib", "Extra")]),
            raw(14, [LabelRef("lab", 4)], kind="nucleus")]
    problems = check_sources(both, recipe(tmp_path), tmp_path)
    assert "tracts fib: file 'Extra' is both dropped and mapped" in problems
    assert "source lab: label 4 is both dropped and mapped" in problems


def test_the_report_counts_structures_per_source(toy_tract_atlas):
    report = (toy_tract_atlas / "build-report.md").read_text()
    for line in ("- source toy: 5 structures", "- source toyhyp: 3 structures",
                 "- source toytracts: 3 structures"):
        assert line in report


def test_relabel_does_not_widen_integer_labels():
    import tracemalloc

    from tools.build_atlas.labels import relabel

    data = np.zeros((128, 128, 64), dtype=np.int32)
    data[10:20, 10:20, 10:20] = 7
    image = nib.Nifti1Image(data, np.eye(4))
    tracemalloc.start()
    out = relabel(image, {7: 300})
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert out[15, 15, 15] == 300 and out[0, 0, 0] == 0 and out.dtype == np.uint16
    assert peak < 2.5 * data.nbytes
