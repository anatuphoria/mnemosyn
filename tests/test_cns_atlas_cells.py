import json

import pytest

from atlas_package import (TOY_CELLS_TEXT, TOY_REFERENCE, tiny_structures, toy_cell_view,
                           write_package)
from cns_atlas import Atlas, AtlasError, KnowledgeError
from cns_atlas.cells import CellView
from cns_atlas.knowledge import parse_entry


def test_cell_view_round_trips_through_json():
    view = toy_cell_view()
    assert CellView.from_json(json.loads(json.dumps(view.to_json()))) == view


def test_package_without_cells_has_no_views(tmp_path):
    atlas = Atlas.open(write_package(tmp_path / "a", tiny_structures()))
    assert atlas.cell_views() == () and atlas.cell_view_for(101) is None


def test_view_is_found_from_a_side_structure(tmp_path):
    atlas = Atlas.open(write_package(tmp_path / "a", tiny_structures(), cells=[toy_cell_view()]))
    assert atlas.cell_view_for(101).key == "toy" and atlas.cell_view_for(110) is None


def test_cells_are_not_read_when_the_atlas_opens(tmp_path):
    root = write_package(tmp_path / "a", tiny_structures())
    (root / "cells.json").write_text("not json")
    atlas = Atlas.open(root)
    with pytest.raises(AtlasError):
        atlas.cell_views()


def test_full_level_includes_basic_cells():
    assert [c.key for c in toy_cell_view().cells_at("full")] == ["big", "small", "stop"]
    assert [c.key for c in toy_cell_view().cells_at("basic")] == ["big", "small"]


def test_cell_text_reads_sections_and_numbers_citations(tmp_path):
    root = write_package(tmp_path / "a", tiny_structures(), cells=[toy_cell_view()],
                         entries={"en": {"cells-toy": TOY_CELLS_TEXT}}, references=TOY_REFERENCE)
    text = Atlas.open(root).cell_text("toy")
    assert text.status == "draft" and "[1]" in text.items["cell:big"]
    assert text.items["layer:upper"].startswith("The upper layer")
    assert text.items["box:input"] == "The input arrives here."
    assert text.steps["basic"] == ("Basic one", "Basic two")
    assert len(text.steps["full"]) == 3 and text.references[0].key == "toy2020"


def test_cell_text_without_a_view_is_none(tmp_path):
    atlas = Atlas.open(write_package(tmp_path / "a", tiny_structures()))
    assert atlas.cell_text("toy") is None


def test_malformed_cells_file_is_an_atlas_error(tmp_path):
    root = write_package(tmp_path / "a", tiny_structures())
    (root / "cells.json").write_text('[{"key": 1}]')
    with pytest.raises(AtlasError):
        Atlas.open(root).cell_views()


def test_unknown_cells_section_is_refused():
    with pytest.raises(KnowledgeError):
        parse_entry('+++\nkey = "cells-toy"\n+++\n## Function\nx\n', "t")


def test_cells_sections_are_accepted():
    entry = parse_entry(TOY_CELLS_TEXT, "t")
    assert "Cell big" in entry.sections and "Full step 3" in entry.sections


def test_cell_view_key_falls_back_to_cells_json(tmp_path):
    atlas = Atlas.open(write_package(tmp_path / "a", tiny_structures(), cells=[toy_cell_view()]))
    assert atlas.cell_view_key(102) == "toy" and atlas.cell_view_key(110) is None
