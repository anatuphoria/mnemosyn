from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from cns_atlas.knowledge import KnowledgeError, parse_entry
from cns_atlas.model import (PATHWAY_SIDES, STEP_SIDES, TEXT_STYLES, Pathway, Relay, Station,
                             Structure, step_from_json)
from cns_atlas.pathways import lit, lit_both, side_words, step_problems, unknown_side_words

from .recipe import BuildError, read_toml

KEY = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
FIELDS = ("key", "name", "start", "steps", "group", "sides", "texts")
KINDS = ("structures", "cross", "relay")


def _step_problems(step, where: str) -> list[str]:
    if not isinstance(step, dict):
        return [f"{where}: must be a table"]
    kinds = [kind for kind in KINDS if kind in step]
    if len(kinds) != 1:
        return [f"{where}: needs exactly one of structures, cross or relay"]
    kind = kinds[0]
    if kind == "cross":
        allowed = {kind}
    elif kind == "structures":
        allowed = {kind, "side", "crossing"}
    else:
        allowed = {kind, "side"}
    problems = []
    unknown = set(step) - allowed
    if unknown:
        problems.append(f"{where}: unknown keys {sorted(unknown)}")
    if kind == "structures" and "crossing" in step and not isinstance(step["crossing"], bool):
        problems.append(f"{where}: crossing must be true or false")
    side = step.get("side", "same")
    if side not in STEP_SIDES:
        problems.append(f"{where}: unknown side {side!r}")
    value = step[kind]
    if kind == "structures":
        if not (isinstance(value, list) and value
                and all(isinstance(i, int) and not isinstance(i, bool) for i in value)):
            problems.append(f"{where}: structures must be a non-empty list of ids")
    elif not (isinstance(value, str) and value.strip()):
        problems.append(f"{where}: {kind} needs a name")
    return problems


def load_pathways(path: Path) -> list[Pathway]:
    if not path.exists():
        return []
    problems: list[str] = []
    pathways: list[Pathway] = []
    seen: set[str] = set()
    data = read_toml(path)
    unknown_top = set(data) - {"pathways"}
    if unknown_top:
        raise BuildError([f"{path}: unknown top-level keys {sorted(unknown_top)}"])
    for n, record in enumerate(data.get("pathways", []), 1):
        if not isinstance(record, dict):
            problems.append(f"pathway {n}: must be a table")
            continue
        key = record.get("key")
        label = f"pathway {key if isinstance(key, str) else n}"
        found = []
        unknown = set(record) - set(FIELDS)
        if unknown:
            found.append(f"{label}: unknown keys {sorted(unknown)}")
        if not (isinstance(key, str) and KEY.fullmatch(key)):
            found.append(f"{label}: key must be lowercase letters, digits and hyphens")
        elif key in seen:
            found.append(f"{label}: duplicate key")
        else:
            seen.add(key)
        for field in ("name", "start", "group"):
            if not (isinstance(record.get(field), str) and record[field].strip()):
                found.append(f"{label}: needs a {field}")
        sides, texts = record.get("sides", "one"), record.get("texts", "lesion")
        if sides not in PATHWAY_SIDES:
            found.append(f"{label}: unknown sides {sides!r}")
        if texts not in TEXT_STYLES:
            found.append(f"{label}: unknown texts {texts!r}")
        steps = record.get("steps")
        if not (isinstance(steps, list) and steps):
            found.append(f"{label}: needs at least one step")
        else:
            for i, step in enumerate(steps, 1):
                found += _step_problems(step, f"{label} step {i}")
                if sides == "both" and isinstance(step, dict) and "side" in step:
                    found.append(f"{label} step {i}: a both-sides route takes no side")
        problems += found
        if not found:
            pathways.append(Pathway(key, record["name"], record["start"],
                                    tuple(step_from_json(step) for step in steps),
                                    record["group"], sides, texts))
    if problems:
        raise BuildError(problems)
    return pathways


def check_pathways(pathways: list[Pathway], structures: list[Structure], shaped: set[int],
                   left_out: frozenset[int] | set[int] = frozenset()) -> list[str]:
    known = {s.id for s in structures}
    has_shape = shaped.__contains__
    problems = []
    for pathway in pathways:
        for i, step in enumerate(pathway.steps, 1):
            if not isinstance(step, Station):
                continue
            where = f"pathway {pathway.key} step {i}"
            for structure_id in step.structures:
                if structure_id in left_out:
                    continue
                if structure_id not in known:
                    problems.append(f"{where}: unknown structure id {structure_id}")
                    continue
                single = Station((structure_id,), step.side)
                if pathway.sides == "both":
                    if not lit_both(structures, has_shape, single):
                        problems.append(f"{where}: {structure_id} has no shape to light")
                    continue
                problems += [f"{where}: {structure_id} has no shape to light for a {side} start"
                             for side in ("left", "right")
                             if not lit(structures, has_shape, single, side)]
    return problems


def check_pathway_texts(knowledge_dir: Path, pathways: list[Pathway]) -> list[str]:
    problems = []
    for pathway in pathways:
        name = f"pathway-{pathway.key}.md"
        if not (knowledge_dir / "en" / name).exists():
            problems.append(f"pathway {pathway.key}: description "
                            f"{knowledge_dir / 'en' / name} is missing")
        count = len(pathway.steps)
        expected = ["Overview", *(f"Step {n}" for n in range(1, count + 1))]
        for path in sorted(knowledge_dir.glob(f"*/{name}")):
            try:
                entry = parse_entry(path.read_text(encoding="utf-8"), str(path))
            except KnowledgeError:
                continue
            if list(entry.sections) != expected:
                problems.append(f"{path}: sections must be Overview, then Step 1 to Step {count}")
                continue
            for n in range(1, count + 1):
                problems += [f"{path}: Step {n}: {problem}"
                             for problem in step_problems(entry.sections[f"Step {n}"],
                                                           pathway.texts)]
            for section, body in entry.sections.items():
                if pathway.sides == "both":
                    problems += [f"{path}: {section}: side word {{{word}}} in a both-sides route"
                                 for word in side_words(body)]
                else:
                    problems += [f"{path}: {section}: unknown side word {{{word}}}"
                                 for word in unknown_side_words(body)]
    return problems


def for_package(pathways: list[Pathway], names: dict[int, str],
                left_out: set[int]) -> list[Pathway]:
    out = []
    for pathway in pathways:
        steps = []
        for step in pathway.steps:
            if isinstance(step, Station) and left_out & set(step.structures):
                kept = tuple(i for i in step.structures if i not in left_out)
                step = (Station(kept, step.side) if kept else
                        Relay(" and ".join(names[i] for i in step.structures), step.side))
            steps.append(step)
        out.append(replace(pathway, steps=tuple(steps)))
    return out
