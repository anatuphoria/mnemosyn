import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cns_desktop.atlas_data import load_atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.state import AppState


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def atlas():
    return load_atlas()


@pytest.fixture
def window(qapp, atlas):
    w = MainWindow(atlas)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def find_pixel(view, want=lambda sid: sid is not None, step=12):
    w, h = view.ren_win.GetSize()
    for y in range(step, h, step):
        for x in range(step, w, step):
            sid = view.structure_at(x, y)
            if want(sid):
                return x, y, sid
    raise AssertionError("no matching pixel")


def test_state_select_guards_and_validates(atlas):
    state = AppState(atlas)
    seen = []
    state.selection_changed.connect(seen.append)
    sid = next(iter(atlas.structures))
    state.select(sid)
    state.select(sid)
    assert seen == [sid]
    with pytest.raises(KeyError):
        state.select("not-a-structure")


def test_state_visibility_emits_only_changes(atlas):
    state = AppState(atlas)
    seen = []
    state.visibility_changed.connect(seen.append)
    a, b = list(atlas.structures)[:2]
    state.set_hidden([a], True)
    state.set_hidden([a, b], True)
    assert seen == [frozenset({a}), frozenset({b})]
    state.isolate(a)
    assert not state.is_hidden(a)
    assert all(state.is_hidden(s) for s in atlas.structures if s != a)


def test_tree_selection_updates_every_view(window):
    sid = next(s for s in window.state.atlas.structures if s != window.state.selected)
    window.tree.tree.setCurrentItem(window.tree.items[sid])
    s = window.state.atlas.structures[sid]
    assert window.state.selected == sid
    assert s.name in window.info.toPlainText()
    assert s.name in window.chart.plotItem.titleLabel.text
    assert window.view._actors[sid].GetProperty().GetAmbient() > 0


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


def test_tree_checkbox_hides_structure_and_it_is_not_pickable(window):
    x, y, sid = find_pixel(window.view)
    window.tree.items[sid].setCheckState(0, Qt.CheckState.Unchecked)
    assert window.state.is_hidden(sid)
    assert not window.view._actors[sid].GetVisibility()
    assert window.view.structure_at(x, y) != sid
    window.state.show_all()
    assert window.tree.items[sid].checkState(0) == Qt.CheckState.Checked
    assert window.view._actors[sid].GetVisibility()


def test_filter_hides_non_matching_tree_items(window):
    window.tree.apply_filter("hippo")
    shown = [sid for sid, item in window.tree.items.items() if not item.isHidden()]
    assert shown and all("hippo" in sid.lower() for sid in shown)
    window.tree.apply_filter("")
    assert not any(item.isHidden() for item in window.tree.items.values())
