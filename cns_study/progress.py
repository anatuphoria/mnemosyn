from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fsrs import Card, Scheduler, State

SCHEMA_VERSION = 1
MODES = ("name-typed", "name-choice", "find", "flashcard")
SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  atlas TEXT NOT NULL, item INTEGER NOT NULL, mode TEXT NOT NULL,
  card TEXT NOT NULL, due TEXT NOT NULL,
  PRIMARY KEY (atlas, item, mode));
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY, atlas TEXT NOT NULL, item INTEGER NOT NULL, mode TEXT NOT NULL,
  rating INTEGER NOT NULL, correct INTEGER NOT NULL, answer_ms INTEGER NOT NULL,
  reviewed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS reviews_by_item ON reviews (atlas, mode, item, reviewed_at);
"""
UPSERT_CARD = ("INSERT INTO cards VALUES (?, ?, ?, ?, ?) ON CONFLICT (atlas, item, mode) "
               "DO UPDATE SET card = excluded.card, due = excluded.due")
INSERT_REVIEW = ("INSERT INTO reviews (atlas, item, mode, rating, correct, answer_ms, "
                 "reviewed_at) VALUES (?, ?, ?, ?, ?, ?, ?)")


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def day_start(moment: datetime, days: int = 0) -> datetime:
    day = moment.astimezone().date() + timedelta(days=days)
    return datetime(day.year, day.month, day.day).astimezone(UTC)


class NewerVersion(sqlite3.DatabaseError):
    pass


@dataclass(frozen=True)
class ModeStats:
    new: int
    learning: int
    known: int
    due_today: int
    due_week: int


class ProgressStore:
    def __init__(self, path: Path, atlas: str) -> None:
        self.path = Path(path)
        self.atlas = atlas
        self.recovered_from: Path | None = None
        self.recovery_reason: str | None = None
        try:
            self.db = self._open()
        except sqlite3.DatabaseError as exc:
            self.recovery_reason = "newer" if isinstance(exc, NewerVersion) else "damaged"
            self.recovered_from = self._set_aside()
            self.db = self._open()

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise NewerVersion(f"progress schema version {version} is newer than this app")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = NORMAL")
            db.executescript(SCHEMA)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.DatabaseError:
            db.close()
            raise
        return db

    def _set_aside(self) -> Path:
        broken = self.path.with_name(f"{self.path.name}.broken-{datetime.now():%Y%m%d-%H%M%S}")
        self.path.replace(broken)
        for suffix in ("-wal", "-shm"):
            sidecar = self.path.with_name(self.path.name + suffix)
            if sidecar.exists():
                sidecar.replace(broken.with_name(broken.name + suffix))
        return broken

    def cards(self, mode: str) -> dict[int, Card]:
        rows = self.db.execute("SELECT item, card FROM cards WHERE atlas = ? AND mode = ?",
                               (self.atlas, mode))
        return {item: Card.from_json(text) for item, text in rows}

    def card(self, item: int, mode: str) -> Card | None:
        row = self.db.execute("SELECT card FROM cards WHERE atlas = ? AND item = ? AND mode = ?",
                              (self.atlas, item, mode)).fetchone()
        return None if row is None else Card.from_json(row[0])

    def record(self, item: int, mode: str, card: Card, rating: int, correct: bool,
               answer_ms: int, when: datetime) -> None:
        self.db.execute("BEGIN")
        try:
            self.db.execute(UPSERT_CARD, (self.atlas, item, mode, card.to_json(), stamp(card.due)))
            self.db.execute(INSERT_REVIEW, (self.atlas, item, mode, int(rating), int(correct),
                                            int(answer_ms), stamp(when)))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def review_count(self, mode: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM reviews WHERE atlas = ? AND mode = ?",
                               (self.atlas, mode)).fetchone()[0]

    def first_reviews_since(self, mode: str, since: datetime) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM (SELECT MIN(reviewed_at) AS first FROM reviews "
            "WHERE atlas = ? AND mode = ? GROUP BY item) WHERE first >= ?",
            (self.atlas, mode, stamp(since))).fetchone()[0]

    def close(self) -> None:
        self.db.close()


def mode_stats(cards: dict[int, Card], ids: list[int], now: datetime) -> ModeStats:
    seen = [cards[i] for i in ids if i in cards]
    today_end, week_end = day_start(now, 1), day_start(now, 7)
    return ModeStats(
        new=len(ids) - len(seen),
        learning=sum(c.state in (State.Learning, State.Relearning) for c in seen),
        known=sum(c.state == State.Review for c in seen),
        due_today=sum(c.due < today_end for c in seen),
        due_week=sum(c.due < week_end for c in seen))


def weakest(cards: dict[int, Card], ids: list[int], scheduler: Scheduler, now: datetime,
            count: int = 10) -> list[tuple[int, float]]:
    seen = [(i, scheduler.get_card_retrievability(cards[i], now)) for i in ids if i in cards]
    return sorted(seen, key=lambda pair: (pair[1], pair[0]))[:count]
