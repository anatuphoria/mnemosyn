import json

import numpy as np
import pytest

from atlas_fixtures import AFFINE, BLOBS, NAMES, make_source_archive, write_source_tree
from cns_atlas import Atlas
from tools.build_atlas.__main__ import main
from tools.build_atlas.build import build
from tools.build_atlas.idlock import load_lock
from tools.build_atlas.recipe import BuildError


def files_of(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


def world(voxel):
    return tuple((AFFINE @ np.array([*voxel, 1.0]))[:3])


@pytest.fixture
def toy_src(tmp_path):
    archive, sha256 = make_source_archive(tmp_path / "upstream")
    return write_source_tree(tmp_path / "src", archive, sha256)


def test_toy_atlas_package_contents(toy_atlas):
    atlas = Atlas.open(toy_atlas)
    assert [s.id for s in atlas.structures] == [1, 2, 100, 101, 102, 110, 111, 112, 120]
    assert atlas.get(101).xrefs == {"toy": "Alpha_L"}
    assert [s.id for s in atlas.structures if atlas.has_mesh(s.id)] == [101, 102, 111, 112, 120]
    for structure_id in (101, 102, 111, 112, 120):
        faces = [len(atlas.mesh(structure_id, lod).faces) for lod in (0, 1, 2)]
        assert faces[0] <= 2000 and faces[0] >= faces[1] >= faces[2] >= 64
    assert atlas.label_at(world(BLOBS[1][0])) == 101
    assert atlas.label_at(world(BLOBS[5][0])) == 120
    assert "Does alpha things" in atlas.knowledge(102).sections["Function"]
    assert atlas.sources["toy"].licence == "CC0 1.0"


def test_toy_atlas_metadata_keeps_brainglobe_keys(toy_atlas):
    metadata = json.loads((toy_atlas / "metadata.json").read_text())
    for key in ("name", "citation", "atlas_link", "species", "symmetric", "resolution",
                "orientation", "shape", "version", "additional_references"):
        assert key in metadata
    assert metadata["orientation"] == "lpi"
    assert metadata["resolution"] == [4000.0, 4000.0, 4000.0]
    assert metadata["shape"] == [40, 48, 36]
    assert metadata["format_version"] == 1 and metadata["coordinate_units"] == "mm"


def test_mesh_vertices_are_in_world_millimetres(toy_atlas):
    atlas = Atlas.open(toy_atlas)
    left = np.asarray(atlas.mesh(101).vertices).mean(axis=0)
    right = np.asarray(atlas.mesh(102).vertices).mean(axis=0)
    assert left[0] < 0 < right[0]
    assert np.allclose(left, world(BLOBS[1][0]), atol=4.0)


def test_build_writes_id_lock(toy_src, tmp_path):
    build(toy_src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    lock = load_lock(toy_src / "ids.lock")
    assert lock.published == {1, 2, 100, 101, 102, 110, 111, 112, 120}


def test_build_is_deterministic(toy_src, tmp_path):
    a = build(toy_src, tmp_path / "a", cache=tmp_path / "cache", log=lambda *_: None)
    b = build(toy_src, tmp_path / "b", cache=tmp_path / "cache", log=lambda *_: None)
    assert files_of(a) == files_of(b)


def test_failed_build_keeps_previous_package(toy_src, tmp_path):
    out = build(toy_src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    before, lock_before = files_of(out), (toy_src / "ids.lock").read_text()
    (toy_src / "knowledge" / "en" / "100.md").write_text(
        "+++\nid = 100\n+++\n## Function\nBroken [nope2000].\n")
    with pytest.raises(BuildError, match="cites missing reference"):
        build(toy_src, out, cache=tmp_path / "cache", log=lambda *_: None)
    assert files_of(out) == before
    assert (toy_src / "ids.lock").read_text() == lock_before
    assert Atlas.open(out).get(101).name == "Alpha gyrus (left)"


def test_unmapped_source_label_fails(tmp_path):
    blobs = {**BLOBS, 6: ((30, 40, 28), (2, 2, 2))}
    archive, sha256 = make_source_archive(tmp_path / "upstream", blobs, {**NAMES, 6: "Delta"})
    src = write_source_tree(tmp_path / "src", archive, sha256)
    with pytest.raises(BuildError, match="source toy: label 6 has no structure"):
        build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)


def test_structure_without_voxels_fails(tmp_path):
    blobs = {k: v for k, v in BLOBS.items() if k != 5}
    archive, sha256 = make_source_archive(tmp_path / "upstream", blobs)
    src = write_source_tree(tmp_path / "src", archive, sha256)
    with pytest.raises(BuildError, match=r"structure 120 \(Gamma body\) has no voxels"):
        build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)


def test_cli_success_and_failure(toy_src, tmp_path, capsys):
    args = ["--src", str(toy_src), "--out", str(tmp_path / "cli"), "--cache", str(tmp_path / "c")]
    assert main(args) == 0
    assert "built" in capsys.readouterr().out
    (toy_src / "recipe.toml").write_text(
        (toy_src / "recipe.toml").read_text().replace("redistribution = true",
                                                      "redistribution = false"))
    assert main(args) == 1
    assert "redistribution is not allowed" in capsys.readouterr().err


def test_refuses_to_replace_a_directory_that_is_not_an_atlas(toy_src, tmp_path):
    out = tmp_path / "Documents"
    out.mkdir()
    (out / "thesis.docx").write_bytes(b"important")
    with pytest.raises(BuildError, match="not an atlas package"):
        build(toy_src, out, cache=tmp_path / "cache", log=lambda *_: None)
    assert (out / "thesis.docx").read_bytes() == b"important"


def test_previous_package_survives_a_failed_final_rename(toy_src, tmp_path, monkeypatch):
    out = build(toy_src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    before = files_of(out)
    original = type(out).replace

    def failing_replace(self, target):
        if self.name == "package":
            raise OSError("disk full")
        return original(self, target)

    monkeypatch.setattr(type(out), "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        build(toy_src, out, cache=tmp_path / "cache", log=lambda *_: None)
    monkeypatch.undo()
    assert files_of(out) == before
    assert not list(tmp_path.glob(".out-*"))
