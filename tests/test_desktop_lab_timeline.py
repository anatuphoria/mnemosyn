import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.experiments_panel import MIME
from cns_desktop.lab.timeline import LABEL_WIDTH, RULER_HEIGHT, Timeline

DAY = 1440.0


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def timeline(qapp, toy_lab_atlas):
    doc = LabDocument(Atlas.open(toy_lab_atlas), "toy")
    widget = Timeline(doc)
    widget.resize(1000, 260)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()


def mouse(widget, kind, pos, button=Qt.MouseButton.LeftButton):
    buttons = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseButtonRelease else button
    event = QMouseEvent(kind, QPointF(pos), QPointF(widget.mapToGlobal(pos)), button, buttons,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


def drag(widget, start, end):
    mouse(widget, QMouseEvent.Type.MouseButtonPress, start)
    mouse(widget, QMouseEvent.Type.MouseMove, QPoint((start.x() + end.x()) // 2, end.y()))
    mouse(widget, QMouseEvent.Type.MouseMove, end)
    mouse(widget, QMouseEvent.Type.MouseButtonRelease, end)


def drop(widget, key, x):
    data = QMimeData()
    data.setData(MIME, key.encode())
    event = QDropEvent(QPointF(x, RULER_HEIGHT + 10), Qt.DropAction.CopyAction, data,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.dropEvent(event)


def test_x_and_t_map_both_ways(timeline):
    assert timeline.span == (0.0, DAY)
    assert timeline.x_of(0.0) == pytest.approx(LABEL_WIDTH)
    assert timeline.t_of(timeline.x_of(700.0)) == pytest.approx(700.0)


def test_dropping_an_experiment_adds_a_block_at_that_time(timeline):
    drop(timeline, "pill", timeline.x_of(600.0))
    (block,) = timeline.document.experiment.blocks
    assert block.experiment == "pill" and block.start == pytest.approx(600.0, abs=1.0)


def test_dragging_moves_and_stretching_lengthens(timeline):
    doc = timeline.document
    doc.add_block("stress", 300.0)
    rect = timeline.block_rect(0)
    middle = rect.center().toPoint()
    drag(timeline, middle, middle + QPoint(round(timeline.x_of(500.0) - timeline.x_of(300.0)), 0))
    assert doc.experiment.blocks[0].start == pytest.approx(500.0, abs=2.0)
    assert doc.undo.count() == 2
    rect = timeline.block_rect(0)
    edge = QPoint(round(rect.right()) - 2, round(rect.center().y()))
    drag(timeline, edge, edge + QPoint(round(timeline.x_of(120.0) - timeline.x_of(0.0)), 0))
    assert doc.experiment.blocks[0].length == pytest.approx(180.0, abs=2.0)


def test_blocks_stay_inside_the_run_and_keep_a_minimum_length(timeline):
    doc = timeline.document
    doc.add_block("stress", 300.0)
    middle = timeline.block_rect(0).center().toPoint()
    drag(timeline, middle, QPoint(5, middle.y()))
    assert doc.experiment.blocks[0].start == 0.0
    middle = timeline.block_rect(0).center().toPoint()
    drag(timeline, middle, QPoint(timeline.width() + 200, middle.y()))
    assert doc.experiment.blocks[0].start + doc.experiment.blocks[0].length <= DAY
    rect = timeline.block_rect(0)
    edge = QPoint(round(rect.right()) - 2, round(rect.center().y()))
    drag(timeline, edge, QPoint(round(rect.left()) - 300, edge.y()))
    assert doc.experiment.blocks[0].length == 1.0
    assert timeline.block_rect(0).width() >= 6


def test_present_blocks_cannot_be_moved(timeline):
    doc = timeline.document
    doc.add_block("remove_b", 0.0)
    middle = timeline.block_rect(0).center().toPoint()
    drag(timeline, middle, middle + QPoint(200, 0))
    assert doc.experiment.blocks[0].start == 0.0 and doc.undo.count() == 1
    assert doc.selection == ("block", 0)


def test_the_ruler_scrubs_the_playhead(timeline):
    doc = timeline.document
    x = round(timeline.x_of(720.0))
    drag(timeline, QPoint(x, 5), QPoint(round(timeline.x_of(900.0)), 5))
    assert doc.playhead == pytest.approx(900.0, abs=2.0)


def test_the_wheel_zooms_around_the_pointer(timeline):
    x = timeline.x_of(720.0)
    event = QWheelEvent(QPointF(x, 100), QPointF(timeline.mapToGlobal(QPoint(round(x), 100))),
                        QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    timeline.wheelEvent(event)
    start, end = timeline.span
    assert end - start < DAY and start < 720.0 < end
    assert timeline.x_of(720.0) == pytest.approx(x, abs=1.0)
    for _ in range(40):
        timeline.zoom(0.5, 720.0)
    assert timeline.span[1] - timeline.span[0] == pytest.approx(30.0)
    for _ in range(40):
        timeline.zoom(2.0, 720.0)
    assert timeline.span == (0.0, DAY)


def test_dragging_an_empty_lane_pans(timeline):
    timeline.zoom(0.25, 720.0)
    before = timeline.span
    y = round(timeline.lane_rect("x").center().y())
    drag(timeline, QPoint(600, y), QPoint(500, y))
    assert timeline.span[0] > before[0]


def test_delete_removes_the_selected_block(timeline):
    doc = timeline.document
    doc.add_block("pill", 100.0)
    doc.select(("block", 0))
    timeline.setFocus()
    QTest.keyClick(timeline, Qt.Key.Key_Delete)
    assert doc.experiment.blocks == ()


def test_lanes_draw_the_normal_run_behind(timeline):
    assert timeline.lane_keys() == ["x", "y", "m"]
    lines = timeline.lane_lines("x")
    assert set(lines) == {"run", "normal"} and all(len(v) > 100 for v in lines.values())
    timeline.compare = False
    assert set(timeline.lane_lines("x")) == {"run"}
    timeline.document.take_snapshot()
    assert set(timeline.lane_lines("x")) == {"run", "snapshot"}


def test_hidden_lanes_are_skipped(timeline):
    timeline.hide_lane("y")
    assert timeline.lane_keys() == ["x", "m"]
