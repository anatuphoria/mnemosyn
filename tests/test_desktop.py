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
    for y in range(step, height, step):
        for x in range(step, width, step):
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
    assert window.view._actors[111].GetProperty().GetAmbient() > 0


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
    assert not window.view._actors[101].GetVisibility()
    assert not window.state.is_hidden(111)
    window.state.show_all()
    assert window.tree.items[100].checkState(0) == Qt.CheckState.Checked
    assert window.view._actors[101].GetVisibility()


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
    actor = window.view._actors[101]
    normals = actor.GetMapper().GetInput().GetPointData().GetNormals()
    assert normals is not None
    assert normals.GetNumberOfTuples() == len(atlas.mesh(101).normals)
    assert actor.GetProperty().GetInterpolationAsString() == "Gouraud"
