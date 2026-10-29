from __future__ import annotations

import keyword
import tomllib
from pathlib import Path

from cns_atlas.knowledge import CITATION
from cns_atlas.models import (Check, Edit, Effect, Experiment, LabModel, LabTest, NormalNote, Option,
                              Parameter, Part, Reading, Term, Value)
from cns_lab.expressions import CONSTANTS, FUNCTIONS, ExpressionError, names
from cns_lab.engine import Simulator
from cns_lab.times import TimeError, clock, duration, moment

from .recipe import BuildError, read_toml

TOP = {"key", "version", "route", "start_clock", "settle_speedup", "settle_days", "max_step",
       "why_threshold", "values", "parameters", "effects", "terms", "parts", "experiments",
       "tests", "checks", "normal"}
FIELDS = {
    "values": {"key", "unit", "start", "display_scale", "display_unit", "other_unit",
               "other_scale", "relative", "normal", "lane", "slow", "refs"},
    "parameters": {"key", "value", "unit", "low", "high", "refs"},
    "effects": {"key", "expr", "kind", "arrow"},
    "terms": {"key", "value", "sign", "expr", "kind", "arrow"},
    "parts": {"key", "structure", "x", "y", "values"},
    "experiments": {"key", "group", "mode", "length", "options", "edits", "weeks"},
    "tests": {"key", "doses", "readings", "rule", "cutoff"},
    "checks": {"key", "length", "blocks", "asserts"},
    "normal": {"key", "from", "to"},
}
EFFECT_KINDS = {"drives", "holds back"}
TERM_KINDS = {"drives", "clears", "grows", "shrinks", "absorbs"}
MODES = {"from a time", "present"}
PARAMETER_OPS = {"set", "add", "scale"}
VALUE_OPS = {"clamp", "dose"}
RULES = {"below", "at least", "suppressed by"}
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
    texts_path = knowledge / "en" / f"lab-{key}.toml"
    texts = _texts(texts_path, r)
    used: set[str] = set()

    def text(text_key: str) -> str:
        used.add(text_key)
        if text_key not in texts:
            r.say(f"text {text_key!r} is missing from {texts_path.name}")
            return text_key
        return CITATION.sub("", texts[text_key]).strip()

    version = data.get("version")
    if not (isinstance(version, int) and not isinstance(version, bool) and version >= 1):
        r.say("version must be a whole number from 1")
        version = 1
    route = data.get("route")
    if route is not None and route not in routes:
        r.say(f"unknown route {route!r}")
    start_clock = r.time(clock, data.get("start_clock", "08:00"), "start_clock", 480.0)
    max_step = r.time(duration, data.get("max_step", "30 min"), "max_step", 30.0)
    numbers = {}
    for name, default in (("settle_speedup", 50), ("settle_days", 10), ("why_threshold", 0.1)):
        value = data.get(name, default)
        if not (_number(value) and value > 0):
            r.say(f"{name} must be a positive number")
            value = default
        numbers[name] = value
    if not isinstance(numbers["settle_days"], int):
        r.say("settle_days must be a whole number")

    values = []
    for row in r.rows(data, "values"):
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
        values.append(Value(k, text(f"value.{k}.name"), str(row.get("unit", "")),
                            float(row.get("start", 1.0)) if _number(row.get("start")) else 1.0,
                            float(row["display_scale"]) if _number(row.get("display_scale"))
                            else 1.0,
                            str(row.get("display_unit", "")), str(row.get("other_unit", "")),
                            float(row.get("other_scale", 0.0)), relative,
                            tuple(float(v) for v in normal) if normal else None,
                            row.get("lane"), bool(row.get("slow", False)),
                            r.refs(row, references, where)))
    value_keys = {v.key for v in values}

    parameters = []
    for row in r.rows(data, "parameters"):
        k, where = row["key"], f"parameter {row['key']}"
        if not _text(row.get("unit")):
            r.say(f"{where}: needs unit")
        ok = r.ranged(row, "value", where)
        text(f"parameter.{k}.meaning")
        parameters.append(Parameter(k, text(f"parameter.{k}.name"),
                                    float(row["value"]) if ok else 0.0, str(row.get("unit", "")),
                                    float(row["low"]) if ok else 0.0,
                                    float(row["high"]) if ok else 0.0,
                                    r.refs(row, references, where)))
    parameter_keys = {p.key for p in parameters}
    clash = value_keys & parameter_keys
    if clash:
        r.say(f"names used for both a value and a parameter: {sorted(clash)}")

    parts = []
    for row in r.rows(data, "parts"):
        k, where = row["key"], f"part {row['key']}"
        structure = row.get("structure")
        if structure is not None and structure not in structure_ids:
            r.say(f"{where}: unknown structure {structure}")
        if not (_number(row.get("x")) and _number(row.get("y"))):
            r.say(f"{where}: x and y must be numbers")
        shown = row.get("values", [])
        for v in shown:
            if v not in value_keys:
                r.say(f"{where}: unknown value {v!r}")
        parts.append(Part(k, text(f"part.{k}"), structure, float(row.get("x", 0)),
                          float(row.get("y", 0)), tuple(shown)))
    part_keys = {p.key for p in parts}

    def arrow(row: dict, where: str):
        found = row.get("arrow")
        if found is None:
            return None
        if not (isinstance(found, list) and len(found) == 2
                and all(isinstance(p, str) for p in found)):
            r.say(f"{where}: arrow must be [from part, to part]")
            return None
        for p in found:
            if p not in part_keys:
                r.say(f"{where}: arrow names unknown part {p!r}")
        return tuple(found)

    effects = []
    allowed = value_keys | parameter_keys | {"t", "clock"}
    for row in r.rows(data, "effects"):
        k, where = row["key"], f"effect {row['key']}"
        if row.get("kind") not in EFFECT_KINDS:
            r.say(f"{where}: kind must be one of {sorted(EFFECT_KINDS)}")
        effects.append(Effect(k, r.expr(row.get("expr"), allowed, where), str(row.get("kind")),
                              arrow(row, where)))
        text(f"effect.{k}")
        allowed = allowed | {k}

    terms = []
    for row in r.rows(data, "terms"):
        k, where = row["key"], f"term {row['key']}"
        if row.get("value") not in value_keys:
            r.say(f"{where}: unknown value {row.get('value')!r}")
        if row.get("sign") not in (1, -1):
            r.say(f"{where}: sign must be 1 or -1")
        if row.get("kind") not in TERM_KINDS:
            r.say(f"{where}: kind must be one of {sorted(TERM_KINDS)}")
        terms.append(Term(k, str(row.get("value")), int(row.get("sign", 1)),
                          r.expr(row.get("expr"), allowed, where), str(row.get("kind")),
                          arrow(row, where)))
        text(f"term.{k}")
    names_used = value_keys | parameter_keys | {e.key for e in effects} | {t.key for t in terms}
    if len(names_used) != len(values) + len(parameters) + len(effects) + len(terms):
        r.say("keys of values, parameters, effects and terms must all differ")

    experiments = []
    for row in r.rows(data, "experiments"):
        k, where = row["key"], f"experiment {row['key']}"
        if not _text(row.get("group")):
            r.say(f"{where}: needs a group")
        mode = row.get("mode", "from a time")
        if mode not in MODES:
            r.say(f"{where}: mode must be one of {sorted(MODES)}")
        length = row.get("length")
        length = None if length is None else r.time(duration, length, where, 60.0)
        options = []
        for n, opt in enumerate(row.get("options", []), 1):
            ow = f"{where} option {n}"
            if not (isinstance(opt, dict) and isinstance(opt.get("key"), str)
                    and opt["key"].isidentifier()):
                r.say(f"{ow}: needs a key")
                continue
            ok = r.ranged(opt, "default", ow)
            options.append(Option(opt["key"], text(f"experiment.{k}.option.{opt['key']}"),
                                  str(opt.get("unit", "")),
                                  float(opt["default"]) if ok else 0.0,
                                  float(opt["low"]) if ok else 0.0,
                                  float(opt["high"]) if ok else 0.0))
        option_keys = {o.key for o in options}
        edits = []
        for n, edit in enumerate(row.get("edits", []), 1):
            ew = f"{where} edit {n}"
            if not isinstance(edit, dict):
                r.say(f"{ew}: must be a table")
                continue
            op, target = edit.get("op"), edit.get("target")
            if op in PARAMETER_OPS:
                if target not in parameter_keys:
                    r.say(f"{ew}: {op} needs a parameter, not {target!r}")
            elif op in VALUE_OPS:
                if target not in value_keys:
                    r.say(f"{ew}: {op} needs a value, not {target!r}")
            else:
                r.say(f"{ew}: op must be one of {sorted(PARAMETER_OPS | VALUE_OPS)}")
            daily = bool(edit.get("daily", False))
            if daily and op != "dose":
                r.say(f"{ew}: only a dose can be daily")
            edits.append(Edit(str(op), str(target),
                              r.expr(edit.get("expr"), option_keys | parameter_keys, ew), daily))
        if not edits:
            r.say(f"{where}: needs at least one edit")
        text(f"experiment.{k}.description")
        experiments.append(Experiment(k, str(row.get("group", "")), text(f"experiment.{k}"),
                                      str(mode), length, tuple(options), tuple(edits),
                                      bool(row.get("weeks", False))))

    tests = []
    for row in r.rows(data, "tests"):
        k, where = row["key"], f"test {row['key']}"
        doses = []
        for n, dose in enumerate(row.get("doses", []), 1):
            dw = f"{where} dose {n}"
            if not isinstance(dose, dict) or dose.get("value") not in value_keys:
                r.say(f"{dw}: needs a known value")
                continue
            after = r.time(duration, dose["after"], dw) if "after" in dose else 0.0
            doses.append((after, dose["value"], r.expr(dose.get("amount"), parameter_keys, dw)))
        readings = []
        for n, reading in enumerate(row.get("readings", []), 1):
            rw = f"{where} reading {n}"
            if not isinstance(reading, dict) or reading.get("value") not in value_keys:
                r.say(f"{rw}: needs a known value")
                continue
            readings.append(Reading(reading["value"], r.time(duration, reading.get("after"), rw)))
        if not readings:
            r.say(f"{where}: needs at least one reading")
        if row.get("rule") not in RULES:
            r.say(f"{where}: rule must be one of {sorted(RULES)}")
        if not _number(row.get("cutoff")):
            r.say(f"{where}: cutoff must be a number")
        for suffix in ("", ".normal", ".abnormal", ".description"):
            text(f"test.{k}{suffix}")
        tests.append(LabTest(k, text(f"test.{k}"), tuple(doses), tuple(readings),
                             str(row.get("rule")), float(row.get("cutoff", 0))))
    block_keys = {e.key for e in experiments} | {t.key for t in tests}
    if len(block_keys) != len(experiments) + len(tests):
        r.say("experiments and tests must have different keys")

    checks = []
    for row in r.rows(data, "checks"):
        k, where = row["key"], f"check {row['key']}"
        length = r.time(duration, row.get("length"), where, 1440.0)
        blocks = []
        for n, block in enumerate(row.get("blocks", []), 1):
            bw = f"{where} block {n}"
            if not isinstance(block, dict) or block.get("experiment") not in block_keys:
                r.say(f"{bw}: needs a known experiment or test")
                continue
            out = {"experiment": block["experiment"],
                   "start": r.time(moment, block.get("start", "day 1 00:00"), bw)
                   - start_clock}
            if "length" in block:
                out["length"] = r.time(duration, block["length"], bw)
            if "mode" in block:
                if block["mode"] not in MODES:
                    r.say(f"{bw}: unknown mode {block['mode']!r}")
                out["mode"] = block["mode"]
            if "options" in block:
                out["options"] = dict(block["options"])
            blocks.append(out)
        asserts = []
        for n, check in enumerate(row.get("asserts", []), 1):
            aw = f"{where} assert {n}"
            kind = check.get("kind") if isinstance(check, dict) else None
            if kind not in ASSERTS:
                r.say(f"{aw}: kind must be one of {sorted(ASSERTS)}")
                continue
            missing = ASSERTS[kind] - set(check)
            if missing:
                r.say(f"{aw}: needs {sorted(missing)}")
                continue
            out = dict(check)
            for field in ("value", "first", "then"):
                if field in out and out[field] not in value_keys:
                    r.say(f"{aw}: unknown value {out[field]!r}")
            for field in ("at", "by"):
                if field in out:
                    out[field] = r.time(moment, out[field], aw) - start_clock
            if "window" in out:
                out["window"] = [r.time(moment, w, aw) - start_clock for w in out["window"]]
            if "expect" in out and kind != "test_result":
                out["expect"] = [r.time(clock, w, aw) for w in out["expect"]]
            if kind == "vs_normal" and not ({"rises", "falls"} & set(out)):
                r.say(f"{aw}: needs rises or falls")
            if kind == "test_result":
                if not (isinstance(out["block"], int) and 0 <= out["block"] < len(blocks)):
                    r.say(f"{aw}: block must be the index of one of the check's blocks")
                if out["expect"] not in ("normal", "abnormal"):
                    r.say(f"{aw}: expect must be normal or abnormal")
            asserts.append(out)
        text(f"check.{k}")
        checks.append(Check(k, length, tuple(blocks), tuple(asserts)))

    notes = []
    for row in r.rows(data, "normal"):
        where = f"normal {row['key']}"
        notes.append(NormalNote(row["key"], r.time(clock, row.get("from"), where),
                                r.time(clock, row.get("to"), where)))
        text(f"normal.{row['key']}")

    name = text("name")
    text("scope")
    for text_key in sorted(set(texts) - used):
        r.say(f"text {text_key!r} in {texts_path.name} is not used by the model")
    for text_key, value in texts.items():
        for ref in CITATION.findall(value):
            if ref not in references:
                r.say(f"text {text_key!r} cites missing reference [{ref}]")
    model = LabModel(key, name, version, route, start_clock, float(numbers["settle_speedup"]),
                     int(numbers["settle_days"]), max_step, float(numbers["why_threshold"]),
                     tuple(values), tuple(parameters), tuple(effects), tuple(terms), tuple(parts),
                     tuple(experiments), tuple(tests), tuple(checks), tuple(notes))
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
    return models
