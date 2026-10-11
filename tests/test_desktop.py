import time

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from cns_atlas import DISCLAIMER, Atlas
from cns_desktop.app import disclaimer_due, main, mark_disclaimer_shown
from cns_desktop.main_window import MainWindow, about_text
from cns_desktop.state import AppState


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def atlas(toy_atlas):
    return Atlas.open(toy_atlas)


@pytest.fixture
def window(qapp, atlas):
    w = MainWindow(atlas)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def find_pixel(view, want=lambda sid: sid is not None, step=6):
    width, height = view.ren_win.GetSize()
    points = [(x, y) for y in range(step, height, step) for x in range(step, width, step)]
    points.sort(key=lambda p: (p[0] - width / 2) ** 2 + (p[1] - height / 2) ** 2)
    for x, y in points:
        sid = view.structure_at(x, y)
        if want(sid):
            return x, y, sid
    raise AssertionError("no matching pixel")


def test_state_select_guards_and_validates(atlas):
    state = AppState(atlas)
    seen = []
    state.selection_changed.connect(seen.append)
    state.select(101)
    state.select(101)
    assert seen == [101]
    with pytest.raises(KeyError):
        state.select(999)


def test_state_isolate_keeps_the_whole_subtree(atlas):
    state = AppState(atlas)
    assert state.geometry_ids == (101, 102, 111, 112, 120)
    state.isolate(100)
    assert not state.is_hidden(101) and not state.is_hidden(102)
    assert all(state.is_hidden(i) for i in (111, 112, 120))


def test_tree_mirrors_the_hierarchy(window):
    assert window.tree.tree.topLevelItem(0).text(0) == "Central nervous system"
    alpha = window.tree.items[100]
    assert [alpha.child(i).text(0) for i in range(alpha.childCount())] == [
        "Alpha gyrus (left)", "Alpha gyrus (right)"]


def test_tree_selection_updates_every_view(window):
    window.tree.tree.setCurrentItem(window.tree.items[111])
    assert window.state.selected == 111
    assert "Beta nucleus (left)" in window.info.toPlainText()
    assert "Beta nucleus (left)" in window.chart.plotItem.titleLabel.text
    assert window.view.highlighted == [111]


def test_click_in_3d_selects_structure_under_cursor(window):
    current = window.state.selected
    x, y, sid = find_pixel(window.view, lambda s: s is not None and s != current)
    window.view.pick_at(x, y)
    assert window.state.selected == sid
    assert window.tree.tree.currentItem() is window.tree.items[sid]


def test_click_on_background_keeps_selection(window):
    before = window.state.selected
    window.view.pick_at(1, 1)
    assert window.state.selected == before


def test_unchecking_a_group_hides_its_whole_subtree(window):
    window.tree.items[100].setCheckState(0, Qt.CheckState.Unchecked)
    assert window.state.is_hidden(101) and window.state.is_hidden(102)
    assert not window.view.is_drawn(101)
    assert not window.state.is_hidden(111)
    window.state.show_all()
    assert window.tree.items[100].checkState(0) == Qt.CheckState.Checked
    assert window.view.is_drawn(101)


def test_filter_matches_acronym_and_keeps_ancestors(window):
    window.tree.apply_filter("ben")
    shown = {sid for sid, item in window.tree.items.items() if not item.isHidden()}
    assert {1, 2, 110, 111, 112} <= shown
    assert 100 not in shown and 120 not in shown
    window.tree.apply_filter("")
    assert not any(item.isHidden() for item in window.tree.items.values())


def test_info_panel_shows_draft_references_source_and_disclaimer(window):
    window.state.select(101)
    text = window.info.toPlainText()
    assert "Draft" in text
    assert "Does alpha things [1]" in text
    assert "Author A (2020). A reference." in text
    assert "Toy labelled atlas" in text
    assert DISCLAIMER in text


def test_info_panel_without_entry(window):
    window.state.select(111)
    assert "No description yet." in window.info.toPlainText()


def test_about_text_has_disclaimer_and_sources(atlas):
    text = about_text(atlas)
    assert DISCLAIMER in text and "Toy labelled atlas" in text


def test_disclaimer_is_due_once(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert disclaimer_due(settings)
    mark_disclaimer_shown(settings)
    assert not disclaimer_due(settings)


def test_main_reports_missing_atlas(tmp_path, capsys):
    assert main(["--atlas", str(tmp_path / "missing")]) == 1
    assert "python -m tools.build_atlas" in capsys.readouterr().err


@pytest.mark.perf
def test_selection_updates_all_panels_under_7ms(window):
    ids = list(window.state.geometry_ids)
    times = []
    for i in range(40):
        target = ids[i % len(ids)]
        if target == window.state.selected:
            continue
        start = time.perf_counter()
        window.state.select(target)
        times.append(time.perf_counter() - start)
    times.sort()
    assert times[len(times) // 2] < 0.007


def test_view_uses_the_packages_stored_normals(window, atlas):
    normals = window.view.blocks[101].GetPointData().GetNormals()
    assert normals is not None
    assert normals.GetNumberOfTuples() == len(atlas.mesh(101).normals)
    assert window.view.actor.GetProperty().GetInterpolationAsString() == "Gouraud"


def test_selecting_a_concept_highlights_all_of_its_geometry(window):
    window.state.select(100)
    assert window.view.highlighted == [101, 102]
    window.state.select(111)
    assert window.view.highlighted == [111]


def test_group_toggle_sends_one_visibility_change(window):
    seen = []
    window.state.visibility_changed.connect(seen.append)
    window.tree.items[1].setCheckState(0, Qt.CheckState.Unchecked)
    assert seen == [frozenset(window.state.geometry_ids)]
    window.tree.items[1].setCheckState(0, Qt.CheckState.Checked)
    assert len(seen) == 2
    assert not any(window.state.is_hidden(i) for i in window.state.geometry_ids)


def test_check_marks_follow_the_state(window):
    window.state.set_hidden([101], True)
    assert window.tree.items[101].checkState(0) == Qt.CheckState.Unchecked
    assert window.tree.items[100].checkState(0) == Qt.CheckState.PartiallyChecked
    assert window.tree.items[1].checkState(0) == Qt.CheckState.PartiallyChecked
    window.state.show_all()
    assert window.tree.items[1].checkState(0) == Qt.CheckState.Checked


def test_slice_state_emits_once_and_validates(atlas):
    state = AppState(atlas)
    assert (state.slice_axis, state.slice_mm) == ("axial", 0.0)
    seen = []
    state.slice_changed.connect(lambda axis, mm: seen.append((axis, mm)))
    state.set_slice("coronal", 12)
    state.set_slice("coronal", 12.0)
    assert seen == [("coronal", 12.0)]
    with pytest.raises(ValueError, match="oblique"):
        state.set_slice("oblique", 0.0)


def test_one_composite_block_per_structure_with_geometry(window):
    data = window.view.composite_mapper.GetInputDataObject(0, 0)
    assert data.GetNumberOfBlocks() == len(window.state.geometry_ids) == 5
    assert window.view.lod == 0


def test_hidden_structure_cannot_be_picked(window):
    x, y, sid = find_pixel(window.view)
    window.state.set_hidden([sid], True)
    assert window.view.structure_at(x, y) != sid


def test_nothing_is_picked_when_everything_is_hidden(window):
    x, y, _ = find_pixel(window.view)
    window.state.set_hidden(window.state.geometry_ids, True)
    assert window.view.structure_at(x, y) is None


def test_visibility_change_renders_once(window):
    before = window.view.render_count
    window.tree.items[100].setCheckState(0, Qt.CheckState.Unchecked)
    assert window.view.render_count == before + 1


def test_highlight_overlay_skips_hidden_structures(window):
    window.state.set_hidden([101], True)
    window.state.select(100)
    assert window.view.highlighted == [101, 102]
    assert window.view.overlay_ids == [102]
    assert not window.view.overlay.GetPickable()
    window.state.set_hidden([101], False)
    assert window.view.overlay_ids == [101, 102]


def test_cutting_plane_follows_the_slice(window):
    window.state.set_slice("coronal", 12.0)
    ymin, ymax = window.view.plane.GetBounds()[2:4]
    assert abs(ymin - 12.0) < 1e-6 and abs(ymax - 12.0) < 1e-6
    window.state.set_slice("axial", -20.0)
    zmin, zmax = window.view.plane.GetBounds()[4:6]
    assert abs(zmin + 20.0) < 1e-6 and abs(zmax + 20.0) < 1e-6
