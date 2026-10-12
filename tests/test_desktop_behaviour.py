import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_desktop.views.pathway_panel import PAUSE, PLAY

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
    assert panel.playing and panel.play_button.text() == PAUSE
    panel.advance(2.9)
    assert panel.index == 0
    panel.advance(0.2)
    assert panel.index == 1
    for _ in range(4):
        panel.advance(3.0)
    assert panel.index == 5 and not panel.playing and panel.play_button.text() == PLAY
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
