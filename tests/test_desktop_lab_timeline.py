import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.experiments_panel import MIME
from cns_desktop.lab.labels import plain
from cns_desktop.lab.timeline import LABEL_WIDTH, LANE_HEIGHT, RULER_HEIGHT, Timeline

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


def test_a_zoomed_block_stays_out_of_the_name_column(timeline):
    doc = timeline.document
    blank = timeline.grab().toImage()
    doc.add_block("pill", 120.0)
    timeline.zoom(0.25, 720.0)
    assert timeline.x_of(120.0) < LABEL_WIDTH
    y = round(timeline.block_rect(0).center().y())
    assert timeline._block_at(QPointF(LABEL_WIDTH - 20, y)) is None
    image = timeline.grab().toImage()
    for x in range(0, LABEL_WIDTH - 2, 4):
        assert image.pixel(x, y) == blank.pixel(x, y)


def test_the_playhead_can_be_grabbed_anywhere_along_its_line(timeline):
    doc = timeline.document
    doc.set_playhead(600.0)
    before = timeline.span
    y = round(timeline.lane_rect("y").center().y())
    x = round(timeline.x_of(600.0))
    drag(timeline, QPoint(x + 2, y), QPoint(round(timeline.x_of(800.0)), y))
    assert doc.playhead == pytest.approx(800.0, abs=3.0) and timeline.span == before


def test_the_playhead_wins_over_a_block_under_it(timeline):
    doc = timeline.document
    doc.add_block("stress", 300.0)
    doc.set_playhead(320.0)
    y = round(timeline.block_rect(0).center().y())
    drag(timeline, QPoint(round(timeline.x_of(320.0)), y), QPoint(round(timeline.x_of(500.0)), y))
    assert doc.playhead == pytest.approx(500.0, abs=3.0)
    assert doc.experiment.blocks[0].start == 300.0


def test_overlapping_changes_stack_in_rows(timeline):
    doc = timeline.document
    doc.add_block("pill", 300.0)
    doc.add_block("stress", 600.0)
    doc.add_block("stress", 100.0)
    first, second, third = (timeline.block_rect(i) for i in range(3))
    assert not first.intersects(second)
    assert second.top() > first.top()
    assert third.top() == first.top()
    assert timeline.lane_rect("x").top() >= second.bottom()


def test_ruler_labels_stay_inside_the_widget(timeline):
    for x, rect, _text in timeline.ruler_labels():
        assert LABEL_WIDTH <= rect.left() and rect.right() <= timeline.width()
    texts = [text for _x, _rect, text in timeline.ruler_labels()]
    assert texts[0] == "0 h" and texts[-1] == "1 d"


def test_the_whole_run_comes_back_after_zooming(timeline):
    timeline.zoom(0.1, 720.0)
    timeline.show_whole_run()
    assert timeline.span == (0.0, DAY)
    timeline.zoom(0.1, 720.0)
    mouse(timeline, QMouseEvent.Type.MouseButtonDblClick, QPoint(500, 5))
    assert timeline.span == (0.0, DAY)


def test_a_sideways_swipe_pans_when_zoomed(timeline):
    timeline.zoom(0.25, 720.0)
    before = timeline.span
    event = QWheelEvent(QPointF(500, 100), QPointF(timeline.mapToGlobal(QPoint(500, 100))),
                        QPoint(0, 0), QPoint(-120, 0), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    timeline.wheelEvent(event)
    assert timeline.span[0] > before[0]
    assert timeline.span[1] - timeline.span[0] == pytest.approx(before[1] - before[0])


def test_lanes_share_the_height_they_are_given(timeline):
    timeline.resize(1000, 900)
    keys = timeline.lane_keys()
    heights = {round(timeline.lane_rect(k).height()) for k in keys}
    assert len(heights) == 1 and heights.pop() > LANE_HEIGHT
    assert timeline.lane_rect(keys[-1]).bottom() == pytest.approx(timeline.height(), abs=2)
    timeline.resize(1000, 100)
    assert timeline.lane_rect(keys[0]).height() == LANE_HEIGHT


def test_every_lane_and_change_row_fits_in_the_minimum_height(timeline):
    doc = timeline.document
    for start in (100.0, 110.0, 120.0):
        doc.add_block("pill", start)
    keys = timeline.lane_keys()
    timeline.resize(1000, timeline.minimumHeight())
    assert timeline.lane_rect(keys[-1]).bottom() <= timeline.height()
    assert timeline.block_rect(2).bottom() <= timeline.lane_rect(keys[0]).top()
    timeline.hide_lane(keys[0])
    assert timeline.minimumHeight() < timeline.height()


def test_lane_values_match_the_run_at_the_playhead(timeline):
    doc = timeline.document
    doc.set_playhead(600.0)
    text, _tone = timeline.lane_value("x")
    assert text == plain(doc.run.display("x", 600.0), 3)


def test_lane_values_are_toned_against_the_normal_run(timeline):
    doc = timeline.document
    doc.add_block("pill", 100.0)
    doc.set_playhead(105.0)
    assert timeline.lane_value("y")[1] == "raised" and timeline.lane_value("x")[1] == "lowered"
    doc.set_playhead(700.0)
    assert timeline.lane_value("y")[1] == ""


def test_the_lane_scale_does_not_change_with_zoom(timeline):
    before = timeline.lane_marks("x")
    timeline.zoom(0.1, 300.0)
    assert timeline.lane_marks("x") == before


def test_a_failed_run_shows_no_values(timeline):
    timeline.document.run = None
    assert timeline.lane_value("x") == ("", "")
    timeline.grab()


def test_a_long_name_never_meets_its_value(timeline):
    timeline.resize(500, 260)
    timeline.document.add_block("pill", 100.0)
    timeline.document.set_playhead(700.0)
    for key in timeline.lane_keys():
        name, unit, value = timeline.name_layout(key)
        assert not name.intersects(value) and not unit.intersects(value)
        assert value.right() <= LABEL_WIDTH and value.width() > 0


def test_timed_blocks_stay_reachable_under_a_present_one(timeline):
    doc = timeline.document
    doc.add_block("pill", 300.0)
    doc.add_block("remove_b", 0.0)
    middle = timeline.block_rect(0).center().toPoint()
    mouse(timeline, QMouseEvent.Type.MouseButtonPress, middle)
    mouse(timeline, QMouseEvent.Type.MouseButtonRelease, middle)
    assert doc.selection == ("block", 0)
