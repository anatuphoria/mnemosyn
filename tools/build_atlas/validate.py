from __future__ import annotations

from pathlib import Path

import numpy as np

from cns_atlas.knowledge import KnowledgeError, Reference, parse_entry
from cns_atlas.model import KINDS, SIDES

from .hierarchy import PlannedStructure, RawStructure
from .idlock import IdLock
from .recipe import MESH_GRIDS, Recipe

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
    labels = {spec.source.id: spec for spec in recipe.sources}
    tracts = {spec.source.id: spec for spec in recipe.tracts}
    known = set(labels) | set(tracts)
    volumes = {v.name for v in recipe.volumes}
    groups = {r.id for r in raws if r.kind == "group"}
    problems = []
    for spec in recipe.sources:
        name = spec.source.id
        if not spec.source.licence:
            problems.append(f"source {name}: licence is missing")
        if spec.local_only and spec.source.redistribution:
            problems.append(f"source {name}: a shareable source must not be local-only")
        elif not spec.source.redistribution and not spec.local_only:
            problems.append(f"source {name}: redistribution is not allowed")
        if spec.licence_file and not (src / spec.licence_file).exists():
            problems.append(f"source {name}: licence file {spec.licence_file} is missing")
        if spec.volume not in volumes:
            problems.append(f"source {name}: unknown volume {spec.volume!r}")
        if spec.mesh_grid not in MESH_GRIDS:
            problems.append(f"source {name}: mesh_grid must be one of {MESH_GRIDS}")
        if spec.members and (spec.member or spec.label_names):
            problems.append(f"source {name}: give member or members, not both")
        if spec.manual and not spec.source.url:
            problems.append(f"source {name}: a manual source needs a url to download it from")
        if spec.separate and not spec.members:
            problems.append(f"source {name}: separate needs members")
        elif spec.separate and spec.mesh_grid != "native":
            problems.append(f"source {name}: separate needs mesh_grid = \"native\"")
        if spec.parts and spec.threshold is None:
            problems.append(f"source {name}: parts need a threshold")
        if spec.trim_outside is not None and spec.trim_outside not in groups:
            problems.append(f"source {name}: trim_outside {spec.trim_outside} is not a group")
        if spec.threshold is not None and not (spec.mask or spec.members or spec.parts):
            problems.append(f"source {name}: threshold needs mask = true or members")
        problems += [f"source {name}: drop value {value!r} is not a label number"
                     for value in spec.drop
                     if not isinstance(value, int) or isinstance(value, bool)]
    for spec in recipe.tracts:
        name = spec.source.id
        if not spec.source.licence:
            problems.append(f"tracts {name}: licence is missing")
        if not spec.source.redistribution:
            problems.append(f"tracts {name}: redistribution is not allowed")
        if spec.licence_file and not (src / spec.licence_file).exists():
            problems.append(f"tracts {name}: licence file {spec.licence_file} is missing")
        if spec.labels not in volumes:
            problems.append(f"tracts {name}: unknown volume {spec.labels!r}")
        if "{name}" not in spec.download:
            problems.append(f"tracts {name}: download must contain {{name}}")
        if not spec.files:
            problems.append(f"tracts {name}: no files listed")
        problems += [f"tracts {name}: dropped file {dropped!r} is not listed"
                     for dropped in spec.drop if dropped not in spec.names]
    if len({spec.labels for spec in recipe.tracts}) > 1:
        problems.append("tracts: all tract sources must use one label volume")
    for v in recipe.volumes:
        if v.grid_source not in labels:
            problems.append(f"volume {v.name}: unknown grid source {v.grid_source!r}")
        elif labels[v.grid_source].local_only and any(
                s.volume == v.name and not s.local_only
                for s in (*recipe.sources, *recipe.templates)):
            problems.append(f"volume {v.name}: grid source {v.grid_source!r} is local-only, so "
                            f"every source and template of the volume must be local-only")
    mapped: dict[str, set[str]] = {name: set() for name in tracts}
    numbers: dict[str, set[int]] = {name: set() for name in labels}
    used: dict[str, set[str]] = {name: set() for name in labels}
    for r in raws:
        if r.labels and not r.sources:
            problems.append(f"structure {r.id}: has geometry but lists no source")
        for name in sorted({*r.sources, *(ref.source for ref in r.labels)}):
            if name not in known:
                problems.append(f"structure {r.id}: unknown source {name!r}")
        for ref in r.labels:
            member_spec = labels.get(ref.source)
            if member_spec is not None and member_spec.members:
                if not isinstance(ref.value, str):
                    problems.append(f"structure {r.id}: source {ref.source} needs a member "
                                    f"name, not {ref.value!r}")
                elif ref.value not in member_spec.member_values:
                    problems.append(f"structure {r.id}: source {ref.source} has no member "
                                    f"{ref.value!r}")
                else:
                    used[ref.source].add(ref.value)
                continue
            if isinstance(ref.value, str):
                spec = tracts.get(ref.source)
                if spec is None:
                    problems.append(f"structure {r.id}: mask {ref.value!r} needs a tracts "
                                    f"source, not {ref.source!r}")
                elif ref.value not in spec.names:
                    problems.append(f"structure {r.id}: tracts {ref.source} has no file "
                                    f"{ref.value!r}")
                else:
                    mapped[ref.source].add(ref.value)
            elif ref.source in tracts:
                problems.append(f"structure {r.id}: tracts {ref.source} needs a file name, "
                                f"not {ref.value!r}")
            elif ref.source in labels:
                numbers[ref.source].add(ref.value)
    for name, spec in tracts.items():
        problems += [f"tracts {name}: file {file!r} has no structure and is not dropped"
                     for file in spec.names if file not in mapped[name] and file not in spec.drop]
        problems += [f"tracts {name}: file {file!r} is both dropped and mapped"
                     for file in spec.drop if file in mapped[name]]
    for name, spec in labels.items():
        problems += [f"source {name}: label {value} is both dropped and mapped"
                     for value in spec.drop if value in numbers[name]]
    for name, spec in labels.items():
        problems += [f"source {name}: member {member!r} has no structure"
                     for member in spec.member_values if member not in used[name]]
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


def check_voxels(planned: list[PlannedStructure], volumes: list[np.ndarray],
                 spared: frozenset[int] | set[int] = frozenset()) -> list[str]:
    present: set[int] = set()
    for data in volumes:
        present.update(np.unique(data).tolist())
    return [f"structure {p.structure.id} ({p.structure.name}) has no voxels"
            for p in planned
            if p.labels and p.structure.id not in present and p.structure.id not in spared]


def check_templates(recipe: Recipe, src: Path) -> list[str]:
    volumes = {v.name for v in recipe.volumes}
    problems = []
    for spec in recipe.templates:
        name = spec.source.id
        if not spec.source.licence:
            problems.append(f"template {name}: licence is missing")
        if spec.local_only and spec.source.redistribution:
            problems.append(f"template {name}: a shareable template must not be local-only")
        elif not spec.source.redistribution and not spec.local_only:
            problems.append(f"template {name}: redistribution is not allowed")
        if spec.licence_file and not (src / spec.licence_file).exists():
            problems.append(f"template {name}: licence file {spec.licence_file} is missing")
        if spec.volume not in volumes:
            problems.append(f"template {name}: unknown volume {spec.volume!r}")
    targets = [spec.volume for spec in recipe.templates]
    problems += [f"volume {v}: more than one template"
                 for v in sorted({t for t in targets if targets.count(t) > 1})]
    return problems
