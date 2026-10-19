import dataclasses
import json
import zipfile

import nibabel as nib
import numpy as np
import pytest

from atlas_fixtures import SPINE_AFFINE, sha256_file, spine_volume, write_extended_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import load_structures
from tools.build_atlas.labels import load_label_image, load_members
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import check_sources, check_templates


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def edit(path, old, new):
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))


def spec_of(src, name):
    return next(s for s in load_recipe(src / "recipe.toml").sources if s.source.id == name)


def test_a_mask_threshold_keeps_values_at_or_above_it(tmp_path):
    path = tmp_path / "p.nii.gz"
    nib.save(nib.Nifti1Image(np.array([[[0.2, 0.6], [0.5, 0.0]]], dtype=np.float32), np.eye(4)),
             path)
    data = np.asarray(load_label_image(path, mask=True, threshold=0.5).dataobj)
    assert data.tolist() == [[[0, 1], [1, 0]]]


def test_members_use_the_threshold(tmp_path):
    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    archive = tmp_path / "prob.zip"
    shape = (20, 20, 20)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, value in (("Pair_L", 0.4), ("Pair_R", 0.7), ("Mid", 0.5)):
            data = np.zeros(shape, dtype=np.float32)
            data[5:8, 5:8, 5:8] = value
            data[0, 0, {"Pair_L": 1, "Pair_R": 2, "Mid": 3}[name]] = 0.9
            zipped.writestr(f"MEM/{name}.nii", nib.Nifti1Image(data, affine).to_bytes())
    spec = dataclasses.replace(spec_of(src, "toymembers"), threshold=0.5)
    image, lost = load_members(spec, archive)
    data = np.asarray(image.dataobj)
    assert (data[5:8, 5:8, 5:8] == 2).all() and lost == 27
    assert data[0, 0, 1] == 1 and data[0, 0, 3] == 3


def blobs(tmp_path):
    data = np.zeros((40, 30, 80), dtype=np.float32)
    data[10:14, 5:9, 20:25] = 2.0
    data[20:22, 12:15, 60:63] = 5.0
    affine = np.array([[0.5, 0, 0, -10.0], [0, 0.5, 0, -7.0], [0, 0, 0.5, -20.0],
                       [0, 0, 0, 1.0]])
    path = tmp_path / "fine.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), path)
    return path


def test_a_crop_margin_grows_the_box_and_keeps_positions(tmp_path):
    path = blobs(tmp_path)
    full = load_label_image(path)
    cut = load_label_image(path, cropped=True, margin=1.0)
    assert cut.shape == (18, 16, 49)
    for value in (2, 5):
        a = nib.affines.apply_affine(full.affine, np.argwhere(np.asarray(full.dataobj) == value))
        b = nib.affines.apply_affine(cut.affine, np.argwhere(np.asarray(cut.dataobj) == value))
        assert np.allclose(np.sort(a, axis=0), np.sort(b, axis=0))


def test_a_crop_margin_stops_at_the_image_edge(tmp_path):
    assert load_label_image(blobs(tmp_path), cropped=True, margin=100.0).shape == (40, 30, 80)


def test_the_recipe_reads_threshold_and_margin(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    edit(src / "recipe.toml", 'url = "https://example.org/toy-masks"\n',
         'url = "https://example.org/toy-masks"\nthreshold = 0.5\n')
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\ncrop = true\nmargin = 3\n')
    assert spec_of(src, "toymembers").threshold == 0.5
    assert spec_of(src, "toyhyp").margin == 3.0 and spec_of(src, "toyhyp").threshold is None
    assert problems_for(src) == []


def test_a_threshold_needs_mask_or_members(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False)
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\nthreshold = 0.5\n')
    assert "source toyhyp: threshold needs mask = true or members" in problems_for(src)


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def spine_tree(tmp_path):
    return write_extended_source_tree(tmp_path, tracts=False, spine=True)


def test_a_spine_tree_passes_every_check(tmp_path):
    src = spine_tree(tmp_path)
    recipe = load_recipe(src / "recipe.toml")
    assert problems_for(src) == [] and check_templates(recipe, src) == []
    assert [t.source.id for t in recipe.templates if t.local_only] == ["toyspine-t2"]


def test_a_shared_source_on_a_local_only_volume_is_refused(tmp_path):
    src = spine_tree(tmp_path)
    edit(src / "recipe.toml", 'volume = "brain"\npriority = 0\ndrop = [4]',
         'volume = "spine"\npriority = 0\ndrop = [4]')
    assert ("volume spine: grid source 'toyspine' is local-only, so every source and template "
            "of the volume must be local-only") in problems_for(src)


def test_a_shareable_template_cannot_be_local_only(tmp_path):
    src = spine_tree(tmp_path)
    edit(src / "recipe.toml", 'title = "Toy spinal template"\nauthors = "Test G"\nyear = 2024\n'
         'version = "1"\nlicence = "No licence stated"\nredistribution = false',
         'title = "Toy spinal template"\nauthors = "Test G"\nyear = 2024\n'
         'version = "1"\nlicence = "No licence stated"\nredistribution = true')
    assert ("template toyspine-t2: a shareable template must not be local-only"
            in check_templates(load_recipe(src / "recipe.toml"), src))


def test_a_normal_build_leaves_the_spine_volume_out(tmp_path):
    with_spine = quiet_build(spine_tree(tmp_path / "a"), tmp_path / "a" / "out", tmp_path / "c")
    plain = quiet_build(write_extended_source_tree(tmp_path / "b", tracts=False),
                        tmp_path / "b" / "out", tmp_path / "c")
    for name in ("structures.json", "sources.json", "volumes/brain.nii.gz"):
        assert (with_spine / name).read_bytes() == (plain / name).read_bytes(), name
    metadata = json.loads((with_spine / "metadata.json").read_text())
    assert [v["file"] for v in metadata["volumes"]] == [v["file"] for v in json.loads(
        (plain / "metadata.json").read_text())["volumes"]]
    assert not (with_spine / "volumes" / "spine.nii.gz").exists()
    report = (with_spine / "build-report.md").read_text()
    assert "- local-only sources left out: toyspine, toyspine-t2, toyspine-wm\n" in report


def test_a_local_build_adds_a_ras_spine_volume_and_template(toy_spine_atlas):
    atlas = Atlas.open(toy_spine_atlas)
    assert [v.name for v in atlas.volumes] == ["brain", "spine"]
    spine = atlas.volumes[1]
    assert nib.aff2axcodes(spine.affine) == ("R", "A", "S") and spine.shape == (10, 10, 56)
    fill = atlas.fills["spine"]
    assert fill.shape == spine.shape and np.allclose(fill.affine, spine.affine)
    assert (np.asarray(spine.data) == 220).any() and set(atlas.fills) == {"spine"}
    for value, structure_id in ((1, 200), (2, 210)):
        want = nib.affines.apply_affine(SPINE_AFFINE, np.argwhere(spine_volume() == value))
        got = nib.affines.apply_affine(fill.affine,
                                       np.argwhere(np.asarray(fill.data) == structure_id))
        assert np.allclose(np.sort(want, axis=0), np.sort(got, axis=0))
    records = json.loads((toy_spine_atlas / "metadata.json").read_text())["volumes"]
    assert {"file": "volumes/spine-template.nii.gz", "labels": "spine"}.items() <= next(
        r for r in records if r.get("labels") == "spine").items()
    assert atlas.local_only == ("toyspine", "toyspine-wm", "toyspine-t2")
    assert atlas.has_mesh(200) and atlas.has_mesh(210)


def test_separate_members_keep_their_own_shapes(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    edit(src / "recipe.toml", 'url = "https://example.org/toy-masks"\n',
         'url = "https://example.org/toy-masks"\nseparate = true\n')
    assert spec_of(src, "toymembers").separate and problems_for(src) == []
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    atlas = Atlas.open(out)
    x = np.asarray(atlas.mesh(190).vertices)[:, 0]
    assert x.min() < -4.0 and x.max() > 4.0
    assert "- overlapping voxels in toymembers: 200\n" in (out / "build-report.md").read_text()


def test_separate_needs_members_and_a_native_grid(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False)
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\nseparate = true\n')
    assert "source toyhyp: separate needs members" in problems_for(src)


def test_separate_shapes_do_not_keep_full_grids_alive(tmp_path):
    from tools.build_atlas.labels import separate_natives

    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    spec = dataclasses.replace(spec_of(src, "toymembers"), separate=True)
    archive = next((tmp_path / "t" / "upstream" / "members").glob("*.zip"))
    natives = separate_natives(spec, archive, {1: 181, 2: 182, 3: 190})
    assert [int(data.max()) for data, _ in natives] == [181, 182, 190]
    assert all(data.base is None for data, _ in natives)
    assert all(data.shape == (7, 10, 10) or data.shape == (5, 10, 10) for data, _ in natives)


def taller_tract_tree(tmp_path, within=True):
    src = spine_tree(tmp_path)
    tract = tmp_path / "upstream" / "toy_spine_wm.nii.gz"
    old = sha256_file(tract)
    mask = np.zeros(spine_volume().shape, dtype=np.uint8)
    mask[6:8, 6:10, 40:66] = 1
    nib.save(nib.Nifti1Image(mask, SPINE_AFFINE), tract)
    edit(src / "recipe.toml", old, sha256_file(tract))
    if within:
        edit(src / "recipe.toml", "mask = true\n", 'mask = true\nwithin = "toyspine"\n')
    return src


def test_within_trims_voxels_above_and_below_the_named_source(tmp_path):
    src = taller_tract_tree(tmp_path)
    assert spec_of(src, "toyspine-wm").within == "toyspine" and problems_for(src) == []
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    spine = atlas.volumes[1]
    index = np.argwhere(np.asarray(spine.data) == 220)
    top = -230.0 + 59 + 0.5
    assert len(index) and (nib.affines.apply_affine(spine.affine, index)[:, 2] < top).all()
    assert np.asarray(atlas.mesh(220).vertices)[:, 2].max() < top + 1.0


def test_without_within_the_tract_keeps_its_full_height(tmp_path):
    src = taller_tract_tree(tmp_path, within=False)
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    assert np.asarray(atlas.mesh(220).vertices)[:, 2].max() > -230.0 + 63


def test_within_must_name_a_label_source_on_the_same_volume(tmp_path):
    src = spine_tree(tmp_path)
    edit(src / "recipe.toml", "mask = true\n", 'mask = true\nwithin = "toyhyp"\n')
    assert "source toyspine-wm: within 'toyhyp' is not a label source of volume spine" in (
        problems_for(src))


def probability_zip(path, maps, affine):
    with zipfile.ZipFile(path, "w") as zipped:
        for name, data in maps.items():
            zipped.writestr(f"MEM/{name}.nii", nib.Nifti1Image(data, affine).to_bytes())
    return path


TILE_SIDES = {1: "left", 2: "right", 3: "midline"}


def test_tiles_give_each_voxel_to_the_most_likely_member(tmp_path):
    from tools.build_atlas.labels import load_tiles

    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    shape = (10, 10, 10)
    maps = {name: np.zeros(shape, dtype=np.float32) for name in ("Pair_L", "Pair_R", "Mid")}
    maps["Pair_L"][2:4, 2:4, 2:4], maps["Mid"][2:4, 2:4, 2:4] = 0.4, 0.3
    maps["Pair_L"][6:8, 6:8, 6:8], maps["Mid"][6:8, 6:8, 6:8] = 0.2, 0.2
    archive = probability_zip(tmp_path / "p.zip", maps, np.diag([1.0, 1.0, 1.0, 1.0]))
    spec = dataclasses.replace(spec_of(src, "toymembers"), tiles=0.5)
    data = np.asarray(load_tiles(spec, archive, TILE_SIDES).dataobj)
    assert (data[2:4, 2:4, 2:4] == 1).all() and (data[6:8, 6:8, 6:8] == 0).all()
    assert set(np.unique(data)) == {0, 1}


def test_tiles_split_ties_by_side(tmp_path):
    from tools.build_atlas.labels import load_tiles

    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    shape = (20, 6, 6)
    maps = {name: np.zeros(shape, dtype=np.float32) for name in ("Pair_L", "Pair_R", "Mid")}
    maps["Pair_L"][8:14], maps["Pair_R"][8:14] = 0.6, 0.6
    affine = np.diag([1.0, 1.0, 1.0, 1.0])
    affine[0, 3] = -10.5
    archive = probability_zip(tmp_path / "p.zip", maps, affine)
    spec = dataclasses.replace(spec_of(src, "toymembers"), tiles=0.5)
    data = np.asarray(load_tiles(spec, archive, TILE_SIDES).dataobj)
    assert (data[8:11] == 1).all() and (data[11:14] == 2).all()
    assert (data == 1).sum() == (data == 2).sum()


def test_tiles_need_members_and_rule_out_separate(tmp_path):
    src = write_extended_source_tree(tmp_path / "a", tracts=False)
    edit(src / "recipe.toml", 'mesh_grid = "native"\n', 'mesh_grid = "native"\ntiles = 0.5\n')
    assert "source toyhyp: tiles needs members" in problems_for(src)
    src = write_extended_source_tree(tmp_path / "b", tracts=False, members="download")
    edit(src / "recipe.toml", 'url = "https://example.org/toy-masks"\n',
         'url = "https://example.org/toy-masks"\ntiles = 0.5\nseparate = true\n')
    assert "source toymembers: tiles and separate do not mix" in problems_for(src)


def test_a_tiled_build_reports_small_shapes(tmp_path, monkeypatch):
    import tools.build_atlas.build as build_module

    monkeypatch.setattr(build_module, "SMALL_VOXELS", 400)
    src = write_extended_source_tree(tmp_path, tracts=False, members="download")
    edit(src / "recipe.toml", 'url = "https://example.org/toy-masks"\n',
         'url = "https://example.org/toy-masks"\ntiles = 0.5\n')
    assert problems_for(src) == []
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    report = (out / "build-report.md").read_text()
    assert "  - small shapes: Toy middle (300 voxels)\n" in report
    assert Atlas.open(out).has_mesh(181) and Atlas.open(out).has_mesh(190)


def test_a_midline_voxel_tied_between_sides_goes_to_neither(tmp_path):
    from tools.build_atlas.labels import load_tiles

    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    shape = (21, 6, 6)
    maps = {name: np.zeros(shape, dtype=np.float32) for name in ("Pair_L", "Pair_R", "Mid")}
    maps["Pair_L"][9:11], maps["Pair_R"][10:12] = 0.6, 0.6
    affine = np.diag([1.0, 1.0, 1.0, 1.0])
    affine[0, 3] = -10.0
    archive = probability_zip(tmp_path / "p.zip", maps, affine)
    spec = dataclasses.replace(spec_of(src, "toymembers"), tiles=0.5)
    data = np.asarray(load_tiles(spec, archive, TILE_SIDES).dataobj)
    assert (data[9] == 1).all() and (data[11] == 2).all() and (data[10] == 0).all()


def field_meshes(tmp_path, maps, affine):
    from tools.build_atlas.labels import load_tiles, tile_fields
    from tools.build_atlas.meshing import field_surface

    src = write_extended_source_tree(tmp_path / "t", tracts=False, members="download")
    archive = probability_zip(tmp_path / "p.zip", maps, affine)
    spec = dataclasses.replace(spec_of(src, "toymembers"), tiles=0.5)
    tiles = load_tiles(spec, archive, TILE_SIDES)
    return {value: field_surface(field, field_affine)
            for value, field, field_affine in tile_fields(spec, archive, tiles, {1, 2, 3})}


def test_tile_borders_follow_the_probabilities_not_the_voxels(tmp_path):
    shape = (30, 30, 10)
    g = np.indices(shape).astype(np.float32)
    first = 0.5 + 0.5 * np.tanh((g[0] - 15 + 0.3 * (g[1] - 15)) / 3)
    maps = {"Pair_L": first, "Mid": 1 - first, "Pair_R": np.zeros(shape, np.float32)}
    meshes = field_meshes(tmp_path, maps, np.eye(4))
    points = np.asarray(meshes[1].points)
    inner = points[(points[:, 1] > 3) & (points[:, 1] < 26) & (points[:, 2] > 2)
                   & (points[:, 2] < 7) & (points[:, 0] > 3) & (points[:, 0] < 26)]
    distance = (inner[:, 0] - 15 + 0.3 * (inner[:, 1] - 15)) / np.hypot(1, 0.3)
    assert len(inner) > 20 and np.abs(distance).max() < 0.1
    assert set(meshes) == {1, 3}


def test_mirrored_tiles_give_mirrored_shapes(tmp_path):
    shape = (21, 12, 12)
    g = np.indices(shape).astype(np.float32)
    bump = np.exp(-((g[1] - 6) ** 2 + (g[2] - 6) ** 2) / 8)
    left = bump * np.clip(1 - np.abs(g[0] - 8) / 4, 0, 1)
    affine = np.diag([1.0, 1.0, 1.0, 1.0])
    affine[0, 3] = -10.0
    maps = {"Pair_L": left, "Pair_R": left[::-1].copy(), "Mid": np.zeros(shape, np.float32)}
    meshes = field_meshes(tmp_path, maps, affine)
    a, b = meshes[1], meshes[2]
    assert a.volume == pytest.approx(b.volume, rel=0.01)
    assert np.asarray(a.points)[:, 0].max() <= 1e-3 and np.asarray(b.points)[:, 0].min() >= -1e-3


def test_small_shapes_include_structures_with_no_voxels():
    from tools.build_atlas.build import small_shapes

    labelled = np.array([[0, 5, 5]])
    assert small_shapes(labelled, [7, 5], {5: "Toy five", 7: "Toy seven"}) == [
        "Toy five (2 voxels)", "Toy seven (0 voxels)"]
