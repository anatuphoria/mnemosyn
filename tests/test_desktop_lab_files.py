import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow
from cns_lab.files import write

Button = QMessageBox.StandardButton


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(toy_lab_atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.messages = []
    w.inform = lambda title, text: w.messages.append(text)
    w.show()
    qapp.processEvents()
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def test_save_then_open_gives_the_same_experiment(window, tmp_path):
    doc = window.lab.document
    doc.add_block("pill", 120.0)
    doc.set_value("k", 2.0)
    path = tmp_path / "first.mnemolab"
    window.pick_save = lambda: path
    window.lab.action("Save").trigger()
    assert path.exists() and not doc.is_modified() and doc.path == path
    saved = doc.experiment
    window.lab.action("New experiment").trigger()
    assert doc.experiment.blocks == ()
    window.pick_open = lambda: path
    window.lab.action("Open").trigger()
    assert doc.experiment == saved and window.workspaces.current == "Lab"


def test_save_as_asks_again_and_save_reuses_the_path(window, tmp_path):
    doc = window.lab.document
    first, second = tmp_path / "a.mnemolab", tmp_path / "b.mnemolab"
    asked = []
    window.pick_save = lambda: (asked.append(1), first)[1]
    doc.add_block("pill", 10.0)
    window.lab.action("Save").trigger()
    doc.add_block("pill", 20.0)
    window.lab.action("Save").trigger()
    assert len(asked) == 1
    window.pick_save = lambda: second
    window.lab.action("Save as").trigger()
    assert second.exists() and doc.path == second


def test_the_title_shows_the_file_and_unsaved_changes(window, tmp_path):
    doc = window.lab.document
    assert "·" not in window.windowTitle()
    doc.add_block("pill", 10.0)
    assert window.windowTitle().endswith("· Untitled experiment[*]") and window.isWindowModified()
    window.pick_save = lambda: tmp_path / "morning.mnemolab"
    window.lab.action("Save").trigger()
    assert window.windowTitle().endswith("· morning.mnemolab[*]")
    assert not window.isWindowModified()


def test_closing_with_unsaved_changes_asks_first(qapp, toy_lab_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_lab_atlas), progress_path=tmp_path / "progress.sqlite")
    w.show()
    w.lab.document.add_block("pill", 10.0)
    answers = [Button.Cancel]
    w.ask = lambda *_args: answers.pop(0)
    assert not w.close()
    answers.append(Button.Discard)
    qapp.processEvents()
    assert w.close()


def test_new_with_unsaved_changes_can_be_cancelled(window):
    doc = window.lab.document
    doc.add_block("pill", 10.0)
    window.ask = lambda *_args: Button.Cancel
    window.lab.action("New experiment").trigger()
    assert len(doc.experiment.blocks) == 1


def test_opening_an_old_file_reports_what_changed(window, tmp_path):
    doc = window.lab.document
    path = tmp_path / "old.mnemolab"
    write(path, doc.experiment.replace(version=7))
    window.pick_open = lambda: path
    window.lab.action("Open").trigger()
    assert window.messages == ["This file was made with version 7 of the model; this is "
                               "version 1."]


def test_a_broken_file_is_refused_with_a_message(window, tmp_path):
    path = tmp_path / "broken.mnemolab"
    path.write_text("not [ toml")
    window.pick_open = lambda: path
    window.lab.action("Open").trigger()
    assert window.messages == ["This file cannot be read as a Lab experiment."]
    assert window.lab.document.path is None


def test_recent_files_are_kept_and_capped_at_eight(window, tmp_path):
    doc = window.lab.document
    for n in range(10):
        path = tmp_path / f"e{n}.mnemolab"
        write(path, doc.experiment)
        window.pick_open = lambda p=path: p
        window.lab.action("Open").trigger()
    recent = window.lab.recent_files()
    assert len(recent) == 8 and recent[0].name == "e9.mnemolab"
    assert window.lab.recent_menu.actions()[0].text() == "e9.mnemolab"


def test_file_actions_wait_while_a_quiz_runs(window):
    lab = window.lab
    window.enter_quiz()
    assert not any(lab.action(n).isEnabled() for n in ("New experiment", "Open", "Save", "Save as"))
    window.leave_quiz()
    assert all(lab.action(n).isEnabled() for n in ("New experiment", "Open", "Save", "Save as"))
