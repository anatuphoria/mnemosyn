from __future__ import annotations

import json
import math
import tomllib
from pathlib import Path

from cns_atlas.models import LabModel

from .experiment import FROM_A_TIME, PRESENT, Block, Experiment
from .times import UNITS, TimeError, clock, duration

EXTENSION = ".mnemolab"
FORMAT = 1
SHORTEST = 60.0
LONGEST = 8 * 7 * 1440.0


class FileError(Exception):
    pass


def _string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _number(value: float) -> str:
    return repr(float(value))


def duration_text(minutes: float) -> str:
    for unit in ("w", "d", "h"):
        count = minutes / UNITS[unit]
        if count >= 1 and count == int(count):
            return f"{int(count)} {unit}"
    return f"{minutes:g} min"


def _clock_text(minutes: float) -> str:
    minutes = round(minutes) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def write(path: Path, experiment: Experiment) -> None:
    lines = [f"format = {FORMAT}", f"system = {_string(experiment.system)}",
             f"model_version = {experiment.version}",
             f"length = {_string(duration_text(experiment.length))}",
             f"start_clock = {_string(_clock_text(experiment.start_clock))}",
             f"title = {_string(experiment.title)}", f"note = {_string(experiment.note)}", "",
             "[values]"]
    lines += [f"{key} = {_number(value)}" for key, value in experiment.values]
    for block in experiment.blocks:
        lines += ["", "[[blocks]]", f"experiment = {_string(block.experiment)}",
                  f"start = {_number(block.start)}"]
        if block.length is not None:
            lines.append(f"length = {_string(duration_text(block.length))}")
        lines += [f"mode = {_string(block.mode)}", "", "[blocks.options]"]
        lines += [f"{key} = {_number(value)}" for key, value in block.options]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _finite(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _clamped(name: str, unit: str, value: float, low: float, high: float,
             report: list[str]) -> float:
    if low <= value <= high:
        return value
    kept = min(max(value, low), high)
    report.append(f"{name} was {value:g} {unit}, outside {low:g} to {high:g}; it is now {kept:g}.")
    return kept


def read(path: Path, models: dict[str, LabModel]) -> tuple[Experiment, tuple[str, ...]]:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise FileError("This file cannot be read as a Lab experiment.") from exc
    if data.get("format") != FORMAT:
        raise FileError("This file is not a Lab experiment this version of Mnemosyn can open.")
    system = data.get("system")
    model = models.get(system) if isinstance(system, str) else None
    if model is None:
        raise FileError(f"This file is for a system this atlas does not have: {system!r}.")
    try:
        length = duration(data["length"])
        start_clock = clock(data.get("start_clock", "08:00"))
        version = int(data["model_version"])
        values = data.get("values", {})
        rows = data.get("blocks", [])
        if not isinstance(values, dict) or not isinstance(rows, list):
            raise TypeError("values and blocks")
    except (KeyError, TypeError, ValueError, TimeError) as exc:
        raise FileError("This file cannot be read as a Lab experiment.") from exc
    report: list[str] = []
    if not SHORTEST <= length <= LONGEST:
        kept = min(max(length, SHORTEST), LONGEST)
        report.append(f"The run was {duration_text(length)} long; it is now "
                      f"{duration_text(kept)}.")
        length = kept
    if version != model.version:
        report.append(f"This file was made with version {version} of the model; "
                      f"this is version {model.version}.")
    parameters = {p.key: p for p in model.parameters}
    kept_values = []
    for key, value in values.items():
        parameter = parameters.get(key)
        if parameter is None:
            report.append(f"The value {key} is not in this model and was left out.")
            continue
        if not _finite(value):
            report.append(f"The value {key} is not a number and was left out.")
            continue
        kept_values.append((key, _clamped(parameter.name, parameter.unit, float(value),
                                          parameter.low, parameter.high, report)))
    experiments = {e.key: e for e in model.experiments}
    tests = {t.key: t for t in model.tests}
    blocks = []
    for row in rows:
        key = row.get("experiment") if isinstance(row, dict) else None
        found = experiments.get(key) if isinstance(key, str) else None
        if found is None and not (isinstance(key, str) and key in tests):
            report.append(f"The change {key} is not in this model and was left out.")
            continue
        name = found.name if found else tests[key].name
        mode = row.get("mode", FROM_A_TIME)
        if mode not in (PRESENT, FROM_A_TIME) or (mode == PRESENT and not (
                found and found.mode == PRESENT)):
            mode = FROM_A_TIME
        start = row.get("start", 0.0)
        start = float(start) if _finite(start) else 0.0
        if mode == PRESENT:
            start = 0.0
        elif start < 0:
            report.append(f"{name} started before the run and was moved to its start.")
            start = 0.0
        elif start > length - 1:
            report.append(f"{name} started after the end of the run and was moved to its end.")
            start = length - 1
        block_length = found.length if found else None
        if block_length is not None and "length" in row:
            try:
                block_length = duration(row["length"])
            except TimeError:
                pass
        if block_length is not None:
            block_length = max(block_length, 1.0)
            if start + block_length > length:
                report.append(f"{name} lasted past the end of the run and now ends with it.")
                block_length = max(length - start, 1.0)
        options = []
        given = row.get("options", {}) if isinstance(row.get("options", {}), dict) else {}
        known = {o.key: o for o in found.options} if found else {}
        for option_key, value in given.items():
            option = known.get(option_key)
            if option is None:
                report.append(f"The option {option_key} of {name} is not in this model and "
                              "was left out.")
                continue
            if not _finite(value):
                report.append(f"The option {option_key} of {name} is not a number and was "
                              "left out.")
                continue
            options.append((option_key, _clamped(f"{option.name} of {name}", option.unit,
                                                 float(value), option.low, option.high, report)))
        blocks.append(Block(key, start, block_length, tuple(options), mode))
    title = data.get("title", "") if isinstance(data.get("title", ""), str) else ""
    note = data.get("note", "") if isinstance(data.get("note", ""), str) else ""
    experiment = Experiment(model.key, model.version, length, start_clock, tuple(blocks),
                            tuple(kept_values), title, note)
    return experiment, tuple(report)
