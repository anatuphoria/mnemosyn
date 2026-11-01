import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from cns_atlas import Atlas
from cns_desktop.lab.circuit import CircuitView
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.viewport import Viewport


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def circuit(qapp, toy_lab_atlas):
    doc = LabDocument(Atlas.open(toy_lab_atlas), "toy")
    view = CircuitView(doc)
    view.resize(800, 400)
    view.show()
    qapp.processEvents()
    yield view
    view.close()


def test_every_part_and_arrow_is_drawn(circuit):
    assert set(circuit.part_items) == {"a", "b", "body"}
    assert set(circuit.arrow_items) == {"fb", "make_x", "make_y"}
    assert circuit.part_label("a") == "Alpha\nX 11.2 ng/mL"
    assert circuit.part_label("b").startswith("Beta\nY ")


def test_relative_values_show_their_direction(circuit):
    circuit.document.add_block("pill", 0.0)
    circuit.document.set_playhead(5.0)
    assert "↑" in circuit.part_label("b") and "× healthy" in circuit.part_label("b")


def test_arrow_width_follows_the_run(circuit):
    normal = circuit.arrow_width("make_y")
    assert normal == pytest.approx(1 + 5 * 1 / 4)
    circuit.document.add_block("remove_b", 0.0)
    assert circuit.arrow_width("make_y") < normal
    assert circuit.arrow_width("fb") > normal


def test_a_removed_part_is_dashed(circuit):
    assert not circuit.is_dashed("body")
    circuit.document.add_block("remove_b", 0.0)
    assert circuit.is_dashed("body") and circuit.is_dashed("make_y")


def test_clicking_selects_parts_and_links(qapp, circuit):
    rect = circuit.mapFromScene(circuit.part_items["a"].sceneBoundingRect().center())
    QTest.mouseClick(circuit.viewport(), Qt.MouseButton.LeftButton, pos=rect)
    assert circuit.document.selection == ("part", "a")
    line = circuit.arrow_items["make_x"].line()
    middle = circuit.mapFromScene((line.p1() + line.p2()) / 2)
    QTest.mouseClick(circuit.viewport(), Qt.MouseButton.LeftButton, pos=middle)
    assert circuit.document.selection == ("link", "make_x")


def test_the_viewport_switches_pages(qapp, circuit):
    brain = QLabel("brain")
    viewport = Viewport(brain)
    circuit = CircuitView(circuit.document)
    viewport.add_circuit(circuit)
    viewport.show_lab_parts(True)
    viewport.show_circuit(True)
    assert viewport.stack.currentWidget() is circuit and viewport.showing_circuit
    viewport.show_circuit(False)
    assert viewport.stack.currentWidget() is brain


def test_an_arrow_passes_through_its_via_parts(qapp, toy_lab_atlas):
    from dataclasses import replace

    doc = LabDocument(Atlas.open(toy_lab_atlas), "toy")
    terms = tuple(replace(t, via=("a",)) if t.key == "make_y" else t for t in doc.model.terms)
    doc.model = replace(doc.model, terms=terms)
    view = CircuitView(doc)
    centre = {k: item.rect().center() for k, item in view.part_items.items()}
    ends = [(line.line().p1(), line.line().p2()) for line in view.segments("make_y")]
    assert ends == [(centre["b"], centre["a"]), (centre["a"], centre["body"])]
    widths = {line.pen().widthF() for line in view.segments("make_y")}
    assert widths == {view.arrow_width("make_y")}
    view.close()


def test_a_long_value_wraps_inside_its_box(circuit):
    from dataclasses import replace

    from cns_desktop.lab.circuit import BOX_H, BOX_W

    values = circuit.document.simulator.values
    values["x"] = replace(values["x"], name="Alpha hormone level today")
    circuit.refresh()
    text = circuit.part_texts["a"]
    assert text.boundingRect().width() <= BOX_W - 16
    assert text.boundingRect().height() <= BOX_H - 8
    assert circuit.part_label("a").endswith("\n11.2 ng/mL")


def test_the_circuit_fits_without_scrollbars(circuit, qapp):
    for size in ((800, 400), (420, 180), (1200, 300)):
        circuit.resize(*size)
        qapp.processEvents()
        assert not circuit.horizontalScrollBar().isVisible()
        assert not circuit.verticalScrollBar().isVisible()


def test_a_smaller_circuit_after_a_larger_one_has_no_scrollbars(circuit, qapp):
    from PySide6.QtCore import QRectF

    circuit.scene().addRect(QRectF(4000.0, 0.0, 10.0, 10.0))
    assert circuit.scene().sceneRect().right() > 4000.0
    circuit.populate()
    qapp.processEvents()
    assert circuit.sceneRect() == circuit.scene().itemsBoundingRect()
