import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_atlas.lesions import Lesion
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, atlas, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    yield w
    qapp.processEvents()
    w.close()


def label_lesion(atlas, structure_id):
    volume = atlas.volumes[0]
    return Lesion.empty(atlas).with_mask(volume.name, volume.data == structure_id)


def test_the_lesion_workspace_is_listed_and_has_its_panels(window, qapp):
    lesion = window.lesion
    assert lesion is not None and window.workspaces.button("Lesion").isVisibleTo(window)
    window.workspaces.switch("Lesion")
    qapp.processEvents()
    assert lesion.tools_group.keys() == ["place", "cases"]
    assert lesion.results_group.keys() == ["deficits", "hit"]
    assert lesion.tools_group.isVisible() and lesion.results_group.isVisible()
    assert window.slices_group.isVisible() and not window.structures_group.isVisible()
    window.workspaces.switch("Explore")
    qapp.processEvents()
    assert not lesion.tools_group.isVisible() and not lesion.results_group.isVisible()
    assert window.structures_group.isVisible()


def test_entering_and_leaving_restores_the_window(window, qapp):
    state = window.state
    state.select(101)
    state.set_hidden([102], True)
    window.workspaces.switch("Lesion")
    state.select(111)
    state.set_hidden([102], False)
    window.workspaces.switch("Explore")
    qapp.processEvents()
    assert state.selected == 101 and state.is_hidden(102)


def test_the_document_keeps_an_undo_step_per_lesion_and_a_fresh_report(window):
    doc = window.lesion.document
    atlas = window.state.atlas
    assert doc.lesion.is_empty and doc.report.deficits == ()
    doc.set_lesion(label_lesion(atlas, 101), "Brush")
    assert [d.step for d in doc.report.deficits if d.route == "loop"] == [0]
    assert doc.undo.count() == 1
    doc.clear()
    assert doc.lesion.is_empty and doc.undo.count() == 2
    doc.undo.undo()
    assert not doc.lesion.is_empty and np.any(doc.lesion.masks["brain"])
    doc.undo.undo()
    assert doc.lesion.is_empty


def test_an_atlas_without_pathways_has_no_lesion_workspace(qapp, toy_atlas, tmp_path):
    w = open_window(qapp, toy_atlas, tmp_path)
    try:
        assert w.lesion is None and not w.workspaces.button("Lesion").isVisibleTo(w)
        w.workspaces.switch("Lesion")
        assert w.workspaces.current == "Explore"
    finally:
        w.close()
