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


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_labels_at_the_same_place_do_not_cover_each_other(window, qapp):
    from cns_desktop.lab.brain_overlay import BrainOverlay

    overlay = BrainOverlay(window.view)
    centre = window.view.centre_of(111)
    overlay.show({111: ("Alpha nucleus · X 1.2 units", (255, 255, 255)),
                  101: ("Beta nucleus", (255, 255, 255)),
                  102: ("Gamma · Y 3 units", (255, 255, 255))},
                 {111: centre, 101: centre, 102: centre + 0.5})
    window.view.render()
    qapp.processEvents()
    boxes = list(overlay.boxes().values())
    assert len(boxes) == 3
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not overlaps(a, b), (a, b)
    overlay.clear()


def test_a_label_starts_past_its_structure_on_screen(window, qapp):
    import itertools

    doc, brain = lab_of(window)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    window.view.render()
    qapp.processEvents()
    renderer = window.view.renderer
    low, high = window.view.extent_of(111)
    right = 0.0
    for corner in itertools.product(*zip(low, high)):
        renderer.SetWorldPoint(*corner, 1.0)
        renderer.WorldToDisplay()
        right = max(right, renderer.GetDisplayPoint()[0])
    assert brain.overlay.boxes()[111][0] >= right


def test_labels_draw_in_a_layer_above_the_scene(window):
    doc, brain = lab_of(window)
    brain.activate()
    doc.add_block("remove_b", 0.0)
    actor = brain.overlay.actors[111]
    layer = brain.overlay.renderer
    assert layer.HasViewProp(actor) and not window.view.renderer.HasViewProp(actor)
    assert layer.GetLayer() > window.view.outline.renderer.GetLayer()
    assert layer.GetActiveCamera() is window.view.renderer.GetActiveCamera()
    again = lab_of(window)[1]
    assert again.overlay.renderer is layer
