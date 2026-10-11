import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest
from fsrs import Card, Rating, Scheduler

from cns_study.progress import ModeStats, ProgressStore, day_start, mode_stats, weakest

T0 = day_start(datetime(2026, 10, 11, 12, tzinfo=timezone.utc)) + timedelta(hours=9)


def reviewed(item, rating, when):
    card, _ = Scheduler(enable_fuzzing=False).review_card(Card(card_id=item, due=when), rating,
                                                          when)
    return card


def test_cards_and_reviews_survive_reopening(tmp_path):
    path = tmp_path / "progress.sqlite"
    store = ProgressStore(path, "atlas-a")
    card = reviewed(100, Rating.Good, T0)
    store.record(100, "name-typed", card, Rating.Good, True, 1200, T0)
    store.close()
    again = ProgressStore(path, "atlas-a")
    assert again.card(100, "name-typed").due == card.due
    assert again.review_count("name-typed") == 1
    assert again.recovered_from is None
    again.close()


def test_atlases_and_modes_are_kept_apart(tmp_path):
    store = ProgressStore(tmp_path / "p.sqlite", "atlas-a")
    store.record(100, "find", reviewed(100, Rating.Easy, T0), Rating.Easy, True, 900, T0)
    other = ProgressStore(tmp_path / "p.sqlite", "atlas-b")
    assert other.cards("find") == {}
    assert store.cards("name-typed") == {}
    assert list(store.cards("find")) == [100]


def test_a_damaged_file_is_set_aside(tmp_path):
    path = tmp_path / "progress.sqlite"
    path.write_bytes(b"this is not a database" * 100)
    store = ProgressStore(path, "atlas-a")
    assert store.recovered_from is not None
    assert store.recovered_from.name.startswith("progress.sqlite.broken-")
    assert store.recovered_from.read_bytes().startswith(b"this is not a database")
    assert store.cards("find") == {}


def test_a_newer_schema_is_set_aside_not_overwritten(tmp_path):
    path = tmp_path / "progress.sqlite"
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version = 2")
    db.close()
    store = ProgressStore(path, "atlas-a")
    assert store.recovered_from is not None
    old = sqlite3.connect(store.recovered_from)
    assert old.execute("PRAGMA user_version").fetchone()[0] == 2
    old.close()


def test_first_reviews_count_items_first_seen_since_a_moment(tmp_path):
    store = ProgressStore(tmp_path / "p.sqlite", "atlas-a")
    yesterday = T0 - timedelta(days=1)
    store.record(1, "find", reviewed(1, Rating.Good, yesterday), Rating.Good, True, 500, yesterday)
    store.record(1, "find", reviewed(1, Rating.Good, T0), Rating.Good, True, 500, T0)
    store.record(2, "find", reviewed(2, Rating.Good, T0), Rating.Good, True, 500, T0)
    assert store.first_reviews_since("find", T0 - timedelta(hours=1)) == 1


def test_day_start_is_local_midnight_in_utc():
    start = day_start(T0)
    assert start <= T0 < start + timedelta(days=1)
    assert start.astimezone().hour == 0 and start.tzinfo == timezone.utc


def test_mode_stats_and_weakest():
    cards = {1: reviewed(1, Rating.Good, T0), 2: reviewed(2, Rating.Easy, T0)}
    stats = mode_stats(cards, [1, 2, 3], T0)
    assert stats == ModeStats(new=1, learning=1, known=1, due_today=1, due_week=1)
    weak = weakest(cards, [1, 2, 3], Scheduler(enable_fuzzing=False), T0 + timedelta(days=4))
    assert [item for item, _ in weak] == [1, 2]
    assert all(0 < value < 1 for _, value in weak)


def test_a_new_file_gets_the_current_schema_version(tmp_path):
    path = tmp_path / "p.sqlite"
    ProgressStore(path, "atlas-a").close()
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    db.close()


def test_the_reason_for_setting_a_file_aside_is_kept(tmp_path):
    newer = tmp_path / "newer.sqlite"
    db = sqlite3.connect(newer)
    db.execute("PRAGMA user_version = 2")
    db.close()
    assert ProgressStore(newer, "atlas-a").recovery_reason == "newer"
    damaged = tmp_path / "damaged.sqlite"
    damaged.write_bytes(b"not a database" * 100)
    assert ProgressStore(damaged, "atlas-a").recovery_reason == "damaged"
    assert ProgressStore(tmp_path / "fresh.sqlite", "atlas-a").recovery_reason is None


def test_a_failed_commit_does_not_block_the_next_answer(tmp_path):
    store = ProgressStore(tmp_path / "p.sqlite", "atlas-a")
    real = store.db

    class FailingCommit:
        failed = False

        def execute(self, sql, *args):
            if sql == "COMMIT" and not self.failed:
                self.failed = True
                raise sqlite3.OperationalError("database is locked")
            return real.execute(sql, *args)

    store.db = FailingCommit()
    with pytest.raises(sqlite3.OperationalError):
        store.record(1, "find", reviewed(1, Rating.Good, T0), Rating.Good, True, 500, T0)
    store.record(2, "find", reviewed(2, Rating.Good, T0), Rating.Good, True, 500, T0)
    assert list(store.cards("find")) == [2]


@pytest.fixture
def berlin(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_day_boundaries_follow_the_calendar_across_a_clock_change(berlin):
    moment = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
    assert day_start(moment, 2).astimezone().hour == 0
    assert day_start(moment, 2) - day_start(moment, 1) == timedelta(hours=25)
