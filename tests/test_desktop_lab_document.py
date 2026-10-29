from itertools import pairwise

import pytest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_lab.experiment import Block

DAY = 1440.0


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def test_a_new_document_is_a_healthy_day(doc):
    assert doc.experiment.blocks == () and doc.experiment.length == DAY
    assert doc.run is not None and doc.normal is not None and doc.error == ""
    assert doc.playhead == 0.0 and doc.selection is None and not doc.is_modified()


def test_every_edit_is_one_undo_step(doc):
    history = [doc.experiment]
    doc.add_block("pill", 100.0)
    doc.move_block(0, 200.0)
    doc.add_block("stress", 300.0)
    doc.stretch_block(1, 90.0)
    doc.set_option(0, "dose", 3.0)
    doc.add_block("remove_b", 0.0)
    doc.set_mode(2, "from a time")
    doc.delete_block(2)
    doc.set_value("k", 2.0)
    doc.reset_value("k")
    doc.set_length(2 * DAY)
    assert doc.undo.count() == 11
    seen = [doc.experiment]
    while doc.undo.canUndo():
        doc.undo.undo()
        seen.append(doc.experiment)
    assert seen[-1] == history[0]
    assert all(a != b for a, b in pairwise(seen))
    assert doc.undo.undoText() == ""
    doc.undo.redo()
    assert [b.experiment for b in doc.experiment.blocks] == ["pill"]


def test_new_blocks_take_their_defaults(doc):
    doc.add_block("pill", 100.0)
    doc.add_block("stress", 200.0)
    doc.add_block("remove_b", 0.0)
    doc.add_block("pill_test", 300.0)
    pill, stress, removal, test = doc.experiment.blocks
    assert pill == Block("pill", 100.0, None, (("dose", 1.0),), "from a time")
    assert stress.length == 60.0 and stress.option_map == {"strength": 1.0}
    assert removal.mode == "present" and test.mode == "from a time"


def test_runs_follow_the_experiment(doc):
    before = doc.run
    changes = []
    doc.changed.connect(lambda: changes.append(1))
    doc.add_block("pill", 100.0)
    assert doc.run is not before and doc.run.experiment == doc.experiment and changes


def test_a_settle_error_is_kept_as_a_message_not_raised(doc, monkeypatch):
    from cns_lab.engine import SettleError

    def broken(_experiment):
        raise SettleError()

    monkeypatch.setattr(doc.simulator, "run", broken)
    doc.set_value("k", 0.1)
    assert doc.run is None and doc.error == "The model cannot settle with these values."


def test_blocks_are_clamped_inside_the_run(doc):
    doc.add_block("pill", 5000.0)
    assert doc.experiment.blocks[0].start == DAY - 1
    doc.move_block(0, -50.0)
    assert doc.experiment.blocks[0].start == 0.0
    doc.add_block("stress", 1400.0)
    assert doc.experiment.blocks[1].length == 40.0
    doc.stretch_block(1, 0.0)
    assert doc.experiment.blocks[1].length == 1.0
    doc.set_length(1000.0)
    assert doc.experiment.blocks[1].start == 999.0 and doc.experiment.blocks[1].length == 1.0


def test_values_and_options_stay_in_their_ranges(doc):
    doc.set_value("k", 99.0)
    assert doc.experiment.value_map == {"k": 10.0}
    doc.add_block("pill", 10.0)
    doc.set_option(0, "dose", -4.0)
    assert doc.experiment.blocks[0].option_map == {"dose": 0.0}
    doc.reset_values()
    assert doc.experiment.values == ()


def test_only_present_experiments_can_be_present(doc):
    doc.add_block("pill", 10.0)
    doc.set_mode(0, "present")
    assert doc.experiment.blocks[0].mode == "from a time" and doc.undo.count() == 1


def test_a_weeks_experiment_asks_for_a_longer_run(doc):
    asked = []
    doc.wants_longer.connect(asked.append)
    doc.add_block("course", 10.0)
    assert asked == [4 * 7 * DAY]
    doc.set_length(4 * 7 * DAY)
    doc.add_block("course", 20.0)
    assert asked == [4 * 7 * DAY]


def test_playhead_selection_and_snapshot(doc):
    moved, chosen = [], []
    doc.playhead_moved.connect(moved.append)
    doc.selection_changed.connect(chosen.append)
    doc.set_playhead(5000.0)
    assert doc.playhead == DAY and moved == [DAY]
    doc.select(("part", "a"))
    assert doc.selection == ("part", "a") and chosen == [("part", "a")]
    doc.take_snapshot()
    assert doc.snapshot is doc.run
    doc.add_block("pill", 10.0)
    assert doc.snapshot is not doc.run
    doc.clear_snapshot()
    assert doc.snapshot is None


def test_deleting_the_selected_block_clears_the_selection(doc):
    doc.add_block("pill", 10.0)
    doc.select(("block", 0))
    doc.delete_block(0)
    assert doc.selection is None


def test_new_starts_over_and_is_clean(doc):
    doc.add_block("pill", 10.0)
    assert doc.is_modified()
    doc.new()
    assert doc.experiment.blocks == () and not doc.is_modified() and doc.undo.count() == 0


def test_any_engine_failure_shows_the_plain_message_and_no_stale_runs(doc, monkeypatch):
    from cns_lab.solver import SolverError

    def broken(_experiment):
        raise SolverError("step too small at 812.345 min")

    monkeypatch.setattr(doc.simulator, "run", broken)
    doc.set_length(2 * DAY)
    assert doc.error == "The model cannot settle with these values."
    assert doc.run is None and doc.normal is None


def test_loading_keeps_blocks_inside_the_run(doc):
    outside = doc.experiment.replace(blocks=(Block("stress", 5000.0, 900.0, (("strength", 1.0),)),))
    doc.load(outside, None)
    (block,) = doc.experiment.blocks
    assert block.start == DAY - 1 and block.length == 1.0
