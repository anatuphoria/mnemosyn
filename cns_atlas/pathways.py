from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .knowledge import Entry, Reference
from .model import Station, Step, Structure

START_SIDES = ("left", "right")
LABELS = ("Role:", "Lesion:")
SIDE_WORD = re.compile(r"\{([^{}\n]*)\}")


@dataclass(frozen=True)
class StepText:
    role: str
    lesion: str


@dataclass(frozen=True)
class PathwayText:
    status: str
    overview: str
    steps: tuple[StepText, ...]
    references: tuple[Reference, ...]


def other_side(side: str) -> str:
    return {"left": "right", "right": "left"}[side]


def side_of(step_side: str, start_side: str) -> str:
    if step_side == "midline":
        return "midline"
    return start_side if step_side == "same" else other_side(start_side)


def lit(structures: Sequence[Structure], has_shape: Callable[[int], bool], step: Step,
        start_side: str) -> tuple[int, ...]:
    if not isinstance(step, Station):
        return ()
    sides = {side_of(step.side, start_side), "midline", "none"}
    wanted = set(step.structures)
    return tuple(s.id for s in structures
                 if s.side in sides and wanted.intersection(s.structure_id_path)
                 and has_shape(s.id))


def resolve(atlas, step: Step, start_side: str) -> tuple[int, ...]:
    return lit(atlas.structures, atlas.has_mesh, step, start_side)


def fill(text: str, side: str) -> str:
    return text.replace("{same}", side).replace("{opposite}", other_side(side))


def unknown_side_words(text: str) -> list[str]:
    return [word for word in SIDE_WORD.findall(text) if word not in ("same", "opposite")]


def step_problems(body: str) -> list[str]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    problems = []
    for label in LABELS:
        found = [line for line in lines if line.startswith(label)]
        if len(found) != 1:
            problems.append(f"needs one '{label}' line, found {len(found)}")
        elif not found[0][len(label):].strip():
            problems.append(f"'{label}' line is empty")
    problems += [f"unexpected line {line!r}" for line in lines if not line.startswith(LABELS)]
    return problems


def step_text(body: str) -> StepText:
    lines = [line.strip() for line in body.splitlines()]
    role, lesion = (next((line[len(label):].strip() for line in lines if line.startswith(label)),
                         "") for label in LABELS)
    return StepText(role, lesion)


def text_for(entry: Entry, count: int, side: str) -> PathwayText:
    if side not in START_SIDES:
        raise ValueError(f"side must be left or right, got {side!r}")

    def show(text: str) -> str:
        return entry.numbered(fill(text, side))

    parsed = (step_text(entry.sections.get(f"Step {n}", "")) for n in range(1, count + 1))
    steps = tuple(StepText(show(t.role), show(t.lesion)) for t in parsed)
    return PathwayText(entry.status, show(entry.sections.get("Overview", "")), steps,
                       entry.references)
