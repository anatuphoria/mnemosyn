from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler

from .items import Item
from .progress import ProgressStore, day_start

NEW_PER_DAY = 20
LEARN_AHEAD = timedelta(minutes=20)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QuizChoice:
    mode: str
    level: str
    scope: int | None
    practice: bool


@dataclass(frozen=True)
class Summary:
    answered: int
    correct: int
    percent: int
    most_missed: tuple[Item, ...]
    due_tomorrow: int


def due_and_new(items: list[Item], mode: str, store: ProgressStore, now: datetime,
                new_per_day: int = NEW_PER_DAY) -> tuple[list[int], list[int]]:
    cards = store.cards(mode)
    ids = {item.id for item in items}
    due = [i for _, i in sorted((c.due, i) for i, c in cards.items() if i in ids and c.due <= now)]
    left = max(0, new_per_day - store.first_reviews_since(mode, day_start(now)))
    new = [item.id for item in items if item.id not in cards][:left]
    return due, new


class Session:
    def __init__(self, items: list[Item], mode: str, store: ProgressStore, practice: bool = False,
                 now: Callable[[], datetime] = utc_now, rng: random.Random | None = None,
                 scheduler: Scheduler | None = None, new_per_day: int = NEW_PER_DAY) -> None:
        self.items = {item.id: item for item in items}
        self.mode = mode
        self.store = store
        self.practice = practice
        self.now = now
        self.rng = rng or random.Random()
        self.scheduler = scheduler or Scheduler()
        self.cards: dict[int, Card] = {}
        self.waiting: list[int] = []
        self.current: Item | None = None
        self.answered = 0
        self.right = 0
        self.missed: Counter[int] = Counter()
        if practice:
            self.queue = list(self.items)
            self.rng.shuffle(self.queue)
        else:
            self.cards = {i: c for i, c in store.cards(mode).items() if i in self.items}
            due, new = due_and_new(items, mode, store, now(), new_per_day)
            self.queue = due + new

    def remaining(self) -> int:
        return len(self.queue) + len(self.waiting)

    def next(self) -> Item | None:
        moment = self.now()
        ready = [i for i in self.waiting if self.cards[i].due <= moment]
        if ready or (self.waiting and not self.queue):
            pick = min(ready or self.waiting, key=lambda i: self.cards[i].due)
            self.waiting.remove(pick)
        elif self.queue:
            pick = self.queue.pop(0)
        else:
            self.current = None
            return None
        self.current = self.items[pick]
        return self.current

    def answer(self, rating: Rating, correct: bool, answer_ms: int) -> None:
        item = self.current
        if item is None:
            raise RuntimeError("no question is waiting for an answer")
        if not self.practice:
            moment = self.now()
            card = self.cards.get(item.id) or Card(card_id=item.id, due=moment)
            card, _ = self.scheduler.review_card(card, rating, moment, answer_ms)
            self.store.record(item.id, self.mode, card, int(rating), correct, answer_ms, moment)
            self.cards[item.id] = card
            if card.due <= moment + LEARN_AHEAD:
                self.waiting.append(item.id)
        self.current = None
        self.answered += 1
        self.right += int(correct)
        if not correct:
            self.missed[item.id] += 1

    def summary(self) -> Summary:
        percent = round(100 * self.right / self.answered) if self.answered else 0
        order = sorted(self.missed.items(), key=lambda pair: (-pair[1], pair[0]))
        tomorrow_end = day_start(self.now(), 2)
        due = sum(card.due < tomorrow_end for card in self.cards.values())
        return Summary(self.answered, self.right, percent,
                       tuple(self.items[i] for i, _ in order[:5]), due)
