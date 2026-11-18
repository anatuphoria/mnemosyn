import pytest

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.views.brain_view import FAINT

ROUTE = frozenset({101, 112, 120, 152})


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
    assert view.chunks.attributes_for(101).GetBlockOpacity(view.blocks[101]) == 1.0
    assert view.chunks.attributes_for(102).GetBlockOpacity(view.blocks[102]) == pytest.approx(FAINT)
    assert view.chunks.attributes_for(101).GetBlockPickability(view.blocks[101])
    assert not view.chunks.attributes_for(102).GetBlockPickability(view.blocks[102])
    window.state.set_focus(None)
    assert not view.chunks.has_opacities()
    assert not view.chunks.has_pickabilities()


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


def test_a_selection_outside_the_focus_is_not_outlined(window):
    window.state.select(102)
    assert window.view.overlay_ids == [102]
    window.state.set_focus([101, 112])
    assert window.view.overlay_ids == []
    window.state.set_focus(None)
    assert window.view.overlay_ids == [102]


def test_a_new_selection_outside_the_focus_is_outlined(window):
    window.state.set_focus([101, 112])
    window.state.select(102)
    assert window.view.overlay_ids == [102]


def drawn_in_focus(view, ids):
    return frozenset(i for i in ids if view.chunks.has(i))


def test_focused_parts_are_drawn_again_above_the_faded_ones(window):
    view = window.view
    window.state.set_focus(ROUTE)
    assert view.front.shown == drawn_in_focus(view, ROUTE) and view.front.shown
    assert view.front.renderer.GetLayer() < view.outline.renderer.GetLayer()
    window.state.set_focus(None)
    assert view.front.shown == frozenset()


def test_the_front_copies_follow_lab_colours_and_hiding(window):
    view = window.view
    window.state.set_focus(ROUTE)
    target = min(drawn_in_focus(view, ROUTE))
    view.set_lab_colors({target: (1.0, 0.0, 0.0)})
    assert view.front.color_of(target) == pytest.approx((1.0, 0.0, 0.0))
    view.set_lab_colors({target: None})
    assert view.front.color_of(target) == pytest.approx(view.chunks.color_of(target))
    window.state.set_hidden([target], True)
    assert target not in view.front.shown
    window.state.set_hidden([target], False)
    assert target in view.front.shown


def test_the_front_layer_steps_aside_when_the_grey_is_dimmed(window):
    view = window.view
    window.state.set_focus(ROUTE)
    view.set_grey_opacity(0.15)
    assert view.front.shown == frozenset()
    view.set_grey_opacity(1.0)
    assert view.front.shown == drawn_in_focus(view, ROUTE)


def shown_image(view):
    import numpy as np
    from vtkmodules.util.numpy_support import vtk_to_numpy
    from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter

    grab = vtkWindowToImageFilter()
    grab.SetInput(view.ren_win)
    grab.ShouldRerenderOff()
    grab.ReadFrontBufferOff()
    grab.Update()
    image = grab.GetOutput()
    return np.asarray(vtk_to_numpy(image.GetPointData().GetScalars()), dtype=int)


def screen_point(view, structure_id):
    low, high = view.blocks[structure_id].GetBounds()[::2], view.blocks[structure_id].GetBounds()[1::2]
    view.renderer.SetWorldPoint(*[(a + b) / 2 for a, b in zip(low, high)], 1.0)
    view.renderer.WorldToDisplay()
    x, y, _ = view.renderer.GetDisplayPoint()
    return int(x), int(y)


def test_a_click_leaves_a_whole_frame_behind_not_the_pickers(window):
    view = window.view
    target = next(i for i in sorted(view.blocks) if view.chunks.has(i)
                  and view.structure_at(*screen_point(view, i)) == i)
    view.render()
    before = shown_image(view)
    view.pick_at(*screen_point(view, target))
    after = shown_image(view)
    view.render()
    settled = shown_image(view)
    assert window.state.selected == target
    lit = (settled.sum(axis=1) > 30).sum()
    assert (after.sum(axis=1) > 30).sum() >= 0.9 * lit
    assert before.shape == after.shape
