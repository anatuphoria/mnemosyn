import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.views.activity_chart import PAUSE, PLAY

MOOD_ROUTE = {111, 112, 101, 102, 120}


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_behaviour_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_behaviour_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.view.render()
    yield w
    w.close()


def labels(panel):
    return [panel.steps.item(i).text() for i in range(panel.steps.count())]


def test_the_list_has_group_headings(window):
    choices = window.pathways.choices
    texts = [choices.item(i).text() for i in range(choices.count())]
    assert texts == ["Sensory and motor", "Toy loop", "Short path", "Behaviour",
                     "Toy mood circuit"]
    assert choices.item(3).flags() == Qt.ItemFlag.NoItemFlags
    choices.itemClicked.emit(choices.item(3))
    assert not window.pathway_active


def test_a_both_sides_route_lights_both_sides_without_a_switch(window):
    panel = window.pathways
    panel.open("mood")
    assert window.state.focus == MOOD_ROUTE
    assert all(b.isHidden() for b in panel.side_buttons.values())
    assert labels(panel) == ["1 Beta nucleus", "2 Toy relay", "3 Alpha gyrus", "4 Gamma body"]
    assert panel.start.text() == "Start: beta nucleus"
    assert window.state.emphasis == (111, 112)


def test_behaviour_steps_show_disorders_and_drugs(window):
    panel = window.pathways
    panel.open("mood")
    text = panel.details.toPlainText()
    assert "Disorders: Toy low mood." in text and "Drugs: Toy pill [1]." in text
    assert "Lesion" not in text
    panel.go(1)
    assert "Drugs" not in panel.details.toPlainText()


def test_a_sensory_route_after_a_behaviour_route_shows_sides_again(window):
    panel = window.pathways
    panel.open("mood")
    panel.open("loop")
    assert not panel.side_buttons["left"].isHidden()
    assert labels(panel)[0] == "1 Alpha gyrus (left)"


def test_play_steps_a_route_without_a_timeline(window):
    panel = window.pathways
    panel.open("loop")
    panel.play()
    assert panel.playing and window.chart.play_button.text() == PAUSE
    panel.advance(2.9)
    assert panel.index == 0
    panel.advance(0.2)
    assert panel.index == 1
    for _ in range(4):
        panel.advance(3.0)
    assert panel.index == 5 and not panel.playing and window.chart.play_button.text() == PLAY
    panel.play()
    assert panel.index == 0


def test_play_follows_the_timeline(window):
    panel = window.pathways
    times = []
    panel.time_changed.connect(times.append)
    panel.open("mood")
    assert panel.timeline is window.state.atlas.timelines["mood"] and panel.time == 0.0
    panel.play()
    panel.advance(2.0)
    assert panel.time == pytest.approx(20.0) and panel.index == 2
    panel.advance(4.0)
    assert panel.time == pytest.approx(60.0) and panel.index == 3 and not panel.playing
    assert times[-1] == pytest.approx(60.0)
    panel.play()
    assert panel.time == 0.0


def test_space_toggles_play(window):
    panel = window.pathways
    panel.open("loop")
    QTest.keyClick(panel, Qt.Key.Key_Space)
    assert panel.playing
    QTest.keyClick(panel, Qt.Key.Key_Space)
    assert not panel.playing


@pytest.mark.parametrize("action", ["next", "back", "row", "side"])
def test_user_actions_pause_play(window, action):
    panel = window.pathways
    panel.open("loop")
    panel.go(2)
    panel.play()
    {"next": panel.next, "back": panel.back, "row": lambda: panel.steps.setCurrentRow(4),
     "side": lambda: panel.set_side("right")}[action]()
    assert not panel.playing and not panel.timer.isActive()


def test_leaving_or_opening_another_route_stops_play(window):
    panel = window.pathways
    panel.open("loop")
    panel.play()
    panel.open("mood")
    assert not panel.timer.isActive()
    panel.play()
    panel.leave()
    assert not panel.timer.isActive() and panel.timeline is None


def test_selecting_in_3d_pauses_play(window):
    panel = window.pathways
    panel.open("mood")
    panel.play()
    window.state.select(101)
    assert not panel.playing and panel.index == 2


def test_stepping_moves_the_time_and_seeking_moves_the_step(window):
    panel = window.pathways
    panel.open("mood")
    panel.go(3)
    assert panel.time == 40.0
    panel.go(1)
    assert panel.time == 40.0
    panel.seek(25.0)
    assert panel.index == 2 and panel.time == 25.0 and not panel.playing


def test_a_route_with_a_timeline_shows_its_curves(window):
    chart = window.chart
    window.pathways.open("mood")
    assert chart.timeline is window.state.atlas.timelines["mood"]
    assert len(chart.timeline_items) == 1 and chart.cursor.value() == 0.0
    note = chart.note.text()
    assert "Schematic shapes, not measured data" in note and "Toy curves [1]." in note
    assert "Author A (2020)" in note and not chart.note.isHidden()


def test_play_moves_the_cursor_and_chart_clicks_seek(window):
    chart, panel = window.chart, window.pathways
    panel.open("mood")
    panel.play()
    panel.advance(2.0)
    assert chart.cursor.value() == pytest.approx(20.0)
    chart.seek_requested.emit(45.0)
    assert panel.index == 3 and panel.time == 45.0 and chart.cursor.value() == 45.0


def test_seeking_outside_the_timeline_clamps(window):
    chart, panel = window.chart, window.pathways
    panel.open("mood")
    chart.seek_requested.emit(-5.0)
    assert panel.time == 0.0 and chart.cursor.value() == 0.0
    chart.seek_requested.emit(999.0)
    assert panel.time == 60.0 and panel.index == 3


def test_leaving_or_a_route_without_a_timeline_restores_the_chart(window):
    chart, panel = window.chart, window.pathways
    panel.open("mood")
    panel.open("loop")
    assert chart.timeline is None and chart.timeline_items == [] and chart.note.isHidden()
    panel.open("mood")
    panel.leave()
    assert chart.timeline is None and chart.curve.isVisible() and chart.note.isHidden()
    assert chart.plot.plotItem.titleLabel.text == "Select a structure"


def test_closing_the_window_stops_play(qapp, toy_behaviour_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_behaviour_atlas), progress_path=tmp_path / "progress.sqlite")
    w.show()
    w.pathways.open("mood")
    w.pathways.play()
    w.close()
    assert not w.pathways.timer.isActive()


def test_a_timeline_route_opens_on_the_step_of_time_zero(window):
    from dataclasses import replace

    from cns_atlas.timelines import Mark

    timelines = window.state.atlas.timelines
    timelines["mood"] = replace(timelines["mood"], marks=(Mark(0.0, 3), Mark(30.0, 1)))
    panel = window.pathways
    panel.open("mood")
    assert panel.index == 2 and panel.time == 0.0
    assert window.state.emphasis == (101, 102)


def test_selecting_off_the_route_while_playing_pauses(window):
    panel = window.pathways
    panel.open("mood")
    panel.play()
    window.state.select(131)
    assert not panel.playing and window.state.selected == 131


def test_the_control_bar_shows_only_in_pathway_mode(window):
    chart, panel = window.chart, window.pathways
    assert chart.controls.isHidden()
    panel.open("mood")
    assert not chart.controls.isHidden()
    assert chart.step_label.text() == "Step 1 of 4: Beta nucleus"
    assert chart.time_label.text() == "0 / 60 min"
    panel.leave()
    assert chart.controls.isHidden()


def test_the_control_bar_drives_the_route(window):
    chart, panel = window.chart, window.pathways
    panel.open("loop")
    chart.next_button.click()
    assert panel.index == 1 and chart.step_label.text() == "Step 2 of 6: ✕ Toy crossing"
    chart.back_button.click()
    assert panel.index == 0
    chart.play_button.click()
    assert panel.playing and chart.play_button.text() == PAUSE
    chart.play_button.click()
    assert not panel.playing and chart.play_button.text() == PLAY
    assert chart.time_label.text() == ""


def test_speed_scales_playback_without_pausing(window):
    chart, panel = window.chart, window.pathways
    panel.open("mood")
    panel.play()
    chart.speed.setCurrentIndex(2)
    assert panel.playing and panel.speed == 2.0
    panel.advance(1.0)
    assert panel.time == pytest.approx(20.0) and panel.index == 2
    chart.speed.setCurrentIndex(0)
    panel.open("loop")
    panel.play()
    panel.advance(3.0)
    assert panel.index == 0
    panel.advance(3.0)
    assert panel.index == 1


def test_space_on_the_chart_toggles_play(window):
    window.pathways.open("loop")
    QTest.keyClick(window.chart, Qt.Key.Key_Space)
    assert window.pathways.playing


def test_entering_shows_a_hidden_activity_panel_and_leaving_hides_it_again(window, qapp):
    window.chart_dock.hide()
    window.pathways.open("mood")
    assert not window.chart_dock.isHidden()
    window.pathways.leave()
    assert window.chart_dock.isHidden()


def test_a_quiz_hides_the_control_bar(window):
    import random

    from cns_study.session import QuizChoice

    window.pathways.open("mood")
    window.start_quiz(QuizChoice("name-typed", "structures", None, False), rng=random.Random(1))
    assert window.chart.controls.isHidden()
    window.quiz.stop()


class FakeClick:
    def __init__(self, pos):
        self.pos = pos

    def button(self):
        return Qt.MouseButton.LeftButton

    def scenePos(self):
        return self.pos


def test_only_clicks_inside_the_plot_seek(window):
    from PySide6.QtCore import QPointF

    chart, panel = window.chart, window.pathways
    panel.open("mood")
    seen = []
    chart.seek_requested.connect(seen.append)
    chart._on_click(FakeClick(QPointF(-50.0, -50.0)))
    assert seen == []
    chart._on_click(FakeClick(chart.plot.plotItem.vb.sceneBoundingRect().center()))
    assert len(seen) == 1


def test_the_status_bar_names_no_side_for_both_sides_routes(window):
    window.pathways.open("mood")
    window._update_status()
    assert "pathway: Toy mood circuit   │" in window.status.text()


def test_selecting_a_station_parent_goes_to_its_step(window):
    panel = window.pathways
    panel.open("mood")
    panel.go(2)
    window.state.select(110)
    assert panel.index == 0 and window.state.selected == 110
    assert window.state.emphasis == (111, 112)


def test_stepping_to_a_hidden_station_shows_it(window):
    panel = window.pathways
    panel.open("mood")
    panel.go(2)
    window.state.set_hidden([111], True)
    panel.go(0)
    assert not window.state.is_hidden(111)


def test_entering_redraws_the_slices_once(window):
    before = window.slices.redraw_count
    window.pathways.open("mood")
    assert window.slices.redraw_count == before + 1
