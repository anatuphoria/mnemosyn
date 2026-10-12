from __future__ import annotations

from pathlib import Path

from cns_atlas.knowledge import CITATION
from cns_atlas.model import Pathway
from cns_atlas.timelines import Curve, Mark, Timeline

from .recipe import BuildError, read_toml

FIELDS = ("route", "duration", "unit", "play_seconds", "status", "note", "curves", "marks")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _curve_problems(curve, where: str, duration: float) -> list[str]:
    if not isinstance(curve, dict):
        return [f"{where}: must be a table"]
    problems = []
    if not (isinstance(curve.get("name"), str) and curve["name"].strip()):
        problems.append(f"{where}: needs a name")
    color = curve.get("color")
    if not (isinstance(color, list) and len(color) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in color)):
        problems.append(f"{where}: color must be three numbers from 0 to 255")
    points = curve.get("points")
    if not (isinstance(points, list) and len(points) >= 2
            and all(isinstance(p, list) and len(p) == 2 and all(map(_number, p)) for p in points)):
        return problems + [f"{where}: points must be at least two [time, level] pairs"]
    times = [t for t, _ in points]
    if any(b <= a for a, b in zip(times, times[1:])):
        problems.append(f"{where}: times must increase")
    if any(t < 0 or t > duration for t in times):
        problems.append(f"{where}: times must be within 0 and the duration")
    if any(v < 0 or v > 1 for _, v in points):
        problems.append(f"{where}: levels must be between 0 and 1")
    return problems


def _problems(data: dict, where: str, steps: dict[str, int], references) -> list[str]:
    problems = []
    unknown = set(data) - set(FIELDS)
    if unknown:
        problems.append(f"{where}: unknown keys {sorted(unknown)}")
    route = data.get("route")
    if not isinstance(route, str) or route not in steps:
        problems.append(f"{where}: unknown route {route!r}")
    duration, play = data.get("duration"), data.get("play_seconds", 30)
    if not (_number(duration) and duration > 0):
        problems.append(f"{where}: duration must be a positive number")
        duration = None
    if not (_number(play) and play > 0):
        problems.append(f"{where}: play_seconds must be a positive number")
    if not (isinstance(data.get("unit"), str) and data["unit"].strip()):
        problems.append(f"{where}: needs a unit")
    if data.get("status", "draft") not in ("draft", "reviewed"):
        problems.append(f"{where}: status must be draft or reviewed")
    note = data.get("note", "")
    if not isinstance(note, str):
        problems.append(f"{where}: note must be text")
    else:
        problems += [f"{where}: cites missing reference [{key}]"
                     for key in CITATION.findall(note) if key not in references]
    curves = data.get("curves")
    if not (isinstance(curves, list) and curves):
        problems.append(f"{where}: needs at least one curve")
    elif duration is not None:
        for n, curve in enumerate(curves, 1):
            problems += _curve_problems(curve, f"{where} curve {n}", duration)
    marks = data.get("marks")
    if not (isinstance(marks, list) and marks
            and all(isinstance(m, dict) and _number(m.get("time"))
                    and isinstance(m.get("step"), int) for m in marks)):
        return problems + [f"{where}: marks must be tables with a time and a step"]
    times = [m["time"] for m in marks]
    if any(b <= a for a, b in zip(times, times[1:])):
        problems.append(f"{where}: marks must be in time order")
    if duration is not None and any(t < 0 or t > duration for t in times):
        problems.append(f"{where}: marks must be within 0 and the duration")
    if isinstance(route, str) and route in steps:
        problems += [f"{where}: mark {n}: no step {m['step']} in route {route!r}"
                     for n, m in enumerate(marks, 1) if not 1 <= m["step"] <= steps[route]]
    return problems


def load_timelines(folder: Path, pathways: list[Pathway], references) -> list[Timeline]:
    if not folder.exists():
        return []
    steps = {p.key: len(p.steps) for p in pathways}
    problems: list[str] = []
    timelines: list[Timeline] = []
    for path in sorted(folder.glob("*.toml")):
        data = read_toml(path)
        found = _problems(data, str(path), steps, references)
        route = data.get("route")
        if isinstance(route, str) and path.stem != route:
            found.append(f"{path}: file name must be {route}.toml")
        problems += found
        if not found:
            curves = tuple(Curve(c["name"], tuple(c["color"]),
                                 tuple((float(t), float(v)) for t, v in c["points"]))
                           for c in data["curves"])
            marks = tuple(Mark(float(m["time"]), m["step"]) for m in data["marks"])
            timelines.append(Timeline(route, float(data["duration"]), data["unit"],
                                      float(data.get("play_seconds", 30)),
                                      data.get("status", "draft"), data.get("note", ""),
                                      curves, marks))
    if problems:
        raise BuildError(problems)
    return timelines
