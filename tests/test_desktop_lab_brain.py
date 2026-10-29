import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.brain_overlay import LabBrain, RAISED
from cns_desktop.lab.document import LabDocument
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_lab_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    qapp.processEvents()
    w.close()


def lab_of(window):
    doc = LabDocument(window.state.atlas, "toy")
    brain = LabBrain(doc, window.view, window.viewport, window.state)
    return doc, brain


def colour(window, structure_id):
    attributes = window.view.chunks.attributes_for(structure_id)
    return tuple(round(c, 3) for c in attributes.GetBlockColor(window.view.blocks[structure_id]))


def test_model_structures_are_coloured_and_labelled(window):
    doc, brain = lab_of(window)
    own = colour(window, 111)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    assert colour(window, 111) != own
    assert set(brain.overlay.labels) == {111, 101}
    assert brain.overlay.labels[111].startswith("Alpha · X")
    assert window.state.focus == {111, 101, 102}
    assert colour(window, 102) == colour(window, 101)


def test_raised_values_lean_toward_the_raised_colour(window):
    doc, brain = lab_of(window)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    red = colour(window, 111)[0]
    assert red > colour(window, 101)[0] or red == pytest.approx(RAISED[0] / 255, abs=0.2)


def test_leaving_restores_colours_and_focus(window):
    doc, brain = lab_of(window)
    own = colour(window, 111)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    brain.deactivate()
    assert colour(window, 111) == own and window.state.focus is None
    assert brain.overlay.labels == {}


def test_selection_is_shared_between_the_brain_and_the_lab(window):
    doc, brain = lab_of(window)
    brain.activate()
    doc.select(("part", "a"))
    assert window.state.selected == 111
    window.state.select(102)
    assert doc.selection == ("part", "b")
    doc.select(("part", "a"))
    doc.select(("part", "b"))
    assert window.state.selected == 100
    brain.deactivate()
    window.state.select(111)
    assert doc.selection == ("part", "b")


def test_a_part_without_a_shape_lives_in_the_body_strip(window, monkeypatch):
    atlas = window.state.atlas
    real = atlas.has_mesh
    monkeypatch.setattr(atlas, "has_mesh", lambda i: False if i in (101, 102) else real(i))
    doc, brain = lab_of(window)
    brain.activate()
    assert brain.strip_keys() == ["b", "body"]
    assert set(brain.overlay.labels) == {111}
    brain.strip_button("body").click()
    assert doc.selection == ("part", "body")


def test_a_failed_run_shows_neutral_labels(window, monkeypatch):
    from cns_lab.solver import SolverError

    doc, brain = lab_of(window)
    own = colour(window, 111)
    brain.activate()
    doc.add_block("remove_b", 0.0)

    def broken(_experiment):
        raise SolverError("broken")

    monkeypatch.setattr(doc.simulator, "run", broken)
    doc.set_value("k", 2.0)
    assert doc.run is None
    assert brain.overlay.labels[111] == "Alpha" and colour(window, 111) == own


def test_a_removed_part_says_so_in_the_strip_and_labels(window):
    doc, brain = lab_of(window)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    assert brain.strip_button("body").text() == "Body gland\nremoved"
    assert brain.strip_button("body").toolTip() == "Body gland · removed"
    assert "e-" not in brain.overlay.labels[111]
