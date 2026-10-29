import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.experiments_panel import MIME, ExperimentsPanel
from cns_desktop.lab.model_panel import ModelPanel


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def children(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


def test_experiments_are_grouped_in_model_order(doc):
    panel = ExperimentsPanel(doc)
    groups = [panel.topLevelItem(i) for i in range(panel.topLevelItemCount())]
    assert [g.text(0) for g in groups] == ["Remove or cut", "Drugs", "Stressors", "Tests"]
    assert children(groups[1]) == ["Y pill", "Daily Y course"]
    assert children(groups[3]) == ["Y suppression test"]
    assert groups[1].child(0).toolTip(0) == "A dose of Y."


def test_double_click_adds_at_the_playhead(doc):
    panel = ExperimentsPanel(doc)
    doc.set_playhead(300.0)
    panel.itemDoubleClicked.emit(panel.item_for("pill"), 0)
    assert [(b.experiment, b.start) for b in doc.experiment.blocks] == [("pill", 300.0)]
    panel.itemDoubleClicked.emit(panel.topLevelItem(0), 0)
    assert len(doc.experiment.blocks) == 1


def test_dragging_carries_the_experiment_key(doc):
    panel = ExperimentsPanel(doc)
    data = panel.mimeData([panel.item_for("pill_test")])
    assert bytes(data.data(MIME)) == b"pill_test"
    assert not panel.topLevelItem(0).flags() & panel.topLevelItem(0).flags().ItemIsDragEnabled


def test_model_values_cannot_leave_their_range(doc):
    panel = ModelPanel(doc)
    spin = panel.spin("k")
    assert (spin.minimum(), spin.maximum(), spin.value()) == (0.1, 10.0, 1.0)
    assert spin.suffix() == " model units"
    spin.setValue(99.0)
    spin.editingFinished.emit()
    assert doc.experiment.value_map == {"k": 10.0}


def test_edited_values_are_marked_and_reset(doc):
    panel = ModelPanel(doc)
    assert not panel.is_marked("k")
    panel.spin("k").setValue(3.0)
    panel.spin("k").editingFinished.emit()
    assert doc.experiment.value_map == {"k": 3.0} and panel.is_marked("k")
    panel.reset_button("k").click()
    assert doc.experiment.values == () and not panel.is_marked("k")
    assert panel.spin("k").value() == 1.0
    panel.spin("w").setValue(0.5)
    panel.spin("w").editingFinished.emit()
    doc.undo.undo()
    assert panel.spin("w").value() == pytest.approx(0.1)
    panel.spin("w").setValue(0.5)
    panel.spin("w").editingFinished.emit()
    panel.reset_all.click()
    assert doc.experiment.values == ()


def test_unchanged_spin_boxes_add_no_undo_step(doc):
    panel = ModelPanel(doc)
    panel.spin("k").editingFinished.emit()
    assert doc.undo.count() == 0


def test_rows_show_name_and_source(doc):
    panel = ModelPanel(doc)
    assert panel.row_text("k") == ("Feedback halfway point", "Where Y holds back half of X.",
                                   "Author A (2020)")
