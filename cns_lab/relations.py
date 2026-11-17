from __future__ import annotations

import ast
from functools import cache

from cns_atlas.models import LabModel


@cache
def names_in(expr: str) -> frozenset[str]:
    tree = ast.parse(expr.strip(), mode="eval")
    return frozenset(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))


def _starts(model: LabModel, kind: str, key: str) -> list[str]:
    if kind == "value":
        return [t.expr for t in model.terms if t.value == key]
    if kind == "part":
        part = next((p for p in model.parts if p.key == key), None)
        if part is None:
            return []
        exprs = [t.expr for t in model.terms if t.value in part.values]
        exprs += [f.expr for f in (*model.effects, *model.terms)
                  if f.arrow is not None and f.arrow[1] == key]
        return exprs
    if kind == "link":
        found = next((f for f in (*model.effects, *model.terms) if f.key == key), None)
        return [found.expr] if found is not None else []
    return []


def drivers(model: LabModel, selection) -> tuple[str, ...]:
    if not selection or len(selection) != 2:
        return ()
    kind, key = selection
    effects = {e.key: e.expr for e in model.effects}
    reached: set[str] = set()
    seen: set[str] = set()
    waiting = list(_starts(model, kind, key))
    while waiting:
        for name in names_in(waiting.pop()):
            if name in effects and name not in seen:
                seen.add(name)
                waiting.append(effects[name])
            else:
                reached.add(name)
    return tuple(p.key for p in model.parameters if p.panel and p.key in reached)


def selection_name(model: LabModel, selection) -> str:
    if not selection or len(selection) != 2:
        return ""
    kind, key = selection
    if kind == "value":
        found = next((v for v in model.values if v.key == key), None)
        return found.name if found is not None else ""
    if kind == "part":
        found = next((p for p in model.parts if p.key == key), None)
        return found.name if found is not None else ""
    if kind == "link":
        found = next((f for f in (*model.effects, *model.terms) if f.key == key), None)
        if found is None or found.arrow is None:
            return ""
        names = {p.key: p.name for p in model.parts}
        return f"the link from {names.get(found.arrow[0], '')} to {names.get(found.arrow[1], '')}"
    return ""
