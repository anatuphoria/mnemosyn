from __future__ import annotations

import pytest
from fsrs import Card, Rating, Scheduler

from atlas_package import tetra, tiny_structures, write_package
from cns_atlas import Atlas
from cns_desktop.app import report_errors
from cns_desktop.errors import LOG_NAME
from cns_desktop.main_window import DOWNLOAD_URL, PROBLEM_URL, MainWindow
from cns_study.progress import ProgressStore
from cns_study.session import utc_now


pytestmark = pytest.mark.usefixtures("themed")


@pytest.fixture
def window(qapp, tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    w = MainWindow(Atlas.open(root), progress_path=tmp_path / "data" / "progress.sqlite")
    w.opened = []
    w.open_url = w.opened.append
    yield w
    w.close()


def actions(menu):
    return {a.text(): a for a in menu.actions() if a.text()}


def learn(store, item):
    now = utc_now()
    card, _log = Scheduler().review_card(Card(card_id=item), Rating.Good, now)
    store.record(item, "find", card, Rating.Good, True, 500, now)


def test_help_leads_to_updates_problems_and_the_data_folder(window, tmp_path):
    found = actions(window.help_menu)
    found["Check for a newer version"].trigger()
    found["Report a problem"].trigger()
    found["Open data folder"].trigger()
    assert [u.toString() for u in window.opened[:2]] == [DOWNLOAD_URL, PROBLEM_URL]
    assert window.opened[2].toLocalFile() == str(tmp_path / "data")
    assert (tmp_path / "data").is_dir()


def test_backing_up_writes_a_copy_of_the_progress(window, tmp_path):
    learn(window.progress_store(), 101)
    assert window.backup_progress(tmp_path / "copy.sqlite")
    copy = ProgressStore(tmp_path / "copy.sqlite", window.progress_store().atlas)
    assert list(copy.cards("find")) == [101]
    copy.close()


def test_a_backup_that_cannot_be_written_says_so(window, tmp_path):
    assert not window.backup_progress(tmp_path / "missing" / "copy.sqlite")


def test_reset_empties_progress_keeps_the_old_file_and_is_off_in_a_quiz(window):
    store = window.progress_store()
    learn(store, 101)
    window.quiz_active = True
    assert window.reset_progress() is None
    assert list(store.cards("find")) == [101]
    window.quiz_active = False
    kept = window.reset_progress()
    assert kept.exists()
    assert window.progress_store().cards("find") == {}


def test_reset_is_locked_with_the_other_quiz_actions(window):
    assert window.reset_action in window._quiz_locked()


def test_an_error_in_the_running_app_is_saved_and_shown(window, tmp_path, monkeypatch):
    reporter = report_errors(window, tmp_path / "logs")
    monkeypatch.setattr(reporter, "previous", lambda *args: None)
    try:
        try:
            raise RuntimeError("a slot failed")
        except RuntimeError as exc:
            reporter.hook(type(exc), exc, exc.__traceback__)
        assert "RuntimeError: a slot failed" in (tmp_path / "logs" / LOG_NAME).read_text()
        assert str(tmp_path / "logs" / LOG_NAME) in window.error_box.text()
        window.error_box.close()
    finally:
        reporter.remove()
