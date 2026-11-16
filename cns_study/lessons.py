from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path

FORMAT = 1
EXTENSION = ".mnemolesson"
KINDS = ("view", "route", "lab", "quiz", "lesion")
WORKSPACES = ("Explore", "Slices")
AXES = ("axial", "coronal", "sagittal")
SIDES = ("left", "right")
LEVELS = ("structures", "groups", "tracts", "routes", "lab")
MODES = ("name-typed", "name-choice", "find", "route-next", "lab-predict")
MAX_BYTES = 2_000_000
MAX_STEPS = 200
MAX_TITLE = 200
MAX_NOTE = 4000
MAX_IDS = 20_000
MAX_MASKS = 8
MAX_SIDE = 2048
MAX_VOXELS = 64_000_000
MAX_BITS = 1_500_000
NOT_A_LESSON = "This file cannot be read as a lesson."
NEWER = "This lesson was made with a newer version of Mnemosyn."


class LessonError(Exception):
    pass


@dataclass(frozen=True)
class Step:
    kind: str
    title: str = ""
    note: str = ""
    data: dict = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class Lesson:
    title: str = ""
    author: str = ""
    atlas: str = ""
    steps: tuple[Step, ...] = ()

    def with_step(self, step: Step, at: int | None = None) -> Lesson:
        steps = list(self.steps)
        steps.insert(len(steps) if at is None else at, step)
        return replace(self, steps=tuple(steps))

    def without(self, index: int) -> Lesson:
        return replace(self, steps=self.steps[:index] + self.steps[index + 1:])

    def moved(self, index: int, by: int) -> Lesson:
        target = index + by
        if not (0 <= index < len(self.steps) and 0 <= target < len(self.steps)):
            return self
        steps = list(self.steps)
        steps.insert(target, steps.pop(index))
        return replace(self, steps=tuple(steps))

    def changed(self, index: int, **fields) -> Lesson:
        steps = list(self.steps)
        steps[index] = replace(steps[index], **fields)
        return replace(self, steps=tuple(steps))


def _fail(what: str) -> LessonError:
    return LessonError(f"{NOT_A_LESSON} ({what})")


def _text(value, limit: int, what: str) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise _fail(f"{what} is not a text of at most {limit} characters")
    return value


def _number(value, what: str, low: float = -math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise _fail(f"{what} is not a number")
    if value < low:
        raise _fail(f"{what} is too small")
    return float(value)


def _whole(value, what: str, low: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise _fail(f"{what} is not a whole number")
    return value


def _one_of(value, allowed, what: str):
    if value not in allowed:
        raise _fail(f"{what} must be one of {', '.join(map(str, allowed))}")
    return value


def _camera(value):
    if value is None:
        return None
    if not (isinstance(value, list) and len(value) == 3
            and all(isinstance(row, list) and len(row) == 3 for row in value)):
        raise _fail("the camera is not three points")
    return [[_number(v, "a camera value") for v in row] for row in value]


def _view(data: dict) -> dict:
    hidden = data.get("hidden", [])
    if not isinstance(hidden, list) or len(hidden) > MAX_IDS:
        raise _fail("the hidden structures are not a list")
    selected = data.get("selected")
    return {"workspace": _one_of(data.get("workspace", "Explore"), WORKSPACES, "the workspace"),
            "selected": None if selected is None else _whole(selected, "the selection"),
            "hidden": [_whole(i, "a hidden structure") for i in hidden],
            "camera": _camera(data.get("camera")),
            "axis": _one_of(data.get("axis", "axial"), AXES, "the slice axis"),
            "mm": _number(data.get("mm", 0.0), "the slice position"),
            "volume": _text(data.get("volume", ""), MAX_TITLE, "the slice volume")}


def _route(data: dict) -> dict:
    return {"key": _text(data.get("key"), MAX_TITLE, "the route"),
            "side": _one_of(data.get("side", "left"), SIDES, "the side"),
            "index": _whole(data.get("index", 0), "the route step")}


def _lab(data: dict) -> dict:
    return {"experiment": _text(data.get("experiment"), 200_000, "the experiment"),
            "playhead": _number(data.get("playhead", 0.0), "the playhead", 0.0)}


def _quiz(data: dict) -> dict:
    scope = data.get("scope")
    if scope is not None and (isinstance(scope, bool) or not isinstance(scope, int | str)):
        raise _fail("the quiz scope is not a structure or a name")
    if isinstance(scope, str):
        _text(scope, MAX_TITLE, "the quiz scope")
    return {"level": _one_of(data.get("level"), LEVELS, "the quiz level"),
            "mode": _one_of(data.get("mode"), MODES, "the quiz mode"), "scope": scope}


def _mask(row) -> dict:
    if not isinstance(row, dict):
        raise _fail("a lesion image is not an object")
    shape = row.get("shape")
    if not isinstance(shape, list) or len(shape) != 3:
        raise _fail("a lesion image does not have three sides")
    shape = [_whole(n, "a lesion image side", 1) for n in shape]
    if max(shape) > MAX_SIDE or shape[0] * shape[1] * shape[2] > MAX_VOXELS:
        raise _fail("a lesion image is too large")
    return {"shape": shape, "bits": _text(row.get("bits"), MAX_BITS, "a lesion image")}


def _lesion(data: dict) -> dict:
    masks = data.get("masks")
    if not isinstance(masks, dict) or not masks or len(masks) > MAX_MASKS:
        raise _fail("the lesion has no images")
    return {"masks": {_text(name, MAX_TITLE, "a lesion image name"): _mask(row)
                      for name, row in masks.items()},
            "camera": _camera(data.get("camera"))}


CHECKS = {"view": _view, "route": _route, "lab": _lab, "quiz": _quiz, "lesion": _lesion}


def _step(row) -> Step:
    if not isinstance(row, dict):
        raise _fail("a step is not an object")
    kind = _one_of(row.get("kind"), KINDS, "a step's kind")
    data = row.get("data", {})
    if not isinstance(data, dict):
        raise _fail("a step's content is not an object")
    return Step(kind, _text(row.get("title", ""), MAX_TITLE, "a step's title"),
                _text(row.get("note", ""), MAX_NOTE, "a step's note"), CHECKS[kind](data))


def loads(text: str) -> Lesson:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise LessonError(NOT_A_LESSON) from exc
    if not isinstance(data, dict) or data.get("mnemosyn") != "lesson":
        raise LessonError(NOT_A_LESSON)
    version = data.get("format")
    if isinstance(version, int) and not isinstance(version, bool) and version > FORMAT:
        raise LessonError(NEWER)
    if isinstance(version, bool) or version != FORMAT:
        raise LessonError(NOT_A_LESSON)
    steps = data.get("steps", [])
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise _fail(f"it must hold at most {MAX_STEPS} steps")
    return Lesson(_text(data.get("title", ""), MAX_TITLE, "the title"),
                  _text(data.get("author", ""), MAX_TITLE, "the author"),
                  _text(data.get("atlas", ""), MAX_TITLE, "the atlas"),
                  tuple(_step(row) for row in steps))


def dumps(lesson: Lesson) -> str:
    steps = [{"kind": s.kind, "title": s.title, "note": s.note, "data": s.data}
             for s in lesson.steps]
    return json.dumps({"mnemosyn": "lesson", "format": FORMAT, "title": lesson.title,
                       "author": lesson.author, "atlas": lesson.atlas, "steps": steps},
                      indent=1, ensure_ascii=False) + "\n"


def read(path: Path) -> Lesson:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_BYTES:
            raise LessonError(f"{NOT_A_LESSON} (it is too large)")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LessonError(NOT_A_LESSON) from exc
    return loads(text)


def write(path: Path, lesson: Lesson) -> Path:
    path = Path(path)
    if path.suffix != EXTENSION:
        path = path.with_suffix(EXTENSION)
    loads(dumps(lesson))
    path.write_text(dumps(lesson), encoding="utf-8")
    return path
