from __future__ import annotations

import random

from .answers import normalize
from .items import Item


def _answers(item: Item) -> set[str]:
    return {normalize(answer) for answer in item.answers}


def _common_ancestors(a: Item, b: Item) -> int:
    count = 0
    for x, y in zip(a.path[:-1], b.path[:-1]):
        if x != y:
            break
        count += 1
    return count


def choices(item: Item, pool: list[Item], rng: random.Random, count: int = 4) -> list[Item]:
    own = _answers(item)
    others = [o for o in pool
              if o.id != item.id and o.level == item.level and not own & _answers(o)]
    ranked = sorted(others, key=lambda o: (-_common_ancestors(item, o), rng.random()))
    picked = [item, *ranked[:count - 1]]
    rng.shuffle(picked)
    return picked
