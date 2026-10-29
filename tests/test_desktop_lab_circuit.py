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
    assert "↑" in circuit.part_label("b") and "×" in circuit.part_label("b")


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
