from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from cns_atlas.model import Structure

from .recipe import BuildError, read_toml

DEFAULT_COLOR = (170, 170, 180)
SHADE_SPAN = 0.15
ALTERNATE = 0.18
PALETTES = ("alternate", "distinct")
SIDED = ("left", "right")
GROUP_KEYS = {"id", "parent", "acronym", "name", "color", "synonyms", "xrefs", "palette"}
CONCEPT_KEYS = GROUP_KEYS - {"palette"} | {"kind", "left", "right", "midline", "source"}


@dataclass(frozen=True)
class LabelRef:
    source: str
    value: int | str


def _ref(value) -> int | str:
    return value if isinstance(value, str) else int(value)


@dataclass(frozen=True)
class RawStructure:
    id: int
    parent: int | None
    acronym: str
    name: str
    kind: str
    side: str
    concept: int | None
    color: tuple[int, int, int] | None
    synonyms: tuple[str, ...]
    xrefs: dict
    sources: tuple[str, ...]
    labels: tuple[LabelRef, ...]
    palette: str | None = None


@dataclass(frozen=True)
class PlannedStructure:
    structure: Structure
    labels: tuple[LabelRef, ...]


def _record_problems(record: dict, allowed: set[str], label: str) -> list[str]:
    problems = []
    unknown = set(record) - allowed
    if unknown:
        problems.append(f"{label} {record.get('id')}: unknown keys {sorted(unknown)}")
    missing = {"id", "acronym", "name"} - set(record)
    if missing:
        problems.append(f"{label} {record.get('id')}: missing {sorted(missing)}")
    if "midline" in record and ("left" in record or "right" in record):
        problems.append(f"{label} {record.get('id')}: has both 'midline' and 'left'/'right'")
    return problems


def _raw(record: dict, **fields) -> RawStructure:
    color = record.get("color")
    parent = record.get("parent")
    return RawStructure(id=int(record["id"]), parent=int(parent) if parent is not None else None,
                        acronym=str(record["acronym"]), name=str(record["name"]),
                        color=tuple(int(c) for c in color) if color else None,
                        synonyms=tuple(record.get("synonyms", ())),
                        xrefs=dict(record.get("xrefs", {})), **fields)


def _expand_concept(record: dict, source: str) -> list[RawStructure]:
    kind = record.get("kind", "region")
    if "midline" in record:
        return [_raw(record, kind=kind, side="midline", concept=None, sources=(source,),
                     labels=(LabelRef(source, _ref(record["midline"])),))]
    concept = _raw(record, kind=kind, side="none", concept=None, sources=(), labels=())
    out = [concept]
    for offset, side in ((1, "left"), (2, "right")):
        if side in record:
            out.append(RawStructure(
                id=concept.id + offset, parent=concept.id,
                acronym=f"{concept.acronym}-{side[0].upper()}",
                name=f"{concept.name} ({side})", kind=kind, side=side, concept=concept.id,
                color=concept.color, synonyms=(f"{side} {concept.name}",), xrefs={},
                sources=(source,), labels=(LabelRef(source, _ref(record[side])),)))
    return out


def load_structures(path: Path) -> list[RawStructure]:
    data = read_toml(path)
    default_source = data.get("default_source", "")
    raws: list[RawStructure] = []
    problems: list[str] = []
    for record in data.get("groups", []):
        found = _record_problems(record, GROUP_KEYS, "group")
        problems += found
        if not found:
            raws.append(_raw(record, kind="group", side="none", concept=None, sources=(),
                             labels=(), palette=record.get("palette")))
    for record in data.get("concepts", []):
        found = _record_problems(record, CONCEPT_KEYS, "concept")
        problems += found
        if not found:
            raws.extend(_expand_concept(record, record.get("source", default_source)))
    if problems:
        raise BuildError(problems)
    return raws


def without_sources(raws: list[RawStructure], skipped: set[str]) -> list[RawStructure]:
    gone = {r.id for r in raws if r.labels and all(ref.source in skipped for ref in r.labels)}
    children: dict[int | None, list[int]] = {}
    for r in raws:
        children.setdefault(r.parent, []).append(r.id)
    changed = True
    while changed:
        before = len(gone)
        gone |= {r.id for r in raws if r.parent in gone}
        gone |= {r.id for r in raws if r.kind != "group" and not r.labels and children.get(r.id)
                 and all(child in gone for child in children[r.id])}
        changed = len(gone) != before
    return [r for r in raws if r.id not in gone]


def resolve_members(raws: list[RawStructure], values: dict[str, dict[str, int]]
                    ) -> list[RawStructure]:
    def resolved(ref: LabelRef) -> LabelRef:
        table = values.get(ref.source, {})
        return LabelRef(ref.source, table[ref.value]) if ref.value in table else ref
    return [replace(r, labels=tuple(resolved(ref) for ref in r.labels)) for r in raws]


def shade(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    if factor >= 0:
        return tuple(round(c + (255 - c) * factor) for c in rgb)
    return tuple(round(c * (1 + factor)) for c in rgb)


def sibling_factors(ids: list[int]) -> dict[int, float]:
    ordered = sorted(ids)
    if len(ordered) == 1:
        return {ordered[0]: 0.0}
    step = 2 * SHADE_SPAN / (len(ordered) - 1)
    return {sid: -SHADE_SPAN + step * k for k, sid in enumerate(ordered)}


def build_tree(raws: list[RawStructure]) -> list[PlannedStructure]:
    by_id = {r.id: r for r in raws}
    children: dict[int | None, list[int]] = {}
    for r in raws:
        children.setdefault(r.parent, []).append(r.id)
    out: list[PlannedStructure] = []
    stack = [(children[None][0], (), DEFAULT_COLOR)]
    while stack:
        structure_id, path, inherited = stack.pop()
        r = by_id[structure_id]
        path = (*path, structure_id)
        color = r.color or inherited
        structure = Structure(id=r.id, acronym=r.acronym, name=r.name, structure_id_path=path,
                              rgb_triplet=color, kind=r.kind, side=r.side, concept=r.concept,
                              synonyms=r.synonyms, xrefs=r.xrefs, sources=r.sources)
        out.append(PlannedStructure(structure, r.labels))
        kids = children.get(structure_id, [])
        shaded = [c for c in kids if by_id[c].color is None and by_id[c].side not in SIDED
                  and by_id[c].kind != "group"]
        if r.palette == "alternate":
            factors = {c: ALTERNATE if k % 2 == 0 else -ALTERNATE
                       for k, c in enumerate(sorted(shaded))}
        else:
            factors = sibling_factors(shaded) if shaded else {}
        for child in sorted(kids, reverse=True):
            tone = shade(color, factors[child]) if child in factors else color
            stack.append((child, path, tone))
    return out


def with_xrefs(planned: list[PlannedStructure],
               names: dict[str, dict[int, str]]) -> list[PlannedStructure]:
    out = []
    for p in planned:
        xrefs = dict(p.structure.xrefs)
        for ref in p.labels:
            name = (ref.value if isinstance(ref.value, str)
                    else names.get(ref.source, {}).get(ref.value))
            if name:
                xrefs[ref.source] = name
        out.append(replace(p, structure=replace(p.structure, xrefs=xrefs)))
    return out
