from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from cns_atlas.models import LabModel, Value

from .engine import Run, Simulator
from .expressions import names

ZERO = 1e-12
ZERO_CHANGE = 100.0


@dataclass(frozen=True)
class Step:
    source: str
    kind: str
    text_key: str
    value: str | None
    ratio: float
    since: float | None


def phrase(value: Value | None, ratio: float) -> str:
    if not math.isfinite(ratio):
        return "rises from nothing"
    if abs(ratio - 1.0) <= 0.02:
        return "is unchanged"
    if ratio < 1.0:
        return f"falls to {round(ratio * 100)}% of normal"
    if ratio >= 1.5:
        return f"rises to {ratio:.1f} times normal"
    return f"rises by {round((ratio - 1.0) * 100)}%"


def normal_note(model: LabModel, clock: float) -> str | None:
    clock %= 1440
    for note in model.normal_notes:
        start, end = note.start_clock, note.end_clock
        inside = start <= clock < end if start <= end else clock >= start or clock < end
        if inside:
            return note.key
    return None


def _ratio(a: float, b: float) -> float:
    if abs(b) < ZERO:
        return 0.0 if abs(a) < ZERO else math.inf
    return a / b


def _changed(a: float, b: float, threshold: float) -> bool:
    if abs(a) < ZERO and abs(b) < ZERO:
        return False
    if abs(a) < ZERO or abs(b) < ZERO:
        return math.log(ZERO_CHANGE) >= math.log(1 + threshold)
    ratio = a / b
    return ratio <= 0 or abs(math.log(ratio)) >= math.log(1 + threshold)


class _Graph:
    def __init__(self, model: LabModel) -> None:
        self.readers: dict[str, list[str]] = {}
        for effect in model.effects:
            for name in names(effect.expr):
                self.readers.setdefault(name, []).append(f"effect:{effect.key}")
        for term in model.terms:
            for name in names(term.expr):
                self.readers.setdefault(name, []).append(f"term:{term.key}")
        self.term_value = {t.key: t.value for t in model.terms}

    def next(self, node: str) -> list[str]:
        kind, key = node.split(":", 1)
        if kind == "term":
            return [f"value:{self.term_value[key]}"]
        return self.readers.get(key, [])


def chain(sim: Simulator, run: Run, t: float, limit: int = 8) -> tuple[Step, ...]:
    model = sim.model
    graph = getattr(sim, "why_graph", None)
    if graph is None:
        graph = sim.why_graph = _Graph(model)
    experiment = run.experiment
    blocks = sorted(
        ((n, b) for n, b in enumerate(experiment.blocks) if b.present or b.start <= t),
        key=lambda item: (-math.inf if item[1].present else item[1].start, item[0]))
    if not blocks and not experiment.values:
        return ()
    normal = sim.normal(experiment.length, experiment.start_clock)
    mine, theirs = run.factors(t), normal.factors(t)
    params = sim.parameters_at(experiment, t)
    clamped = {sim.keys[i] for i in sim.clamps_at(experiment, t, params)}
    terms = {term.key: term for term in model.terms}
    effects = {effect.key: effect for effect in model.effects}
    experiments = {e.key: e for e in model.experiments}
    threshold = model.why_threshold

    found: list[tuple[tuple, Step]] = []
    seen: set[str] = set()
    # Slow values carry the effect of changes that have already ended, such as a past course.
    memory = [f"value:{v.key}" for v in model.values
              if v.slow and v.key not in clamped
              and _changed(run.at(v.key, t), normal.at(v.key, t), threshold)]

    def walk(queue, order: int, since: float | None) -> None:
        while queue:
            node, depth = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            kind, name = node.split(":", 1)
            if kind == "term" and terms[name].value in clamped:
                continue
            if kind in ("effect", "term"):
                if not _changed(mine[name], theirs[name], threshold):
                    continue
                if kind == "effect":
                    step = Step(name, effects[name].kind, f"effect.{name}", None,
                                _ratio(mine[name], theirs[name]), since)
                    size = abs(math.log(step.ratio)) if 0 < step.ratio < math.inf else 99.0
                    found.append(((depth, order, -size, name), step))
                elif terms[name].kind != "clears":
                    value = terms[name].value
                    ratio = _ratio(run.at(value, t), normal.at(value, t))
                    size = abs(math.log(ratio)) if 0 < ratio < math.inf else 99.0
                    found.append(((depth, order, -size, name),
                                  Step(name, terms[name].kind, f"term.{name}", value, ratio,
                                       since)))
            queue.extend((n, depth + 1) for n in graph.next(node))

    walk(deque((f"param:{key}", 1) for key, _ in experiment.values), -1, None)
    for order, (_, block) in enumerate(blocks):
        since = None if block.present else block.start
        is_test = block.experiment not in experiments
        key = f"test.{block.experiment}" if is_test else f"experiment.{block.experiment}"
        found.append(((0, order, 0.0, block.experiment),
                      Step(block.experiment, "change", key, None, 1.0, since)))
        if is_test:
            starts = [f"value:{v}" for _, v, _ in next(
                x for x in model.tests if x.key == block.experiment).doses]
        else:
            edits = experiments[block.experiment].edits
            starts = [f"{'value' if e.op in ('clamp', 'dose') else 'param'}:{e.target}"
                      for e in edits]
        walk(deque((node, 1) for node in starts), order, since)
    walk(deque((node, 1) for node in memory), len(blocks), None)
    found.sort(key=lambda item: item[0])
    return tuple(step for _, step in found[:limit])
