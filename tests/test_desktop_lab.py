import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow

DAY = 1440.0


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, atlas_path, tmp_path):
    w = MainWindow(Atlas.open(atlas_path), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def test_entering_the_lab_shows_its_docks_and_leaving_restores_the_view(qapp, window):
    lab = window.lab
    assert all(d.isHidden() for d in lab.docks) and lab.toolbar.isHidden()
    window.state.select(120)
    window.workspaces.switch("Lab")
    qapp.processEvents()
    assert all(not d.isHidden() for d in (lab.dock("Experiments"), lab.dock("Why"),
                                          lab.dock("Timeline")))
    assert not lab.toolbar.isHidden() and lab.experiment_menu.menuAction().isVisible()
    assert window.state.focus == {111, 101, 102} and window.viewport.top_bar.isVisible()
    window.workspaces.switch("Explore")
    assert all(d.isHidden() for d in lab.docks) and lab.toolbar.isHidden()
    assert window.state.focus is None and window.state.selected == 120
    assert not lab.experiment_menu.menuAction().isVisible()


def test_space_plays_only_in_the_lab_and_not_during_a_route(qapp, window):
    lab = window.lab
    window.workspaces.switch("Lab")
    window.activateWindow()
    window.view.setFocus()
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert lab.playing
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert not lab.playing
    window.workspaces.switch("Explore")
    window.pathways.open("mood")
    window.view.setFocus()
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert window.pathways.playing and not lab.playing
    window.pathways.pause()


def test_space_in_a_lab_text_box_types_a_space(qapp, window):
    lab = window.lab
    window.workspaces.switch("Lab")
    window.lab.document.select(None)
    box = lab.inspector.title_box()
    box.setFocus()
    QTest.keyClicks(box, "a b")
    assert box.text() == "a b" and not lab.playing
    box.editingFinished.emit()
    assert lab.document.experiment.title == "a b"


def test_playback_speed_follows_the_zoom(window):
    lab = window.lab
    window.workspaces.switch("Lab")
    assert lab.rate() == pytest.approx(DAY / 20)
    lab.timeline.zoom(0.25, 720.0)
    assert lab.rate() == pytest.approx(DAY / 4 / 20)
    lab.set_speed(2.0)
    assert lab.rate() == pytest.approx(DAY / 4 / 10)
    lab.advance(1.0)
    assert lab.document.playhead == pytest.approx(DAY / 4 / 10)


def test_playback_stops_at_the_end(window):
    lab = window.lab
    window.workspaces.switch("Lab")
    lab.document.set_playhead(DAY - 1)
    lab.play()
    lab.advance(5.0)
    assert lab.document.playhead == DAY and not lab.playing


def test_the_status_bar_counts_changes_and_edited_values(window):
    window.workspaces.switch("Lab")
    doc = window.lab.document
    doc.add_block("pill", 10.0)
    doc.add_block("stress", 20.0)
    doc.set_value("k", 2.0)
    window._update_status()
    assert window.status.text() == ("Toy axis · healthy adult   │   2 changes · 1 value edited"
                                    "   │   Space plays, drag a change to move it")


def test_open_in_the_lab_from_the_route(window):
    panel = window.pathways
    panel.open("mood")
    assert not panel.lab_button.isHidden()
    panel.lab_button.click()
    assert window.workspaces.current == "Lab" and not window.pathway_active
    panel.open("loop")
    assert panel.lab_button.isHidden()


def test_an_atlas_without_models_has_no_lab(qapp, toy_behaviour_atlas, tmp_path):
    w = open_window(qapp, toy_behaviour_atlas, tmp_path)
    assert w.lab is None and w.workspaces.button("Lab").isHidden()
    w.pathways.open("mood")
    assert w.pathways.lab_button.isHidden()
    qapp.processEvents()
    w.close()


def test_the_run_length_menu_and_the_longer_run_offer(window):
    lab = window.lab
    window.workspaces.switch("Lab")
    lab.length_action("3 d").trigger()
    assert lab.document.experiment.length == 3 * DAY
    window.ask = lambda *_args: QMessageBox.StandardButton.Yes
    lab.document.add_block("course", 10.0)
    assert lab.document.experiment.length == 4 * 7 * DAY
    window.ask = lambda *_args: QMessageBox.StandardButton.No
    lab.length_action("1 d").trigger()
    lab.document.add_block("course", 10.0)
    assert lab.document.experiment.length == DAY


def test_showing_a_part_in_the_atlas(window):
    lab = window.lab
    window.workspaces.switch("Lab")
    window.viewport.show_circuit(True)
    lab.circuit.show_in_atlas.emit("a")
    assert window.state.selected == 111 and not window.viewport.showing_circuit
    lab.circuit.show_chart.emit("a")
    assert lab.dock("Charts").isVisible()


def test_v_switches_brain_and_circuit(window):
    window.workspaces.switch("Lab")
    window.activateWindow()
    window.view.setFocus()
    QTest.keyClick(window, Qt.Key.Key_V)
    assert window.viewport.showing_circuit
    QTest.keyClick(window, Qt.Key.Key_V)
    assert not window.viewport.showing_circuit
    window.workspaces.switch("Explore")
    QTest.keyClick(window, Qt.Key.Key_V)
    assert not window.viewport.showing_circuit


def test_lab_keys_work_only_in_the_lab(window):
    lab = window.lab
    assert not lab.action("Undo").isEnabled()
    window.workspaces.switch("Lab")
    lab.document.add_block("pill", 10.0)
    assert lab.action("Undo").isEnabled()
    lab.action("Undo").trigger()
    assert lab.document.experiment.blocks == ()


def test_a_quiz_or_a_route_leaves_the_lab_first(window):
    from cns_study.session import QuizChoice

    window.workspaces.switch("Lab")
    assert not window.pathway_dock.toggleViewAction().isEnabled()
    assert not window.tree_dock.toggleViewAction().isEnabled()
    dialog = window.open_quiz_setup()
    assert window.workspaces.current == "Explore"
    dialog.reject()
    window.workspaces.switch("Lab")
    window.start_quiz(QuizChoice("name-typed", "structures", None, False))
    assert window.workspaces.current == "Explore" and window.quiz_active
    assert all(d.isHidden() for d in window.lab.docks)
    window.leave_quiz()
    assert window.pathway_dock.toggleViewAction().isEnabled()
