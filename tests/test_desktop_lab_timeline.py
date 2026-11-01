import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.experiments_panel import MIME
from cns_desktop.lab.labels import plain
from cns_desktop.lab.timeline import (CHANGES_HEIGHT, LABEL_WIDTH, LANE_HEIGHT, MIN_SPAN,
                                     RULER_HEIGHT, Timeline)

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
    y = round(timeline.ruler_rect().center().y())
    drag(timeline, QPoint(x, y), QPoint(round(timeline.x_of(900.0)), y))
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
    mouse(timeline, QMouseEvent.Type.MouseButtonDblClick,
          QPoint(500, round(timeline.ruler_rect().center().y())))
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


def test_every_lane_can_be_scrolled_into_view(timeline):
    doc = timeline.document
    for start in (100.0, 110.0, 120.0):
        doc.add_block("pill", start)
    keys = timeline.lane_keys()
    timeline.resize(1000, timeline.minimumHeight())
    timeline.scroll.setValue(timeline.scroll.maximum())
    assert timeline.lane_rect(keys[-1]).bottom() <= timeline.height()
    assert timeline.block_rect(2).bottom() <= timeline.lane_rect(keys[0]).top()


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


def crowd(timeline):
    for start in (100.0, 110.0, 120.0, 130.0):
        timeline.document.add_block("pill", start)
    timeline.resize(1000, 260)


def test_the_header_stays_while_the_body_scrolls(timeline):
    crowd(timeline)
    assert timeline.scroll.isVisible() and timeline.scroll.maximum() > 0
    assert timeline.ruler_rect().top() == timeline.overview_rect().bottom()
    assert timeline.body_top() == timeline.ruler_rect().bottom()
    top = timeline.lane_rect("x").top()
    before = timeline.grab().toImage()
    timeline.scroll.setValue(timeline.scroll.maximum())
    assert timeline.lane_rect("x").top() == top - timeline.scroll.maximum()
    after = timeline.grab().toImage()
    for y in range(0, round(timeline.body_top()), 3):
        for x in range(0, timeline.width(), 7):
            assert before.pixel(x, y) == after.pixel(x, y)


def test_scrolled_away_changes_cannot_be_grabbed_through_the_header(timeline):
    crowd(timeline)
    timeline.scroll.setValue(timeline.scroll.maximum())
    assert timeline.block_rect(0).top() < timeline.body_top()
    y = round(timeline.ruler_rect().center().y())
    assert timeline._block_at(QPointF(timeline.block_rect(0).center().x(), y)) is None


def test_the_scrollbar_hides_when_everything_fits(timeline):
    timeline.resize(1000, 900)
    assert not timeline.scroll.isVisible() and timeline.scroll.value() == 0


def test_the_wheel_over_the_names_scrolls_the_lanes(timeline):
    crowd(timeline)
    before = timeline.span
    y = round(timeline.lane_rect("x").center().y())
    event = QWheelEvent(QPointF(40, y), QPointF(timeline.mapToGlobal(QPoint(40, y))),
                        QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    timeline.wheelEvent(event)
    assert timeline.scroll.value() > 0 and timeline.span == before


def test_a_new_length_resets_zoom_and_scroll(timeline):
    crowd(timeline)
    timeline.zoom(0.2, 600.0)
    timeline.scroll.setValue(timeline.scroll.maximum())
    timeline.document.set_length(3 * DAY)
    assert timeline.span == (0.0, 3 * DAY) and timeline.scroll.value() == 0


def test_the_minimum_height_holds_the_header_one_row_and_one_lane(timeline):
    assert timeline.minimumHeight() == round(timeline.body_top() + CHANGES_HEIGHT + LANE_HEIGHT)


def test_the_overview_window_fills_the_bar_for_the_whole_run(timeline):
    window = timeline.overview_window()
    assert window.left() == pytest.approx(LABEL_WIDTH)
    assert window.width() == pytest.approx(timeline._plot_width())
    assert timeline.overview_rect().contains(window.center())


def test_dragging_the_overview_window_moves_the_span(timeline):
    timeline.zoom(0.25, 360.0)
    width = timeline.span[1] - timeline.span[0]
    centre = timeline.overview_window().center().toPoint()
    drag(timeline, centre, centre + QPoint(100, 0))
    assert timeline.span[0] > 0
    assert timeline.span[1] - timeline.span[0] == pytest.approx(width)
    assert timeline.overview_window().center().x() == pytest.approx(centre.x() + 100, abs=2)


def test_dragging_an_overview_edge_zooms(timeline):
    timeline.zoom(0.5, 720.0)
    start, end = timeline.span
    window = timeline.overview_window()
    edge = QPoint(round(window.right()) - 1, round(window.center().y()))
    drag(timeline, edge, edge - QPoint(200, 0))
    assert timeline.span[0] == pytest.approx(start)
    assert timeline.span[1] < end
    drag(timeline, QPoint(round(timeline.overview_window().right()) - 1, edge.y()),
         QPoint(0, edge.y()))
    assert timeline.span[1] - timeline.span[0] == pytest.approx(MIN_SPAN)


def test_pressing_outside_the_overview_window_centres_it_there(timeline):
    timeline.zoom(0.25, 0.0)
    y = round(timeline.overview_rect().center().y())
    mouse(timeline, QMouseEvent.Type.MouseButtonPress, QPoint(round(timeline.overview_x(1000.0)), y))
    mouse(timeline, QMouseEvent.Type.MouseButtonRelease, QPoint(round(timeline.overview_x(1000.0)), y))
    start, end = timeline.span
    assert (start + end) / 2 == pytest.approx(1000.0, abs=3.0)


def test_double_clicking_the_overview_shows_the_whole_run(timeline):
    timeline.zoom(0.25, 360.0)
    point = timeline.overview_window().center().toPoint()
    mouse(timeline, QMouseEvent.Type.MouseButtonDblClick, point)
    assert timeline.span == (0.0, DAY)


def test_the_overview_can_be_turned_off(timeline):
    timeline.show_overview = False
    assert timeline.overview_rect().height() == 0 and timeline.ruler_rect().top() == 0


def test_timed_blocks_stay_reachable_under_a_present_one(timeline):
    doc = timeline.document
    doc.add_block("pill", 300.0)
    doc.add_block("remove_b", 0.0)
    middle = timeline.block_rect(0).center().toPoint()
    mouse(timeline, QMouseEvent.Type.MouseButtonPress, middle)
    mouse(timeline, QMouseEvent.Type.MouseButtonRelease, middle)
    assert doc.selection == ("block", 0)
