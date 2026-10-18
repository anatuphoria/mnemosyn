import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.views.brain_view import FAINT

ROUTE = frozenset({101, 112, 120, 152})


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_tract_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_tract_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def picked_ids(view, step=12) -> set[int]:
    width, height = view.ren_win.GetSize()
    found = {view.structure_at(x, y) for y in range(step, height, step)
             for x in range(step, width, step)}
    return found - {None}


def test_focus_keeps_geometry_only_and_signals_changes_once(window):
    seen = []
    window.state.focus_changed.connect(seen.append)
    window.state.set_focus([101, 112, 2])
    window.state.set_focus([112, 101])
    assert window.state.focus == {101, 112} and len(seen) == 1
    assert window.state.in_focus(101) and not window.state.in_focus(102)
    window.state.set_focus(None)
    assert window.state.focus is None and seen[-1] is None and window.state.in_focus(102)


def test_emphasis_rides_on_the_selection_and_a_plain_select_clears_it(window):
    seen = []
    window.state.selection_changed.connect(seen.append)
    window.state.select(101, emphasis=[101, 120, 2])
    assert window.state.emphasis == (101, 120)
    assert window.state.highlighted_ids() == [101, 120]
    window.state.select(101)
    assert window.state.emphasis == () and window.state.highlighted_ids() == [101]
    assert seen == [101, 101]


def test_focus_fades_and_unpicks_everything_else_in_3d(window):
    view = window.view
    window.state.set_focus(ROUTE)
    assert view.attributes.GetBlockOpacity(view.blocks[101]) == 1.0
    assert view.attributes.GetBlockOpacity(view.blocks[102]) == pytest.approx(FAINT)
    assert view.attributes.GetBlockPickability(view.blocks[101])
    assert not view.attributes.GetBlockPickability(view.blocks[102])
    window.state.set_focus(None)
    assert not view.attributes.HasBlockOpacities()
    assert not view.attributes.HasBlockPickabilities()


def test_picking_never_returns_a_structure_outside_the_focus(window):
    window.state.set_focus({112, 120})
    window.view.render()
    picked = picked_ids(window.view)
    assert picked and picked <= {112, 120}


def test_tracts_built_after_the_focus_take_it(window):
    view = window.view
    window.state.set_focus(ROUTE)
    window.state.set_hidden([151, 152], False)
    assert view.tract_actors[151].GetProperty().GetOpacity() == pytest.approx(FAINT)
    assert view.tract_actors[152].GetProperty().GetOpacity() == 1.0


def test_the_overlay_follows_the_emphasis(window):
    window.state.select(110, emphasis=[112])
    assert window.view.overlay_ids == [112]


def test_slices_colour_and_pick_only_the_focus(window):
    window.state.set_slice("axial", 20.0)
    window.state.set_hidden([102], True)
    unlabelled = window.slices.image[19, 28, :3].copy()
    window.state.set_hidden([102], False)
    assert window.slices.structure_at_pixel(19, 28) == 102
    window.state.set_focus(ROUTE)
    assert window.slices.image[19, 28, :3].tolist() == unlabelled.tolist()
    assert window.slices.structure_at_pixel(19, 28) is None
    assert window.slices.structure_at_pixel(19, 12) == 101


def test_centring_uses_the_emphasis(window):
    window.state.select(110, emphasis=[112])
    window.state.set_slice("axial", 20.0)
    window.slices.centre_on_selection()
    assert window.state.slice_mm == -12.0
