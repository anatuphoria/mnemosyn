from __future__ import annotations

import random
import zlib

from cns_atlas import Atlas, Crossing, Relay
from cns_atlas.pathways import lights

from .items import Item, items
import itertools

ROUTE_MODE, LAB_MODE = "route-next", "lab-predict"
QUESTION_MODES = {"routes": ROUTE_MODE, "lab": LAB_MODE}
HIGHER, LOWER, NORMAL = "Higher than normal", "Lower than normal", "About normal"
OUTCOMES = (HIGHER, LOWER, NORMAL)
PRESENT = "present"
DAY, HOUR = 1440.0, 60.0


def stable_id(text: str) -> int:
    return zlib.crc32(text.encode("utf-8")) & 0x7FFFFFFF


def station_name(atlas: Atlas, step) -> str:
    if isinstance(step, Crossing | Relay):
        return step.name
    return " and ".join(atlas.get(i).name for i in step.structures)


def route_items(atlas: Atlas) -> list[Item]:
    found = []
    for pathway in atlas.pathways:
        names = [station_name(atlas, step) for step in pathway.steps]
        lit = lights(atlas, pathway, "left")
        after: dict[str, set[str]] = {}
        for here, following in itertools.pairwise(names):
            after.setdefault(here, set()).add(following)
        for n, (here, following) in enumerate(itertools.pairwise(names)):
            others = tuple(dict.fromkeys(name for name in names if name not in (here, following)))
            if here == following or len(after[here]) > 1 or len(others) < 2:
                continue
            found.append(Item(
                stable_id(f"route:{pathway.key}:{here}>{following}"), "routes",
                f"{pathway.name}: after {here}", "", (following,), frozenset(lit[n]), (),
                prompt=f"{pathway.name}. After {here}, what comes next?", answer=following,
                options=others, reveal=frozenset(lit[n + 1]),
                note=f"Step {n + 2} of {len(names)} in this route.", scope=pathway.group))
    return found


def span_text(minutes: float) -> str:
    if minutes >= 2 * DAY:
        count, word = round(minutes / DAY), "day"
    elif minutes >= HOUR:
        count, word = round(minutes / HOUR, 1), "hour"
    else:
        count, word = round(minutes), "minute"
    return f"{count:g} {word}" if count == 1 else f"{count:g} {word}s"


def moment_text(minutes: float, start_clock: float) -> str:
    clock = (start_clock + minutes) % DAY
    return f"day {int((start_clock + minutes) // DAY) + 1} at {int(clock // 60):02d}:{int(clock % 60):02d}"


def _setting(model, check) -> tuple[str, float, float] | None:
    names, starts, ends = [], [], []
    for row in check.blocks:
        experiment = next((e for e in model.experiments if e.key == row["experiment"]), None)
        if experiment is None:
            return None
        names.append(experiment.name)
        if row.get("mode", experiment.mode) != PRESENT:
            start = float(row.get("start", 0.0))
            length = row.get("length", experiment.length)
            starts.append(start)
            ends.append(start + float(length) if length else start)
    if not names:
        return None
    return ", then ".join(names), (max(starts) if starts else -1.0), max(ends, default=-1.0)


def _when(at: float, start: float, end: float, start_clock: float, fine: bool = False) -> str:
    if start < 0 or at <= start:
        return f"After {span_text(at)}" if fine else f"On {moment_text(at, start_clock)}"
    if end > start and at > end:
        return f"{span_text(at - end)} after it ends".capitalize()
    if end > start:
        return f"{span_text(at - start)} after it starts".capitalize()
    return f"{span_text(at - start)} later".capitalize()


def _outcome(row: dict) -> tuple[str, float, str] | None:
    if row["kind"] == "vs_normal":
        if "rises" in row:
            return HIGHER, row["at"], f"at least {row['rises']:g} times normal"
        return LOWER, row["at"], f"at most {row['falls']:g} times normal"
    if row["kind"] == "back_to_normal":
        return NORMAL, row["by"], f"within {100 * row['tolerance']:g}% of normal again"
    return None


def lab_items(atlas: Atlas) -> list[Item]:
    found = []
    for model in atlas.models.values():
        for check in model.checks:
            setting = _setting(model, check)
            if setting is None:
                continue
            change, start, end = setting
            for row in check.asserts:
                outcome = _outcome(row)
                if outcome is None:
                    continue
                answer, at, measure = outcome
                value = model.value(row["value"]).name
                when = _when(at, start, end, model.start_clock, model.scale == "minutes")
                found.append(Item(
                    stable_id(f"lab:{model.key}:{check.key}:{row['value']}:{at:g}"), "lab",
                    f"{change}: {value}", "", (answer,), frozenset(), (),
                    prompt=f"{model.name}. {change}. {when}, {value} is:", answer=answer,
                    options=tuple(o for o in OUTCOMES if o != answer),
                    note=f"In the model, {value} is {measure}.", scope=model.key,
                    source=(model.key, check.key, float(at))))
    return found


def question_items(atlas: Atlas, level: str, scope: str | None = None) -> list[Item]:
    pool = {"routes": route_items, "lab": lab_items}[level](atlas)
    return pool if scope is None else [item for item in pool if item.scope == scope]


def pool_for(atlas: Atlas, level: str, scope=None) -> list[Item]:
    if level in QUESTION_MODES:
        return question_items(atlas, level, scope)
    return items(atlas, level, scope)


def scopes(atlas: Atlas, level: str) -> list[tuple[str, str]]:
    if level == "lab":
        return [(model.name, key) for key, model in atlas.models.items()]
    return [(group, group) for group in dict.fromkeys(p.group for p in atlas.pathways)]


def offered(item: Item, rng: random.Random, count: int = 4) -> list[str]:
    wrong = list(item.options)
    rng.shuffle(wrong)
    if item.level == "lab":
        return list(OUTCOMES)
    picked = [item.answer, *wrong[:count - 1]]
    rng.shuffle(picked)
    return picked
