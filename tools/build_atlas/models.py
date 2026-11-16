from __future__ import annotations

import keyword
import tomllib
from pathlib import Path

from cns_atlas.knowledge import CITATION
from cns_atlas.models import (CONTROLS, Check, Curve, Edit, Effect, Experiment, LabModel, LabTest,
                              NormalNote, Option, Parameter, Part, Reading, Stop, Term, Value)
from cns_lab.expressions import CONSTANTS, FUNCTIONS, ExpressionError, compile_function, names
from cns_lab.engine import Simulator
from cns_lab.times import TimeError, clock, duration, moment

from .recipe import BuildError, read_toml

SCALES = ("hours", "minutes")
TOP = {"key", "version", "route", "start_clock", "settle_speedup", "settle_days", "max_step",
       "period", "scale",
       "why_threshold", "why_unchanged", "values", "parameters", "effects", "terms", "parts", "experiments",
       "tests", "checks", "normal", "curves"}
FIELDS = {
    "values": {"key", "unit", "start", "display_scale", "display_unit", "other_unit",
               "other_scale", "relative", "normal", "lane", "slow", "refs"},
    "parameters": {"key", "value", "unit", "low", "high", "refs", "panel", "group", "control",
                   "stops"},
    "curves": {"key", "parameters", "x_low", "x_high", "expr", "matches", "input"},
    "effects": {"key", "expr", "kind", "arrow", "via"},
    "terms": {"key", "value", "sign", "expr", "kind", "arrow", "via"},
    "parts": {"key", "structure", "x", "y", "values"},
    "experiments": {"key", "group", "mode", "length", "options", "edits", "weeks", "icon"},
    "tests": {"key", "doses", "readings", "rule", "cutoff", "icon", "edits", "length"},
    "checks": {"key", "length", "blocks", "asserts"},
    "normal": {"key", "from", "to"},
}
ICONS = frozenset(path.stem for path in
                  (Path(__file__).resolve().parents[2] / "cns_desktop" / "resources" / "icons")
                  .glob("*.svg"))
EFFECT_KINDS = {"drives", "holds back"}
TERM_KINDS = {"drives", "clears", "grows", "shrinks", "absorbs"}
MODES = {"from a time", "present"}
PARAMETER_OPS = {"set", "add", "scale"}
VALUE_OPS = {"clamp", "dose"}
RULES = {"below", "at least", "suppressed by", "rises by"}
ASSERTS = {
    "peak_within": {"value", "window", "expect"},
    "trough_within": {"value", "window", "expect"},
    "within": {"value", "at", "low", "high"},
    "vs_normal": {"value", "at"},
    "peak_before": {"first", "then", "window"},
    "back_to_normal": {"value", "by", "tolerance"},
    "test_result": {"block", "expect"},
}


RESERVED = {"t", "clock", *CONSTANTS, *FUNCTIONS}


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _icon(r, row: dict, where: str) -> str:
    icon = row.get("icon", "")
    if not isinstance(icon, str) or (icon and icon not in ICONS):
        r.say(f"{where}: unknown icon {icon!r}")
        return ""
    return icon


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


class _Reader:
    def __init__(self, where: str) -> None:
        self.where = where
        self.problems: list[str] = []

    def say(self, text: str) -> None:
        self.problems.append(f"{self.where}: {text}")

    def rows(self, data: dict, section: str) -> list[dict]:
        rows = data.get(section, [])
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            self.say(f"{section} must be a list of tables")
            return []
        good = []
        for n, row in enumerate(rows, 1):
            unknown = set(row) - FIELDS[section]
            if unknown:
                self.say(f"{section} {n}: unknown keys {sorted(unknown)}")
            if not (isinstance(row.get("key"), str) and row["key"].isidentifier()):
                self.say(f"{section} {n}: needs a key made of letters, digits and _")
                continue
            if row["key"] in RESERVED or row["key"].startswith("_") or keyword.iskeyword(
                    row["key"]):
                self.say(f"{section} {n}: reserved name {row['key']!r} cannot be a key")
                continue
            good.append(row)
        keys = [r["key"] for r in good]
        for key in sorted({k for k in keys if keys.count(k) > 1}):
            self.say(f"{section}: key {key!r} is used twice")
        return good

    def expr(self, text, allowed: set[str], where: str) -> str:
        if not isinstance(text, str):
            self.say(f"{where}: expr must be text")
            return "0"
        try:
            unknown = names(text) - allowed
        except ExpressionError as exc:
            self.say(f"{where}: {exc}")
            return "0"
        if unknown:
            self.say(f"{where}: unknown names {sorted(unknown)}")
        return text

    def time(self, parse, text, where: str, default: float = 0.0) -> float:
        try:
            return parse(text)
        except TimeError as exc:
            self.say(f"{where}: {exc}")
            return default

    def refs(self, row: dict, references, where: str) -> tuple[str, ...]:
        refs = row.get("refs", [])
        if not (isinstance(refs, list) and all(isinstance(r, str) for r in refs)):
            self.say(f"{where}: refs must be a list of reference keys")
            return ()
        for ref in refs:
            if ref not in references:
                self.say(f"{where}: cites missing reference [{ref}]")
        return tuple(refs)

    def ranged(self, row: dict, value_key: str, where: str) -> bool:
        low, high, value = row.get("low"), row.get("high"), row.get(value_key)
        if not all(_number(v) for v in (low, high, value)):
            self.say(f"{where}: {value_key}, low and high must be numbers")
            return False
        if not low <= value <= high:
            self.say(f"{where}: {value_key} {value} is outside {low} to {high}")
            return False
        return True


def _texts(path: Path, reader: _Reader) -> dict[str, str]:
    if not path.exists():
        reader.say(f"texts file {path} is missing")
        return {}
    try:
        table = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        reader.say(f"{path}: {exc}")
        return {}
    out: dict[str, str] = {}

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value, f"{prefix}{key}.")
            elif isinstance(value, str):
                out[f"{prefix}{key}"] = value
            else:
                reader.say(f"{path}: {prefix}{key} must be text")

    walk(table, "")
    return out


def _setting_kind(r: _Reader, row: dict, where: str, ok: bool, text) -> tuple[str, str, tuple]:
    key = row["key"]
    group = row.get("group", "")
    if not isinstance(group, str) or (group and not group.isidentifier()):
        r.say(f"{where}: group must be a key made of letters, digits and _")
        group = ""
    if group:
        text(f"group.{group}.name")
    control = row.get("control", "slider")
    if control not in CONTROLS:
        r.say(f"{where}: control must be one of {', '.join(CONTROLS)}")
        control = "slider"
    if control == "rate" and ok and not row["low"] > 0:
        r.say(f"{where}: a rate needs low above 0")
    raw = row.get("stops", [])
    stops = []
    if not isinstance(raw, list) or not all(isinstance(s, dict) for s in raw):
        r.say(f"{where}: stops must be a list of {{ key, value }} tables")
        raw = []
    for stop in raw:
        name, value = stop.get("key"), stop.get("value")
        if set(stop) - {"key", "value"} or not (isinstance(name, str) and name.isidentifier()) \
                or not _number(value):
            r.say(f"{where}: each stop needs a key and a number value")
            continue
        if ok and not row["low"] <= value <= row["high"]:
            r.say(f"{where}: stop {name} is outside {row['low']} to {row['high']}")
        stops.append(Stop(name, text(f"parameter.{key}.stop.{name}"), float(value)))
    if len({s.key for s in stops}) != len(stops):
        r.say(f"{where}: stop keys must differ")
    if control == "switch" and len(stops) < 2:
        r.say(f"{where}: a switch needs at least two stops")
    if stops and control != "switch":
        r.say(f"{where}: only a switch has stops")
    return group, control, tuple(stops)


def _curves(r: _Reader, data: dict, parameters: list[Parameter], text) -> list[Curve]:
    by_key = {p.key: p for p in parameters}
    curves = []
    placed: dict[str, str] = {}
    for row in r.rows(data, "curves"):
        k, where = row["key"], f"curve {row['key']}"
        keys = row.get("parameters")
        if not (isinstance(keys, list) and 1 <= len(keys) <= 2
                and all(isinstance(x, str) for x in keys)):
            r.say(f"{where}: parameters must list one or two settings")
            keys = []
        for name in keys:
            if name not in by_key:
                r.say(f"{where}: unknown parameter {name!r}")
            elif name in placed:
                r.say(f"{where}: {name} is already in curve {placed[name]}")
            else:
                placed[name] = k
                if by_key[name].control != "curve":
                    r.say(f"{where}: {name} is in curve {k}, so its control must be curve")
        low, high = row.get("x_low"), row.get("x_high")
        if not (_number(low) and _number(high)):
            r.say(f"{where}: x_low and x_high must be numbers")
            low, high = 0.0, 1.0
        elif not low < high:
            r.say(f"{where}: x_low must be below x_high")
        elif keys and keys[0] in by_key:
            handle = by_key[keys[0]]
            if handle.low < low or handle.high > high:
                r.say(f"{where}: {handle.key} runs outside the curve's x range")
        expr = r.expr(row.get("expr"), {"x", *by_key}, where)
        curves.append(Curve(k, text(f"curve.{k}.name"), text(f"curve.{k}.x"), text(f"curve.{k}.y"),
                            float(low), float(high), expr, tuple(keys)))
    for p in parameters:
        if p.control == "curve" and p.key not in placed:
            r.say(f"parameter {p.key}: its control is curve but no curve names it")
    for curve in curves:
        shown = [by_key[k] for k in curve.parameters if k in by_key]
        for p in shown:
            if not p.panel:
                r.say(f"curve {curve.key}: {p.key} is in curve {curve.key} but is kept off the panel")
        groups = sorted({p.group for p in shown})
        if len(groups) > 1:
            r.say(f"curve {curve.key}: curve {curve.key} mixes the groups {' and '.join(groups)}")
    return curves


CURVE_SAMPLES = 7
CURVE_TOLERANCE = 1e-9


def _check_curve_links(r: _Reader, data: dict, curves: list[Curve], values: list, parameters: list,
                       effects: list, terms: list) -> None:
    targets = {e.key: e.expr for e in effects} | {t.key: t.expr for t in terms}
    inputs = {v.key for v in values} | {e.key for e in effects}
    rows = {row["key"]: row for row in data.get("curves", []) if isinstance(row, dict) and "key" in row}
    for curve in curves:
        row = rows.get(curve.key, {})
        matches, given = row.get("matches"), row.get("input")
        if matches is None and given is None:
            continue
        where = f"curve {curve.key}"
        if matches not in targets:
            r.say(f"{where}: curve {curve.key} matches unknown effect or term {matches!r}")
            continue
        if given not in inputs:
            r.say(f"{where}: unknown input {given!r}")
            continue
        known = {p.key: p.value for p in parameters} | {v.key: v.start for v in values}
        known |= {"t": 0.0, "clock": 0.0}
        known.pop(given, None)
        try:
            needed = names(targets[matches]) - {given}
            if needed - set(known):
                r.say(f"{where}: {matches} needs {sorted(needed - set(known))}, so it cannot be drawn")
                continue
            settings = {p.key: p.value for p in parameters}
            target = compile_function({"_y": targets[matches]}, (given, *known))
            drawn = compile_function({"_y": curve.expr}, ("x", *settings))
            for i in range(CURVE_SAMPLES):
                x = curve.x_low + (curve.x_high - curve.x_low) * i / (CURVE_SAMPLES - 1)
                want = target(x, *known.values())[0]
                got = drawn(x, *settings.values())[0]
                if abs(got - want) > CURVE_TOLERANCE * max(1.0, abs(want)):
                    r.say(f"{where}: curve {curve.key} does not match {matches} at x = {x:g}")
                    break
        except (ExpressionError, ZeroDivisionError, OverflowError, ValueError) as exc:
            r.say(f"{where}: cannot compare with {matches} ({exc})")


SETTINGS = (("settle_speedup", 50), ("settle_days", 10), ("why_threshold", 0.1),
            ("why_unchanged", 0.02))


class _Texts:
    def __init__(self, r: _Reader, path: Path) -> None:
        self.r = r
        self.path = path
        self.found = _texts(path, r)
        self.used: set[str] = set()

    def __call__(self, key: str) -> str:
        self.used.add(key)
        if key not in self.found:
            self.r.say(f"text {key!r} is missing from {self.path.name}")
            return key
        return CITATION.sub("", self.found[key]).strip()

    def __contains__(self, key: str) -> bool:
        return key in self.found

    def check(self, references: dict) -> None:
        for key in sorted(set(self.found) - self.used):
            self.r.say(f"text {key!r} in {self.path.name} is not used by the model")
        for key, value in self.found.items():
            for ref in CITATION.findall(value):
                if ref not in references:
                    self.r.say(f"text {key!r} cites missing reference [{ref}]")


class _Sections:
    def __init__(self, r: _Reader, data: dict, text: _Texts, references: dict,
                 structure_ids: set[int]) -> None:
        self.r = r
        self.data = data
        self.text = text
        self.references = references
        self.structure_ids = structure_ids
        self.value_keys: set[str] = set()
        self.parameter_keys: set[str] = set()
        self.part_keys: set[str] = set()
        self.block_keys: set[str] = set()
        self.start_clock = 0.0

    def version(self) -> int:
        version = self.data.get("version")
        if isinstance(version, int) and not isinstance(version, bool) and version >= 1:
            return version
        self.r.say("version must be a whole number from 1")
        return 1

    def numbers(self) -> dict:
        numbers = {}
        for name, default in SETTINGS:
            value = self.data.get(name, default)
            if not (_number(value) and value > 0):
                self.r.say(f"{name} must be a positive number")
                value = default
            numbers[name] = value
        if not isinstance(numbers["settle_days"], int):
            self.r.say("settle_days must be a whole number")
        return numbers

    def _value(self, row: dict) -> Value:
        r, text = self.r, self.text
        k, where = row["key"], f"value {row['key']}"
        for field in ("unit", "display_unit"):
            if not _text(row.get(field)):
                r.say(f"{where}: needs {field}")
        for field in ("start", "display_scale"):
            if not _number(row.get(field)):
                r.say(f"{where}: {field} must be a number")
        normal = row.get("normal")
        if normal is not None and not (isinstance(normal, list) and len(normal) == 2
                                       and all(map(_number, normal)) and normal[0] < normal[1]):
            r.say(f"{where}: normal must be [low, high]")
            normal = None
        relative = bool(row.get("relative", False))
        if relative:
            text(f"value.{k}.note")
        return Value(k, text(f"value.{k}.name"), str(row.get("unit", "")),
                     float(row.get("start", 1.0)) if _number(row.get("start")) else 1.0,
                     float(row["display_scale"]) if _number(row.get("display_scale")) else 1.0,
                     str(row.get("display_unit", "")), str(row.get("other_unit", "")),
                     float(row.get("other_scale", 0.0)), relative,
                     tuple(float(v) for v in normal) if normal else None,
                     row.get("lane"), bool(row.get("slow", False)),
                     r.refs(row, self.references, where))

    def values(self) -> list[Value]:
        values = [self._value(row) for row in self.r.rows(self.data, "values")]
        self.value_keys = {v.key for v in values}
        return values

    def _parameter(self, row: dict) -> Parameter:
        r, text = self.r, self.text
        k, where = row["key"], f"parameter {row['key']}"
        if not _text(row.get("unit")):
            r.say(f"{where}: needs unit")
        ok = r.ranged(row, "value", where)
        if not isinstance(row.get("panel", True), bool):
            r.say(f"{where}: panel must be true or false")
        text(f"parameter.{k}.meaning")
        group, control, stops = _setting_kind(r, row, where, ok, text)
        if control == "rate":
            for side in ("up", "down"):
                if f"parameter.{k}.{side}" in text:
                    text(f"parameter.{k}.{side}")
        return Parameter(k, text(f"parameter.{k}.name"),
                         float(row["value"]) if ok else 0.0, str(row.get("unit", "")),
                         float(row["low"]) if ok else 0.0, float(row["high"]) if ok else 0.0,
                         r.refs(row, self.references, where), row.get("panel", True) is True,
                         group, control, stops)

    def parameters(self) -> list[Parameter]:
        parameters = [self._parameter(row) for row in self.r.rows(self.data, "parameters")]
        self.parameter_keys = {p.key for p in parameters}
        return parameters

    def _part(self, row: dict) -> Part:
        r = self.r
        k, where = row["key"], f"part {row['key']}"
        structure = row.get("structure")
        if structure is not None and structure not in self.structure_ids:
            r.say(f"{where}: unknown structure {structure}")
        if not (_number(row.get("x")) and _number(row.get("y"))):
            r.say(f"{where}: x and y must be numbers")
        shown = row.get("values", [])
        for v in shown:
            if v not in self.value_keys:
                r.say(f"{where}: unknown value {v!r}")
        return Part(k, self.text(f"part.{k}"), structure, float(row.get("x", 0)),
                    float(row.get("y", 0)), tuple(shown))

    def parts(self) -> list[Part]:
        parts = [self._part(row) for row in self.r.rows(self.data, "parts")]
        self.part_keys = {p.key for p in parts}
        return parts

    def _arrow(self, row: dict, where: str):
        found = row.get("arrow")
        if found is None:
            return None
        if not (isinstance(found, list) and len(found) == 2
                and all(isinstance(p, str) for p in found)):
            self.r.say(f"{where}: arrow must be [from part, to part]")
            return None
        for p in found:
            if p not in self.part_keys:
                self.r.say(f"{where}: arrow names unknown part {p!r}")
        return tuple(found)

    def _via(self, row: dict, where: str) -> tuple:
        found = row.get("via", [])
        if not found:
            return ()
        if not (isinstance(found, list) and all(isinstance(p, str) for p in found)):
            self.r.say(f"{where}: via must be a list of parts")
            return ()
        if row.get("arrow") is None:
            self.r.say(f"{where}: via needs an arrow")
        for p in found:
            if p not in self.part_keys:
                self.r.say(f"{where}: via names unknown part {p!r}")
        return tuple(found)

    def effects_and_terms(self) -> tuple[list[Effect], list[Term]]:
        r = self.r
        effects = []
        allowed = self.value_keys | self.parameter_keys | {"t", "clock"}
        for row in r.rows(self.data, "effects"):
            k, where = row["key"], f"effect {row['key']}"
            if row.get("kind") not in EFFECT_KINDS:
                r.say(f"{where}: kind must be one of {sorted(EFFECT_KINDS)}")
            effects.append(Effect(k, r.expr(row.get("expr"), allowed, where),
                                  str(row.get("kind")), self._arrow(row, where),
                                  self._via(row, where)))
            self.text(f"effect.{k}")
            allowed = allowed | {k}
        terms = []
        for row in r.rows(self.data, "terms"):
            k, where = row["key"], f"term {row['key']}"
            if row.get("value") not in self.value_keys:
                r.say(f"{where}: unknown value {row.get('value')!r}")
            if row.get("sign") not in (1, -1):
                r.say(f"{where}: sign must be 1 or -1")
            if row.get("kind") not in TERM_KINDS:
                r.say(f"{where}: kind must be one of {sorted(TERM_KINDS)}")
            terms.append(Term(k, str(row.get("value")), int(row.get("sign", 1)),
                              r.expr(row.get("expr"), allowed, where), str(row.get("kind")),
                              self._arrow(row, where), self._via(row, where)))
            self.text(f"term.{k}")
        return effects, terms

    def _edits(self, row: dict, where: str, option_keys: set) -> list[Edit]:
        r = self.r
        edits = []
        for n, edit in enumerate(row.get("edits", []), 1):
            ew = f"{where} edit {n}"
            if not isinstance(edit, dict):
                r.say(f"{ew}: must be a table")
                continue
            op, target = edit.get("op"), edit.get("target")
            if op in PARAMETER_OPS:
                if target not in self.parameter_keys:
                    r.say(f"{ew}: {op} needs a parameter, not {target!r}")
            elif op in VALUE_OPS:
                if target not in self.value_keys:
                    r.say(f"{ew}: {op} needs a value, not {target!r}")
            else:
                r.say(f"{ew}: op must be one of {sorted(PARAMETER_OPS | VALUE_OPS)}")
            daily = bool(edit.get("daily", False))
            if daily and op != "dose":
                r.say(f"{ew}: only a dose can be daily")
            edits.append(Edit(str(op), str(target),
                              r.expr(edit.get("expr"), option_keys | self.parameter_keys, ew),
                              daily))
        return edits

    def _length(self, row: dict, where: str) -> float | None:
        length = row.get("length")
        return None if length is None else self.r.time(duration, length, where, 60.0)

    def _options(self, row: dict, k: str, where: str) -> list[Option]:
        r = self.r
        options = []
        for n, opt in enumerate(row.get("options", []), 1):
            ow = f"{where} option {n}"
            if not (isinstance(opt, dict) and isinstance(opt.get("key"), str)
                    and opt["key"].isidentifier()):
                r.say(f"{ow}: needs a key")
                continue
            ok = r.ranged(opt, "default", ow)
            options.append(Option(opt["key"], self.text(f"experiment.{k}.option.{opt['key']}"),
                                  str(opt.get("unit", "")),
                                  float(opt["default"]) if ok else 0.0,
                                  float(opt["low"]) if ok else 0.0,
                                  float(opt["high"]) if ok else 0.0))
        return options

    def _experiment(self, row: dict) -> Experiment:
        r, text = self.r, self.text
        k, where = row["key"], f"experiment {row['key']}"
        if not _text(row.get("group")):
            r.say(f"{where}: needs a group")
        mode = row.get("mode", "from a time")
        if mode not in MODES:
            r.say(f"{where}: mode must be one of {sorted(MODES)}")
        length = self._length(row, where)
        options = self._options(row, k, where)
        edits = self._edits(row, where, {o.key for o in options})
        if not edits:
            r.say(f"{where}: needs at least one edit")
        text(f"experiment.{k}.description")
        return Experiment(k, str(row.get("group", "")), text(f"experiment.{k}"), str(mode),
                          length, tuple(options), tuple(edits), bool(row.get("weeks", False)),
                          _icon(r, row, where))

    def experiments(self) -> list[Experiment]:
        return [self._experiment(row) for row in self.r.rows(self.data, "experiments")]

    def _doses(self, row: dict, where: str) -> list:
        r = self.r
        doses = []
        for n, dose in enumerate(row.get("doses", []), 1):
            dw = f"{where} dose {n}"
            if not isinstance(dose, dict) or dose.get("value") not in self.value_keys:
                r.say(f"{dw}: needs a known value")
                continue
            after = r.time(duration, dose["after"], dw) if "after" in dose else 0.0
            doses.append((after, dose["value"],
                          r.expr(dose.get("amount"), self.parameter_keys, dw)))
        return doses

    def _readings(self, row: dict, where: str) -> list[Reading]:
        r = self.r
        readings = []
        for n, reading in enumerate(row.get("readings", []), 1):
            rw = f"{where} reading {n}"
            if not isinstance(reading, dict) or reading.get("value") not in self.value_keys:
                r.say(f"{rw}: needs a known value")
                continue
            readings.append(Reading(reading["value"], r.time(duration, reading.get("after"), rw)))
        return readings

    def _test(self, row: dict) -> LabTest:
        r, text = self.r, self.text
        k, where = row["key"], f"test {row['key']}"
        doses = self._doses(row, where)
        readings = self._readings(row, where)
        if not readings:
            r.say(f"{where}: needs at least one reading")
        if row.get("rule") not in RULES:
            r.say(f"{where}: rule must be one of {sorted(RULES)}")
        if not _number(row.get("cutoff")):
            r.say(f"{where}: cutoff must be a number")
        for suffix in ("", ".normal", ".abnormal", ".description"):
            text(f"test.{k}{suffix}")
        length = self._length(row, where)
        return LabTest(k, text(f"test.{k}"), tuple(doses), tuple(readings),
                       str(row.get("rule")), float(row.get("cutoff", 0)), _icon(r, row, where),
                       tuple(self._edits(row, where, set())), length)

    def tests(self) -> list[LabTest]:
        return [self._test(row) for row in self.r.rows(self.data, "tests")]

    def _check_blocks(self, row: dict, where: str) -> list[dict]:
        r = self.r
        blocks = []
        for n, block in enumerate(row.get("blocks", []), 1):
            bw = f"{where} block {n}"
            if not isinstance(block, dict) or block.get("experiment") not in self.block_keys:
                r.say(f"{bw}: needs a known experiment or test")
                continue
            out = {"experiment": block["experiment"],
                   "start": r.time(moment, block.get("start", "day 1 00:00"), bw)
                   - self.start_clock}
            if "length" in block:
                out["length"] = r.time(duration, block["length"], bw)
            if "mode" in block:
                if block["mode"] not in MODES:
                    r.say(f"{bw}: unknown mode {block['mode']!r}")
                out["mode"] = block["mode"]
            if "options" in block:
                out["options"] = dict(block["options"])
            blocks.append(out)
        return blocks

    def _assert(self, check, aw: str, blocks: list) -> dict | None:
        r = self.r
        kind = check.get("kind") if isinstance(check, dict) else None
        if kind not in ASSERTS:
            r.say(f"{aw}: kind must be one of {sorted(ASSERTS)}")
            return None
        missing = ASSERTS[kind] - set(check)
        if missing:
            r.say(f"{aw}: needs {sorted(missing)}")
            return None
        out = dict(check)
        for field in ("value", "first", "then"):
            if field in out and out[field] not in self.value_keys:
                r.say(f"{aw}: unknown value {out[field]!r}")
        for field in ("at", "by"):
            if field in out:
                out[field] = r.time(moment, out[field], aw) - self.start_clock
        if "window" in out:
            out["window"] = [r.time(moment, w, aw) - self.start_clock for w in out["window"]]
        if "expect" in out and kind != "test_result":
            out["expect"] = [r.time(clock, w, aw) for w in out["expect"]]
        if kind == "vs_normal" and not ({"rises", "falls"} & set(out)):
            r.say(f"{aw}: needs rises or falls")
        if kind == "test_result":
            if not (isinstance(out["block"], int) and 0 <= out["block"] < len(blocks)):
                r.say(f"{aw}: block must be the index of one of the check's blocks")
            if out["expect"] not in ("normal", "abnormal"):
                r.say(f"{aw}: expect must be normal or abnormal")
        return out

    def _check(self, row: dict) -> Check:
        k, where = row["key"], f"check {row['key']}"
        length = self.r.time(duration, row.get("length"), where, 1440.0)
        blocks = self._check_blocks(row, where)
        asserts = [found for n, check in enumerate(row.get("asserts", []), 1)
                   if (found := self._assert(check, f"{where} assert {n}", blocks)) is not None]
        self.text(f"check.{k}")
        return Check(k, length, tuple(blocks), tuple(asserts))

    def checks(self) -> list[Check]:
        return [self._check(row) for row in self.r.rows(self.data, "checks")]

    def notes(self) -> list[NormalNote]:
        notes = []
        for row in self.r.rows(self.data, "normal"):
            where = f"normal {row['key']}"
            notes.append(NormalNote(row["key"], self.r.time(clock, row.get("from"), where),
                                    self.r.time(clock, row.get("to"), where)))
            self.text(f"normal.{row['key']}")
        return notes


def _model(path: Path, knowledge: Path, structure_ids: set[int], references: dict,
           routes: set[str]) -> tuple[LabModel | None, list[str]]:
    data = read_toml(path)
    r = _Reader(str(path))
    unknown = set(data) - TOP
    if unknown:
        r.say(f"unknown keys {sorted(unknown)}")
    key = data.get("key")
    if not (isinstance(key, str) and key.isidentifier()):
        r.say("needs a key")
        return None, r.problems
    if path.stem != key:
        r.say(f"file name must be {key}.toml")
    text = _Texts(r, knowledge / "en" / f"lab-{key}.toml")
    read = _Sections(r, data, text, references, structure_ids)
    version = read.version()
    route = data.get("route")
    if route is not None and route not in routes:
        r.say(f"unknown route {route!r}")
    start_clock = read.start_clock = r.time(clock, data.get("start_clock", "08:00"),
                                            "start_clock", 480.0)
    max_step = r.time(duration, data.get("max_step", "30 min"), "max_step", 30.0)
    period = r.time(duration, data.get("period", "1 d"), "period", 1440.0)
    scale = data.get("scale", "hours")
    if scale not in SCALES:
        r.say(f"scale must be one of {list(SCALES)}")
        scale = "hours"
    numbers = read.numbers()
    values = read.values()
    parameters = read.parameters()
    curves = _curves(r, data, parameters, text)
    clash = read.value_keys & read.parameter_keys
    if clash:
        r.say(f"names used for both a value and a parameter: {sorted(clash)}")
    parts = read.parts()
    effects, terms = read.effects_and_terms()
    _check_curve_links(r, data, curves, values, parameters, effects, terms)
    names_used = (read.value_keys | read.parameter_keys | {e.key for e in effects}
                  | {t.key for t in terms})
    if len(names_used) != len(values) + len(parameters) + len(effects) + len(terms):
        r.say("keys of values, parameters, effects and terms must all differ")
    experiments = read.experiments()
    tests = read.tests()
    read.block_keys = {e.key for e in experiments} | {t.key for t in tests}
    if len(read.block_keys) != len(experiments) + len(tests):
        r.say("experiments and tests must have different keys")
    checks = read.checks()
    notes = read.notes()
    name = text("name")
    text("scope")
    text.check(references)
    model = LabModel(key, name, version, route, start_clock, float(numbers["settle_speedup"]),
                     int(numbers["settle_days"]), max_step, float(numbers["why_threshold"]),
                     tuple(values), tuple(parameters), tuple(effects), tuple(terms), tuple(parts),
                     tuple(experiments), tuple(tests), tuple(checks), tuple(notes),
                     float(numbers["why_unchanged"]), tuple(curves), period, scale)
    return model, r.problems


def load_models(folder: Path, knowledge: Path, structure_ids: set[int], references: dict,
                routes: set[str]) -> list[LabModel]:
    if not folder.exists():
        return []
    problems: list[str] = []
    models = []
    for path in sorted(folder.glob("*.toml")):
        model, found = _model(path, knowledge, structure_ids, references, routes)
        problems += found
        if model is not None and not found:
            try:
                Simulator(model)
            except (ExpressionError, SyntaxError, ValueError) as exc:
                problems.append(f"{path}: the model cannot be compiled ({exc})")
                continue
            models.append(model)
    if problems:
        raise BuildError(problems)
    return sorted(models, key=lambda model: (model.scale != "hours", model.key))
