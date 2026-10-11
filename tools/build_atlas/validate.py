from __future__ import annotations

from pathlib import Path

import numpy as np

from cns_atlas.knowledge import KnowledgeError, Reference, parse_entry
from cns_atlas.model import KINDS, SIDES

from .hierarchy import PlannedStructure, RawStructure
from .idlock import IdLock
from .recipe import Recipe

MAX_ID = 65535


def check_hierarchy(raws: list[RawStructure]) -> list[str]:
    problems = []
    seen: set[int] = set()
    for r in raws:
        if r.id in seen:
            problems.append(f"id {r.id} is used more than once")
        seen.add(r.id)
        if not 1 <= r.id <= MAX_ID:
            problems.append(f"id {r.id} is outside 1..{MAX_ID}")
        if r.kind not in KINDS:
            problems.append(f"structure {r.id}: unknown kind {r.kind!r}")
        if r.side not in SIDES:
            problems.append(f"structure {r.id}: unknown side {r.side!r}")
    roots = [r.id for r in raws if r.parent is None]
    if len(roots) != 1:
        problems.append(f"expected exactly one root, found {len(roots)}: {roots}")
    by_id = {r.id: r for r in raws}
    for r in raws:
        if r.parent is not None and r.parent not in by_id:
            problems.append(f"structure {r.id}: parent {r.parent} does not exist")
    for r in raws:
        node, steps = r, 0
        while node.parent is not None and node.parent in by_id:
            node, steps = by_id[node.parent], steps + 1
            if steps > len(raws):
                problems.append(f"structure {r.id}: hierarchy has a cycle")
                break
    return problems


def check_ids(raws: list[RawStructure], lock: IdLock) -> list[str]:
    ids = {r.id for r in raws}
    problems = [f"id {i} is retired and cannot be reused" for i in sorted(ids & lock.retired)]
    missing = sorted(lock.published - ids - lock.retired)
    problems += [f"id {i} was published but is missing; add it to 'retired' in ids.lock"
                 for i in missing]
    return problems


def check_sources(raws: list[RawStructure], recipe: Recipe, src: Path) -> list[str]:
    known = {spec.source.id for spec in recipe.sources}
    volumes = {v.name for v in recipe.volumes}
    problems = []
    for spec in recipe.sources:
        name = spec.source.id
        if not spec.source.licence:
            problems.append(f"source {name}: licence is missing")
        if not spec.source.redistribution:
            problems.append(f"source {name}: redistribution is not allowed")
        if spec.licence_file and not (src / spec.licence_file).exists():
            problems.append(f"source {name}: licence file {spec.licence_file} is missing")
        if spec.volume not in volumes:
            problems.append(f"source {name}: unknown volume {spec.volume!r}")
    for v in recipe.volumes:
        if v.grid_source not in known:
            problems.append(f"volume {v.name}: unknown grid source {v.grid_source!r}")
    for r in raws:
        if r.labels and not r.sources:
            problems.append(f"structure {r.id}: has geometry but lists no source")
        for name in sorted({*r.sources, *(ref.source for ref in r.labels)}):
            if name not in known:
                problems.append(f"structure {r.id}: unknown source {name!r}")
    return problems


def check_knowledge(knowledge_dir: Path, references: dict[str, Reference],
                    concepts: dict[int, int | None], keys: set[str]) -> list[str]:
    problems = [f"reference [{r.key}] has none of doi, url, isbn"
                for r in references.values() if not r.has_locator]
    for path in sorted(knowledge_dir.glob("*/*.md")):
        try:
            entry = parse_entry(path.read_text(encoding="utf-8"), str(path))
        except KnowledgeError as exc:
            problems.append(str(exc))
            continue
        target = entry.target
        if isinstance(target, int):
            if target not in concepts:
                problems.append(f"{path}: unknown id {target}")
            elif concepts[target] is not None:
                problems.append(f"{path}: describe concept {concepts[target]} instead of {target}")
        elif target not in keys:
            problems.append(f"{path}: unknown key {target!r}")
        if path.name != f"{target}.md":
            problems.append(f"{path}: file name must be {target}.md")
        problems += [f"{path}: cites missing reference [{key}]"
                     for key in entry.citations if key not in references]
    return problems


def check_voxels(planned: list[PlannedStructure], volumes: list[np.ndarray]) -> list[str]:
    present: set[int] = set()
    for data in volumes:
        present.update(np.unique(data).tolist())
    return [f"structure {p.structure.id} ({p.structure.name}) has no voxels"
            for p in planned if p.labels and p.structure.id not in present]


def check_templates(recipe: Recipe, src: Path) -> list[str]:
    volumes = {v.name for v in recipe.volumes}
    problems = []
    for spec in recipe.templates:
        name = spec.source.id
        if not spec.source.licence:
            problems.append(f"template {name}: licence is missing")
        if not spec.source.redistribution:
            problems.append(f"template {name}: redistribution is not allowed")
        if spec.licence_file and not (src / spec.licence_file).exists():
            problems.append(f"template {name}: licence file {spec.licence_file} is missing")
        if spec.volume not in volumes:
            problems.append(f"template {name}: unknown volume {spec.volume!r}")
    targets = [spec.volume for spec in recipe.templates]
    problems += [f"volume {v}: more than one template"
                 for v in sorted({t for t in targets if targets.count(t) > 1})]
    return problems
