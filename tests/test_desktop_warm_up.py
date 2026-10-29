import sys
import time

import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, root, tmp_path):
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite")
    window.resize(1000, 800)
    window.show()
    qapp.processEvents()
    return window


def wait_for_warm_up(qapp, window, seconds=10.0):
    deadline = time.perf_counter() + seconds
    while not window.warm_up_done and time.perf_counter() < deadline:
        qapp.processEvents()
    return window.warm_up_done


def test_warm_up_loads_every_volume_and_centre_table(qapp, toy_spine_atlas, tmp_path):
    window = open_window(qapp, toy_spine_atlas, tmp_path)
    assert wait_for_warm_up(qapp, window)
    atlas = window.state.atlas
    volumes = [*atlas.volumes, *atlas.templates.values(), *atlas.fills.values()]
    assert len(volumes) >= 5 and all(v._data is not None for v in volumes)
    assert set(window.slices._centre_tables) == {v.name for v in atlas.volumes}
    window.close()


def act(qapp, window):
    window.state.select(200)
    window.state.set_slice_volume("spine")
    window.slices.centre_on_selection()
    qapp.processEvents()
    return window.state.selected, window.state.slice_volume, window.state.slice_axis, \
        window.state.slice_mm


def test_acting_during_warm_up_gives_the_same_result(qapp, toy_spine_atlas, tmp_path):
    early = open_window(qapp, toy_spine_atlas, tmp_path / "a")
    assert not early.warm_up_done
    during = act(qapp, early)
    early.close()
    late = open_window(qapp, toy_spine_atlas, tmp_path / "b")
    assert wait_for_warm_up(qapp, late)
    assert act(qapp, late) == during
    late.close()


def test_closing_during_warm_up_is_clean(qapp, toy_spine_atlas, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *exc: errors.append(exc))
    window = open_window(qapp, toy_spine_atlas, tmp_path)
    window.close()
    deadline = time.perf_counter() + 1.0
    while time.perf_counter() < deadline:
        qapp.processEvents()
    assert errors == [] and not window.warm_up_done


def test_an_atlas_without_spine_or_template_warms_up(qapp, toy_atlas, tmp_path):
    window = open_window(qapp, toy_atlas, tmp_path)
    assert wait_for_warm_up(qapp, window)
    window.close()


def frame(view):
    import numpy as np
    from vtkmodules.util.numpy_support import vtk_to_numpy
    from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter

    grab = vtkWindowToImageFilter()
    grab.SetInput(view.ren_win)
    grab.ShouldRerenderOff()
    grab.ReadFrontBufferOff()
    grab.Update()
    return np.asarray(vtk_to_numpy(grab.GetOutput().GetPointData().GetScalars()), dtype=int)


def test_warm_up_leaves_the_selection_glow_on_screen(qapp, toy_spine_atlas, tmp_path):
    import numpy as np

    window = open_window(qapp, toy_spine_atlas, tmp_path)
    window.state.select(101)
    qapp.processEvents()
    window.view.render()
    before = frame(window.view)
    assert wait_for_warm_up(qapp, window)
    qapp.processEvents()
    assert np.abs(before - frame(window.view)).sum() == 0
    window.close()


def test_warm_up_starts_only_after_the_first_frame(qapp, toy_spine_atlas, tmp_path):
    window = MainWindow(Atlas.open(toy_spine_atlas), progress_path=tmp_path / "progress.sqlite")
    window.resize(1000, 800)
    jobs = len(window._warm_up._jobs)
    assert window._warm_up.started_after_render is None and len(window._warm_up._jobs) == jobs
    window.show()
    for _ in range(5):
        qapp.processEvents()
    drawn = window.view.render_count
    window.view.ren_win.Render()
    qapp.processEvents()
    started = window._warm_up.started_after_render
    assert started is not None and 1 <= started <= drawn + 1
    window.close()
