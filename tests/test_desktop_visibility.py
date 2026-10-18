import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_spine_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_spine_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1000, 800)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def test_hiding_a_large_group_renders_once(window, qapp):
    view, state = window.view, window.state
    ids = [i for i in state.geometry_ids if not state.is_tract(i)]
    before = view.render_count
    state.set_hidden(ids, True)
    qapp.processEvents()
    assert view.render_count == before + 1
    assert not any(view.is_drawn(i) for i in ids)
    before = view.render_count
    state.set_hidden(ids, False)
    qapp.processEvents()
    assert view.render_count == before + 1
    assert all(view.is_drawn(i) for i in ids)


def test_showing_tracts_with_others_builds_them_once(window, qapp):
    view, state = window.view, window.state
    state.set_hidden(state.geometry_ids, False)
    qapp.processEvents()
    assert view.tract_builds == 1
    assert all(view.is_drawn(i) for i in state.tract_ids)


@pytest.fixture
def chunked(qapp, toy_spine_atlas, tmp_path, monkeypatch):
    import cns_desktop.views.chunks as chunks

    monkeypatch.setattr(chunks, "CHUNK_FACES", 1)
    w = MainWindow(Atlas.open(toy_spine_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1000, 800)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def test_every_structure_gets_its_own_chunk_when_chunks_are_tiny(chunked):
    view = chunked.view
    assert len(view.chunks.actors) == len(view.ids) > 1
    assert view.chunks.block_count() == len(view.ids)


def test_hiding_a_whole_chunk_switches_it_off_without_touching_its_blocks(chunked, qapp):
    view, state = chunked.view, chunked.state
    first = view.ids[0]
    attributes = view.chunks.attributes_for(first)
    stamp = attributes.GetMTime()
    state.set_hidden([first], True)
    qapp.processEvents()
    assert not view.is_drawn(first) and attributes.GetMTime() == stamp
    state.set_hidden([first], False)
    qapp.processEvents()
    assert view.is_drawn(first) and attributes.GetMTime() == stamp


def test_picking_works_across_chunks(chunked, qapp):
    view = chunked.view
    for structure_id in view.ids:
        centre = np.asarray(view.blocks[structure_id].center)
        view.camera_position = [tuple(centre + (0, 0, 400)), tuple(centre), (0, 1, 0)]
        view.renderer.ResetCameraClippingRange()
        view.render()
        x, y = view.renderer.GetSize()
        found = view.structure_at(x // 2, y // 2)
        assert found is not None and found in view.ids


def test_moving_the_slice_reuses_the_plane(window, qapp):
    view, state = window.view, window.state
    state.set_slice("axial", 0.0)
    qapp.processEvents()
    data = view.plane.GetMapper().GetInput()
    state.set_slice("axial", 7.0)
    qapp.processEvents()
    assert view.plane.GetMapper().GetInput() is data
    low, high = view.plane.GetBounds()[4:6]
    assert low == pytest.approx(state.slice_mm) and high == pytest.approx(state.slice_mm)
    assert state.slice_mm != 0.0
    state.set_slice("coronal", -3.0)
    qapp.processEvents()
    assert view.plane.GetBounds()[2] == pytest.approx(state.slice_mm)
