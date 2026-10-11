from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .items import Item

SIDE_WORDS = frozenset({"left", "right", "bilateral"})
NON_WORD = re.compile(r"[\W_]+")


@dataclass(frozen=True)
class Verdict:
    correct: bool
    exact: bool
    matched: str


def normalize(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    words = [w for w in NON_WORD.sub(" ", plain.casefold()).split() if w not in SIDE_WORDS]
    if words[:1] == ["the"]:
        words = words[1:]
    return " ".join(words)


def word_set(normalized: str) -> frozenset[str]:
    return frozenset(w for w in normalized.split() if w != "of")


def allowance(length: int) -> int:
    return 0 if length <= 4 else 1 if length <= 8 else 2


def distance(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before: list[int] = []
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            value = min(previous[j] + 1, current[j - 1] + 1,
                        previous[j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                value = min(value, before[j - 2] + 1)
            current[j] = value
        if min(current) > limit:
            return limit + 1
        before, previous = previous, current
    return min(previous[-1], limit + 1)


class AnswerIndex:
    def __init__(self, pool: list[Item]) -> None:
        self.exact: dict[str, set[int]] = {}
        self.words: dict[frozenset[str], set[int]] = {}
        self.entries: list[tuple[str, int, str]] = []
        for item in pool:
            for answer in item.answers:
                text = normalize(answer)
                if not text:
                    continue
                self.exact.setdefault(text, set()).add(item.id)
                self.words.setdefault(word_set(text), set()).add(item.id)
                self.entries.append((text, item.id, answer))

    def check(self, typed: str, item: Item) -> Verdict:
        wrong = Verdict(False, False, item.name)
        text = normalize(typed)
        if not text:
            return wrong
        for table, key in ((self.exact, text), (self.words, word_set(text))):
            if key in table:
                return Verdict(True, True, item.name) if item.id in table[key] else wrong
        best: tuple[int, str] | None = None
        for answer_text, owner, answer in self.entries:
            if owner != item.id:
                continue
            limit = allowance(len(answer_text))
            found = distance(text, answer_text, limit)
            if found <= limit and (best is None or found < best[0]):
                best = (found, answer)
        if best is None:
            return wrong
        for answer_text, owner, _ in self.entries:
            if owner != item.id and distance(text, answer_text, best[0]) <= best[0]:
                return wrong
        return Verdict(True, False, best[1])
