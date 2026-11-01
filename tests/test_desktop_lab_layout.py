import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import GAP
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def open_lab(qapp, atlas, tmp_path, size):
    window = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite")
    window.show()
    for _ in range(3):
        window.resize(*size)
        qapp.processEvents()
    window.workspaces.switch("Lab")
    for _ in range(3):
        qapp.processEvents()
    return window


def projected_box(view, bounds):
    renderer = view.renderer
    xs, ys = [], []
    for x in bounds[0:2]:
        for y in bounds[2:4]:
            for z in bounds[4:6]:
                renderer.SetWorldPoint(x, y, z, 1.0)
                renderer.WorldToDisplay()
                dx, dy, _ = renderer.GetDisplayPoint()
                xs.append(dx)
                ys.append(dy)
    ratio = view.devicePixelRatioF()
    height = view.height()
    return (height - max(ys) / ratio, height - min(ys) / ratio, min(xs) / ratio, max(xs) / ratio)


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_lab(qapp, toy_lab_atlas, tmp_path, (1440, 900))
    yield w
    w.close()


def test_the_cards_float_over_the_view(window):
    viewport = window.viewport
    strip, stack = viewport.strip, viewport.stack
    assert strip.parent() is viewport and strip.isVisible()
    assert stack.width() == viewport.width()
    assert stack.geometry().contains(strip.geometry())
    assert strip.geometry().right() == stack.geometry().right() - GAP["medium"]
    assert strip.geometry().top() == stack.geometry().top() + GAP["medium"]


def test_the_brain_fills_the_view_in_the_lab(window):
    view = window.view
    top, bottom, _left, right = projected_box(view, window.lab.brain.brain_bounds())
    assert bottom - top >= 0.5 * view.height()
    strip_left = window.viewport.strip.geometry().left() - view.mapTo(window.viewport, view.rect().topLeft()).x()
    assert right <= strip_left


def test_the_reset_button_frames_the_brain_again(window):
    view = window.view
    view.camera.Zoom(0.3)
    view.reset_view()
    top, bottom, _left, _right = projected_box(view, window.lab.brain.brain_bounds())
    assert bottom - top >= 0.5 * view.height()


def test_leaving_the_lab_restores_the_usual_framing(window, qapp):
    window.workspaces.switch("Explore")
    qapp.processEvents()
    assert window.view.home() is None
    assert window.view.camera.GetWindowCenter() == (0.0, 0.0)
    assert not window.viewport.strip.isVisible()


def test_narrow_cards_show_one_line_and_still_open_the_part(qapp, toy_lab_atlas, tmp_path):
    window = open_lab(qapp, toy_lab_atlas, tmp_path, (1000, 760))
    brain = window.lab.brain
    key = brain.strip_keys()[0]
    card = brain.strip_button(key)
    assert window.viewport.cards_compact()
    assert card.title.text().startswith(f"{brain.document.model.part(key).name} · ")
    assert card.detail.isHidden()
    card.click()
    assert window.lab.document.selection == ("part", key)
    window.close()


def test_the_circuit_view_hides_the_cards(window, qapp):
    window.viewport.show_circuit(True)
    qapp.processEvents()
    assert not window.viewport.strip.isVisible()
    window.viewport.show_circuit(False)
    qapp.processEvents()
    assert window.viewport.strip.isVisible()


def test_a_compact_card_leaves_out_the_value_name(qapp, toy_lab_atlas, tmp_path):
    window = open_lab(qapp, toy_lab_atlas, tmp_path, (1000, 760))
    brain = window.lab.brain
    for key in brain.strip_keys():
        part = brain.document.model.part(key)
        if part.values:
            name = brain.document.simulator.values[part.values[0]].name
            title = brain.strip_button(key).title.text()
            assert title.startswith(f"{part.name} · ") and f"· {name} " not in title, title
    window.close()


def test_a_compact_card_keeps_its_tone(qapp, toy_lab_atlas, tmp_path):
    window = open_lab(qapp, toy_lab_atlas, tmp_path, (1000, 760))
    card = window.lab.brain.strip_button(window.lab.brain.strip_keys()[0])
    card.set_tone("raised")
    assert card.title.property("tone") == "raised"
    card.set_compact(False)
    assert card.title.property("tone") in (None, "")
    window.close()
