import re
import shutil
from pathlib import Path

import pytest

from atlas_fixtures import write_extended_source_tree
from cns_atlas import Atlas
from tools.build_atlas.build import build
from tools.build_atlas.recipe import BuildError

pytest.importorskip("pyvista")

CHANGES = {
    "unknown layer": ('layer = "upper", start = 0.1', 'layer = "nowhere", start = 0.1'),
    "unknown flow in step": ('steps = [{ flows = ["f1"], lit = ["small"] }, { flows = ["f2"]',
                             'steps = [{ flows = ["f9"], lit = ["small"] }, { flows = ["f2"]'),
    "full cell lit in basic": ('{ flows = ["f2"], lit = ["big"] }]\n\n[levels.full]',
                               '{ flows = ["f2"], lit = ["stop"] }]\n\n[levels.full]'),
    "unknown structure": ("structures = [100]", "structures = [99999]"),
    "one point curve": ("points = [[100, 200], [500, 150], [900, 200]]", "points = [[100, 200]]"),
}


def quiet(*_):
    pass


def build_cells_tree(tmp_path: Path) -> Path:
    write_extended_source_tree(tmp_path, tracts=False, cells=True)
    return tmp_path


def build_broken(tmp_path: Path, change: str) -> Path:
    root = build_cells_tree(tmp_path)
    src = root / "src"
    if change == "missing text":
        text = src / "knowledge" / "en" / "cells-toy.md"
        text.write_text(text.read_text().replace("## Cell small\nSmall cells receive the input.\n\n", ""))
    elif change == "bad sha":
        toml = src / "cells" / "toy.toml"
        toml.write_text(re.sub(r'sha256 = "[0-9a-f]{64}"', 'sha256 = "' + "0" * 64 + '"',
                               toml.read_text(), count=1))
    elif change == "extra text":
        text = src / "knowledge" / "en" / "cells-toy.md"
        text.write_text(text.read_text() + "\n## Cell ghost\nNot here.\n")
    else:
        old, new = CHANGES[change]
        toml = src / "cells" / "toy.toml"
        assert old in toml.read_text()
        toml.write_text(toml.read_text().replace(old, new, 1))
    return build(src, root / "out" / "toy", cache=root / "cache", log=quiet)


def move_swc_files_away(root: Path) -> None:
    folder = root / "upstream" / "neurons"
    shutil.move(folder, root / "upstream" / "gone")


def test_cells_json_holds_the_flattened_view(toy_cells_atlas):
    view = Atlas.open(toy_cells_atlas).cell_views()[0]
    assert view.key == "toy" and [c.key for c in view.cells] == ["big", "small", "stop"]
    lines = view.cells[0].reconstructions[0].lines
    assert lines and all(len(line.points) >= 2 for line in lines)
    assert view.cells[1].reconstructions[0].species == "human"


def test_neuromorpho_is_one_source(toy_cells_atlas):
    source = Atlas.open(toy_cells_atlas).sources["neuromorpho"]
    assert source.licence == "CC BY 4.0" and source.provides == "Neuron shapes"
    assert source.doi == "10.1096/fba.2024-00048" and "Author T (2020)" in source.version


def test_cell_text_reaches_the_package(toy_cells_atlas):
    text = Atlas.open(toy_cells_atlas).cell_text("toy")
    assert text.steps["full"][2] == "Full three"


def test_build_report_counts_cell_views(toy_cells_atlas):
    assert "- cell views: 1" in (toy_cells_atlas / "build-report.md").read_text()


def test_cc_by_notice_is_shipped(toy_cells_atlas):
    assert (toy_cells_atlas / "LICENSES" / "CC-BY-4.0.txt").exists()


def test_build_without_cells_writes_an_empty_list(toy_pathway_atlas):
    assert Atlas.open(toy_pathway_atlas).cell_views() == ()


@pytest.mark.parametrize("change, message", [
    ("unknown layer", "toy.toml: cell 'big': unknown layer 'nowhere'"),
    ("unknown flow in step", "toy.toml: basic step 1: unknown flow 'f9'"),
    ("full cell lit in basic", "toy.toml: basic step 2: 'stop' is a full level cell"),
    ("unknown structure", "toy.toml: unknown structure 99999"),
    ("one point curve", "toy.toml: layer 'upper': needs at least two points"),
    ("missing text", "cells-toy.md: missing section 'Cell small'"),
    ("extra text", "cells-toy.md: section 'Cell ghost' names no item"),
])
def test_cell_source_errors(tmp_path, change, message):
    with pytest.raises(BuildError) as error:
        build_broken(tmp_path, change)
    assert any(message in line for line in error.value.problems), error.value.problems


def test_wrong_checksum_names_the_reconstruction(tmp_path):
    with pytest.raises(BuildError, match="toy.toml: cell 'big': reconstruction 1: checksum"):
        build_broken(tmp_path, "bad sha")


def test_failed_download_names_the_reconstruction_and_cache_is_reused(tmp_path):
    root = build_cells_tree(tmp_path)
    build(root / "src", root / "out" / "a", cache=root / "cache", log=quiet)
    move_swc_files_away(root)
    build(root / "src", root / "out" / "b", cache=root / "cache", log=quiet)
    with pytest.raises(BuildError, match="reconstruction 1: download failed"):
        build(root / "src", root / "out" / "c", cache=root / "empty", log=quiet)
