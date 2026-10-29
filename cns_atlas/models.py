from __future__ import annotations

from dataclasses import dataclass, fields
from typing import ClassVar


def _plain(value):
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if hasattr(value, "to_json"):
        return value.to_json()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _tuple(value):
    if isinstance(value, list):
        return tuple(_tuple(v) for v in value)
    return value


class _Record:
    NESTED: ClassVar[dict] = {}

    def to_json(self) -> dict:
        return {f.name: _plain(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_json(cls, data: dict):
        if not isinstance(data, dict):
            raise TypeError(f"{cls.__name__}: expected an object")
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"{cls.__name__}: unknown fields {sorted(unknown)}")
        values = {}
        for name, raw in data.items():
            nested = cls.NESTED.get(name)
            if nested is dict:
                values[name] = tuple(dict(item) for item in raw)
            elif nested is not None:
                values[name] = tuple(nested.from_json(item) for item in raw)
            else:
                values[name] = _tuple(raw)
        return cls(**values)


@dataclass(frozen=True)
class Value(_Record):
    key: str
    name: str
    unit: str
    start: float
    display_scale: float
    display_unit: str
    other_unit: str = ""
    other_scale: float = 0.0
    relative: bool = False
    normal: tuple[float, float] | None = None
    lane: int | None = None
    slow: bool = False
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Parameter(_Record):
    key: str
    name: str
    value: float
    unit: str
    low: float
    high: float
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Effect(_Record):
    key: str
    expr: str
    kind: str
    arrow: tuple[str, str] | None = None


@dataclass(frozen=True)
class Term(_Record):
    key: str
    value: str
    sign: int
    expr: str
    kind: str
    arrow: tuple[str, str] | None = None


@dataclass(frozen=True)
class Part(_Record):
    key: str
    name: str
    structure: int | None
    x: float
    y: float
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Edit(_Record):
    op: str
    target: str
    expr: str
    daily: bool = False


@dataclass(frozen=True)
class Option(_Record):
    key: str
    name: str
    unit: str
    default: float
    low: float
    high: float


@dataclass(frozen=True)
class Experiment(_Record):
    key: str
    group: str
    name: str
    mode: str
    length: float | None
    options: tuple[Option, ...] = ()
    edits: tuple[Edit, ...] = ()
    weeks: bool = False
    icon: str = ""

    NESTED: ClassVar[dict] = {"options": Option, "edits": Edit}


@dataclass(frozen=True)
class Reading(_Record):
    value: str
    after: float


@dataclass(frozen=True)
class LabTest(_Record):
    key: str
    name: str
    doses: tuple[tuple[float, str, str], ...]
    readings: tuple[Reading, ...]
    rule: str
    cutoff: float
    icon: str = ""

    NESTED: ClassVar[dict] = {"readings": Reading}


@dataclass(frozen=True)
class Check(_Record):
    key: str
    length: float
    blocks: tuple[dict, ...] = ()
    asserts: tuple[dict, ...] = ()

    NESTED: ClassVar[dict] = {"blocks": dict, "asserts": dict}


@dataclass(frozen=True)
class NormalNote(_Record):
    key: str
    start_clock: float
    end_clock: float


@dataclass(frozen=True)
class LabModel(_Record):
    key: str
    name: str
    version: int
    route: str | None
    start_clock: float
    settle_speedup: float
    settle_days: int
    max_step: float
    why_threshold: float
    values: tuple[Value, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    effects: tuple[Effect, ...] = ()
    terms: tuple[Term, ...] = ()
    parts: tuple[Part, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    tests: tuple[LabTest, ...] = ()
    checks: tuple[Check, ...] = ()
    normal_notes: tuple[NormalNote, ...] = ()

    NESTED: ClassVar[dict] = {"values": Value, "parameters": Parameter, "effects": Effect, "terms": Term,
              "parts": Part, "experiments": Experiment, "tests": LabTest, "checks": Check,
              "normal_notes": NormalNote}

    def value(self, key: str) -> Value:
        return next(v for v in self.values if v.key == key)

    def parameter(self, key: str) -> Parameter:
        return next(p for p in self.parameters if p.key == key)

    def experiment(self, key: str) -> Experiment:
        return next(e for e in self.experiments if e.key == key)

    def part(self, key: str) -> Part:
        return next(p for p in self.parts if p.key == key)
