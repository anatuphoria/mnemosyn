from __future__ import annotations

import math
from dataclasses import dataclass, replace

PRESENT = "present"
FROM_A_TIME = "from a time"


@dataclass(frozen=True)
class Block:
    experiment: str
    start: float
    length: float | None = None
    options: tuple[tuple[str, float], ...] = ()
    mode: str = FROM_A_TIME

    @property
    def option_map(self) -> dict[str, float]:
        return dict(self.options)

    @property
    def present(self) -> bool:
        return self.mode == PRESENT

    def end(self, run_length: float) -> float:
        if self.present or self.length is None:
            return math.inf if self.present else run_length
        return self.start + self.length

    def active(self, t: float, run_length: float) -> bool:
        return self.present or self.start <= t < self.end(run_length)


@dataclass(frozen=True)
class Experiment:
    system: str
    version: int
    length: float
    start_clock: float
    blocks: tuple[Block, ...] = ()
    values: tuple[tuple[str, float], ...] = ()
    title: str = ""
    note: str = ""

    @property
    def value_map(self) -> dict[str, float]:
        return dict(self.values)

    def replace(self, **changes) -> Experiment:
        return replace(self, **changes)
