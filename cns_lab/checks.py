from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cns_atlas.models import Check

from .engine import Run, Simulator
from .experiment import Block, Experiment
from .times import DAY


@dataclass(frozen=True)
class TestResult:
    test: str
    readings: tuple[float, ...]
    value: float
    normal: bool
    cutoff: float
    unit: str


@dataclass(frozen=True)
class CheckOutcome:
    key: str
    passed: bool
    detail: str


def clock_text(minutes: float) -> str:
    minutes = round(minutes) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def read_test(sim: Simulator, run: Run, block: Block) -> TestResult:
    test = next(t for t in sim.model.tests if t.key == block.experiment)
    readings = tuple(run.display(r.value, block.start + r.after) for r in test.readings)
    if test.rule == "suppressed by":
        others = tuple(b for b in run.experiment.blocks if b != block)
        without = sim.run(run.experiment.replace(blocks=others))
        first = test.readings[0]
        base = without.display(first.value, block.start + first.after)
        value = 1.0 - readings[0] / base if base else 0.0
        return TestResult(test.key, readings, value, value >= test.cutoff, test.cutoff, "fraction")
    value = max(readings)
    normal = value < test.cutoff if test.rule == "below" else value >= test.cutoff
    unit = sim.values[test.readings[0].value].display_unit
    return TestResult(test.key, readings, value, normal, test.cutoff, unit)


def _block(sim: Simulator, row: dict) -> Block:
    key = row["experiment"]
    experiment = next((e for e in sim.model.experiments if e.key == key), None)
    mode = row.get("mode", experiment.mode if experiment else "from a time")
    length = row.get("length", experiment.length if experiment else None)
    options = tuple(sorted(row.get("options", {}).items()))
    return Block(key, float(row.get("start", 0.0)), length, options, mode)


def _grid(run: Run, key: str, window) -> tuple[np.ndarray, np.ndarray]:
    grid = np.arange(window[0], window[1] + 0.5, 1.0)
    return grid, np.interp(grid, run.times, run.value(key))


def _in_clock(minutes: float, expect) -> bool:
    start, end = expect
    return start <= minutes <= end if start <= end else minutes >= start or minutes <= end


def _assert(sim: Simulator, run: Run, normal: Run, blocks: list[Block], row: dict) -> tuple:
    kind = row["kind"]
    clock0 = run.experiment.start_clock
    name = sim.values[row["value"]].name if "value" in row else ""
    if kind in ("peak_within", "trough_within"):
        grid, levels = _grid(run, row["value"], row["window"])
        at = grid[int(np.argmax(levels) if kind == "peak_within" else np.argmin(levels))]
        clock = (clock0 + at) % DAY
        word = "peaks" if kind == "peak_within" else "is lowest"
        return (_in_clock(clock, row["expect"]),
                f"{name} {word} at {clock_text(clock)}, expected {clock_text(row['expect'][0])} "
                f"to {clock_text(row['expect'][1])}")
    if kind == "within":
        level = run.display(row["value"], row["at"])
        unit = sim.values[row["value"]].display_unit
        return (row["low"] <= level <= row["high"],
                f"{name} is {level:.3g} {unit}, expected {row['low']} to {row['high']}")
    if kind in ("vs_normal", "back_to_normal"):
        at = row["at"] if kind == "vs_normal" else row["by"]
        base = normal.at(row["value"], at)
        ratio = run.at(row["value"], at) / base if base else float("inf")
        text = f"{name} is {ratio:.3g} times normal"
        if kind == "back_to_normal":
            return abs(ratio - 1) <= row["tolerance"], f"{text}, expected within {row['tolerance']}"
        if "rises" in row:
            return ratio >= row["rises"], f"{text}, expected at least {row['rises']}"
        return ratio <= row["falls"], f"{text}, expected at most {row['falls']}"
    if kind == "peak_before":
        first, then = sim.values[row["first"]].name, sim.values[row["then"]].name
        grid, a = _grid(run, row["first"], row["window"])
        _, b = _grid(run, row["then"], row["window"])
        ta, tb = grid[int(np.argmax(a))], grid[int(np.argmax(b))]
        return (ta < tb, f"{first} peaks at {clock_text(clock0 + ta)} and {then} at "
                         f"{clock_text(clock0 + tb)}, expected {first} first")
    result = read_test(sim, run, blocks[row["block"]])
    verdict = "normal" if result.normal else "abnormal"
    return (verdict == row["expect"],
            f"{result.test} gives {result.value:.3g} {result.unit} ({verdict}), "
            f"expected {row['expect']}")


def run_check(sim: Simulator, check: Check) -> CheckOutcome:
    model = sim.model
    blocks = [_block(sim, row) for row in check.blocks]
    experiment = Experiment(model.key, model.version, check.length, model.start_clock,
                            tuple(blocks))
    run = sim.run(experiment)
    normal = sim.normal(check.length, model.start_clock)
    failures, details = [], []
    for row in check.asserts:
        passed, detail = _assert(sim, run, normal, blocks, row)
        details.append(detail)
        if not passed:
            failures.append(detail)
    return CheckOutcome(check.key, not failures, "; ".join(failures or details))


def run_checks(sim: Simulator) -> list[CheckOutcome]:
    return [run_check(sim, check) for check in sim.model.checks]
