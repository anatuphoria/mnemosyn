import pytest

from atlas_fixtures import (BLOBS, make_source_archive, write_extended_source_tree,
                            write_source_tree)
from tools.build_atlas.build import build
from tools.build_atlas.recipe import BuildError

pytest.importorskip("pyvista")


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def report(out):
    return (out / "build-report.md").read_text()


def toy_src(root, blobs=BLOBS):
    archive, sha256 = make_source_archive(root / "upstream", blobs=blobs)
    return write_source_tree(root / "src", archive, sha256)


def test_the_first_build_has_nothing_to_compare(tmp_path):
    out = quiet_build(toy_src(tmp_path), tmp_path / "out", tmp_path / "cache")
    assert "- changes since the previous build: no previous build\n" in report(out)


def test_rebuilding_unchanged_reports_no_changes(tmp_path):
    src = toy_src(tmp_path)
    quiet_build(src, tmp_path / "out", tmp_path / "cache")
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    assert "- changes since the previous build: none\n" in report(out)


def test_a_renamed_structure_stops_the_rebuild_unless_accepted(tmp_path):
    src = toy_src(tmp_path)
    quiet_build(src, tmp_path / "out", tmp_path / "cache")
    structures = src / "structures.toml"
    structures.write_text(structures.read_text().replace('name = "Gamma body"',
                                                         'name = "Gamma bodies"'))
    with pytest.raises(BuildError) as error:
        quiet_build(src, tmp_path / "out", tmp_path / "cache")
    assert "renamed: Gamma body (120), now Gamma bodies" in error.value.problems
    assert error.value.problems[-1] == ("if these changes are intended, rebuild with "
                                        "--accept-changes")
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache", accept_changes=True)
    assert "  - renamed: Gamma body (120), now Gamma bodies\n" in report(out)


def test_moved_shapes_are_reported_not_failed(tmp_path):
    quiet_build(toy_src(tmp_path / "a"), tmp_path / "out", tmp_path / "cache")
    smaller = {**BLOBS, 5: (BLOBS[5][0], (3, 2, 2))}
    out = quiet_build(toy_src(tmp_path / "b", smaller), tmp_path / "out", tmp_path / "cache")
    text = report(out)
    assert "  - moved: Gamma body (120)" in text


def test_a_normal_build_over_a_local_one_is_not_a_removal(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=True, local=True)
    quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True)
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    text = report(out)
    assert "- changes since the previous build:" in text and "removed" not in text


def test_an_unreadable_previous_build_is_a_build_error(tmp_path):
    import json

    src = toy_src(tmp_path)
    out = quiet_build(src, tmp_path / "out", tmp_path / "cache")
    metadata = json.loads((out / "metadata.json").read_text())
    metadata["format_version"] = 99
    (out / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(BuildError) as error:
        quiet_build(src, tmp_path / "out", tmp_path / "cache")
    assert "the previous build cannot be read" in error.value.problems[0]
    assert "move it aside" in error.value.problems[0]
