import sqlite3
from datetime import datetime, timedelta, timezone

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
    stats = mode_stats(cards, [1, 2, 3], day_start(T0) + timedelta(days=1))
    assert stats == ModeStats(new=1, learning=1, known=1, due_today=1, due_week=1)
    weak = weakest(cards, [1, 2, 3], Scheduler(enable_fuzzing=False), T0 + timedelta(days=4))
    assert [item for item, _ in weak] == [1, 2]
    assert all(0 < value < 1 for _, value in weak)
