from __future__ import annotations

import sys

from cns_desktop.errors import CRASH_NAME, LOG_NAME, Reporter, entry, trim


def boom():
    try:
        raise ValueError("the thing broke")
    except ValueError:
        return sys.exc_info()


def test_an_entry_names_the_version_and_the_error():
    text = entry("0.5.1", *boom())
    assert "Mnemosyn 0.5.1" in text
    assert "ValueError: the thing broke" in text


def test_the_hook_saves_the_error_and_tells_the_user_once(tmp_path, monkeypatch):
    shown = []
    reporter = Reporter(tmp_path / "data", "1.2.3", shown.append)
    monkeypatch.setattr(reporter, "previous", lambda *args: None)
    reporter.hook(*boom())
    reporter.hook(*boom())
    log = (tmp_path / "data" / LOG_NAME).read_text()
    assert log.count("ValueError: the thing broke") == 2
    assert len(shown) == 1
    assert str(tmp_path / "data" / LOG_NAME) in shown[0]


def test_a_keyboard_interrupt_is_not_reported(tmp_path, monkeypatch):
    shown, passed = [], []
    reporter = Reporter(tmp_path, "1", shown.append)
    monkeypatch.setattr(reporter, "previous", lambda *args: passed.append(args))
    reporter.hook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert passed and not shown
    assert not (tmp_path / LOG_NAME).exists()


def test_a_folder_that_cannot_be_written_does_not_raise(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    shown = []
    reporter = Reporter(blocker / "inside", "1", shown.append)
    monkeypatch.setattr(reporter, "previous", lambda *args: None)
    reporter.hook(*boom())
    assert not shown


def test_the_log_keeps_only_its_newest_part(tmp_path):
    path = tmp_path / LOG_NAME
    path.write_text("".join(f"line {n}\n" for n in range(2000)))
    trim(path, keep=500)
    kept = path.read_text()
    assert len(kept) <= 500
    assert kept.startswith("line ") and kept.endswith("line 1999\n")


def test_install_and_remove_put_the_hook_back(tmp_path):
    before = sys.excepthook
    reporter = Reporter(tmp_path, "1")
    reporter.install()
    try:
        assert sys.excepthook == reporter.hook
        assert (tmp_path / CRASH_NAME).exists()
    finally:
        reporter.remove()
    assert sys.excepthook is before
