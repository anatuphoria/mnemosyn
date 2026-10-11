import random
from datetime import datetime, timedelta, timezone

import pytest
from fsrs import Rating, Scheduler, State

from cns_study.items import Item
from cns_study.progress import ProgressStore, day_start
from cns_study.session import Session, due_and_new

T0 = day_start(datetime(2026, 10, 11, 12, tzinfo=timezone.utc)) + timedelta(hours=9)


class Clock:
    def __init__(self) -> None:
        self.moment = T0

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **delta) -> None:
        self.moment += timedelta(**delta)


def make_items(count):
    return [Item(n, "structures", f"Item {n}", f"I{n}", (f"Item {n}",), frozenset({n * 10}),
                 (1, n)) for n in range(1, count + 1)]


def session(store, items, clock, **options):
    return Session(items, "find", store, now=clock, rng=random.Random(1),
                   scheduler=Scheduler(enable_fuzzing=False), **options)


def drain(quiz, rating=Rating.Easy, correct=True):
    seen = []
    while (item := quiz.next()) is not None:
        seen.append(item.id)
        quiz.answer(rating, correct, 800)
    return seen


@pytest.fixture
def store(tmp_path):
    progress = ProgressStore(tmp_path / "p.sqlite", "atlas")
    yield progress
    progress.close()


def test_new_items_come_in_order_up_to_the_daily_limit(store):
    assert drain(session(store, make_items(5), Clock(), new_per_day=3)) == [1, 2, 3]


def test_the_daily_limit_counts_earlier_sessions_today(store):
    clock, items = Clock(), make_items(5)
    drain(session(store, items, clock, new_per_day=3))
    clock.advance(hours=1)
    assert drain(session(store, items, clock, new_per_day=3)) == []
    clock.advance(days=1)
    assert drain(session(store, items, clock, new_per_day=3)) == [4, 5]


def test_due_cards_come_before_new_ones(store):
    clock, items = Clock(), make_items(3)
    drain(session(store, items, clock, new_per_day=1))
    clock.advance(days=9)
    assert due_and_new(items, "find", store, clock(), 1) == ([1], [2])
    assert drain(session(store, items, clock, new_per_day=1)) == [1, 2]


def test_a_wrong_answer_returns_in_the_same_session(store):
    quiz = session(store, make_items(2), Clock())
    assert quiz.next().id == 1
    quiz.answer(Rating.Again, False, 800)
    assert quiz.next().id == 2
    quiz.answer(Rating.Easy, True, 800)
    assert quiz.next().id == 1
    quiz.answer(Rating.Easy, True, 800)
    assert quiz.next() is None


def test_a_learning_card_that_is_due_comes_first(store):
    clock = Clock()
    quiz = session(store, make_items(3), clock)
    quiz.next()
    quiz.answer(Rating.Again, False, 800)
    clock.advance(minutes=2)
    assert quiz.next().id == 1


def test_practice_shuffles_and_saves_nothing(store):
    quiz = Session(make_items(6), "find", store, practice=True, now=Clock(),
                   rng=random.Random(3))
    expected = [1, 2, 3, 4, 5, 6]
    random.Random(3).shuffle(expected)
    assert drain(quiz) == expected
    assert store.cards("find") == {} and store.review_count("find") == 0
    assert quiz.summary().due_tomorrow == 0


def test_answers_are_stored_with_the_fsrs_schedule(store):
    quiz = session(store, make_items(1), Clock())
    quiz.next()
    quiz.answer(Rating.Good, True, 1500)
    card = store.card(1, "find")
    assert card.state == State.Learning and card.due == T0 + timedelta(minutes=10)


def test_summary_counts_answers_and_most_missed(store):
    quiz = session(store, make_items(3), Clock())
    quiz.next()
    quiz.answer(Rating.Again, False, 800)
    quiz.next()
    quiz.answer(Rating.Easy, True, 800)
    quiz.next()
    quiz.answer(Rating.Easy, True, 800)
    summary = quiz.summary()
    assert (summary.answered, summary.correct, summary.percent) == (3, 2, 67)
    assert [item.id for item in summary.most_missed] == [1]
    assert summary.due_tomorrow == 1


def test_answering_without_a_question_raises(store):
    with pytest.raises(RuntimeError):
        session(store, make_items(1), Clock()).answer(Rating.Good, True, 100)
