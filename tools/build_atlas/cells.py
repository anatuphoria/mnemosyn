from __future__ import annotations

import re
from pathlib import Path

from cns_atlas.cells import (FLOW_KINDS, LEVELS, Box, CellStep, CellType, CellView, Flow, Layer,
                             Placement, Reconstruction)
from cns_atlas.knowledge import KnowledgeError, parse_entry
from cns_atlas.model import Source, Structure

from .fetch import fetch_file
from .morphology import flatten, parse_swc
from .recipe import BuildError, read_toml

KEY = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")
PLANES = ("mid-body",)
VIEW_FIELDS = {"key", "name", "structures", "plane", "frame", "layers", "boxes", "cells", "flows",
               "levels"}
RECONSTRUCTION_FIELDS = {"id", "name", "species", "archive", "doi", "citation", "download",
                         "sha256"}
NEUROMORPHO = {"title": "NeuroMorpho.Org (RRID:SCR_002145)",
               "authors": "Tecuatl C, Ljungquist B, Ascoli GA", "year": 2024,
               "doi": "10.1096/fba.2024-00048", "url": "https://neuromorpho.org"}
LICENCE_FILE = Path("LICENSES") / "CC-BY-4.0.txt"


def load_cell_sources(folder: Path) -> list[dict]:
    if not folder.is_dir():
        return []
    views = []
    for path in sorted(folder.glob("*.toml")):
        data = read_toml(path)
        data["_file"] = str(path)
        views.append(data)
    return views


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _pair(value) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(map(_number, value))


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _keyed(items, where: str, kind: str) -> tuple[dict[str, dict], list[str]]:
    if not isinstance(items, list):
        return {}, [f"{where}: {kind}s must be a list of tables"]
    found, problems = {}, []
    for n, item in enumerate(items, 1):
        key = item.get("key") if isinstance(item, dict) else None
        if not (isinstance(key, str) and KEY.fullmatch(key)):
            problems.append(f"{where}: {kind} {n}: key must be lowercase letters, digits and "
                            f"hyphens")
        elif key in found:
            problems.append(f"{where}: {kind} {key!r} appears twice")
        else:
            found[key] = item
    return found, problems


def _layer_problems(key: str, layer: dict, where: str) -> list[str]:
    here = f"{where}: layer {key!r}"
    problems = [] if _text(layer.get("name")) else [f"{here}: needs name"]
    if not isinstance(layer.get("region", ""), str):
        problems.append(f"{here}: region must be text")
    colour = layer.get("colour")
    if not (isinstance(colour, list) and len(colour) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in colour)):
        problems.append(f"{here}: colour must be three numbers from 0 to 255")
    if not (_number(layer.get("width")) and layer["width"] > 0):
        problems.append(f"{here}: width must be a positive number")
    points = layer.get("points")
    if not (isinstance(points, list) and len(points) >= 2 and all(map(_pair, points))):
        problems.append(f"{here}: needs at least two points")
    return problems


def _box_problems(key: str, box: dict, where: str) -> list[str]:
    here = f"{where}: box {key!r}"
    problems = [] if _text(box.get("name")) else [f"{here}: needs name"]
    problems += [f"{here}: {name} must be two numbers" for name in ("centre", "size")
                 if not _pair(box.get(name))]
    ports = box.get("ports", {})
    if not (isinstance(ports, dict) and all(map(_pair, ports.values()))):
        problems.append(f"{here}: ports must map names to two numbers")
    return problems


def _reconstruction_problems(item, here: str) -> list[str]:
    if not isinstance(item, dict):
        return [f"{here}: must be a table"]
    problems = [f"{here}: unknown keys {sorted(set(item) - RECONSTRUCTION_FIELDS)}"] \
        if set(item) - RECONSTRUCTION_FIELDS else []
    if not isinstance(item.get("id"), int):
        problems.append(f"{here}: id must be a NeuroMorpho number")
    problems += [f"{here}: needs {name}" for name in sorted(RECONSTRUCTION_FIELDS - {"id"})
                 if name != "sha256" and not _text(item.get(name))]
    if not (isinstance(item.get("sha256"), str) and SHA256.fullmatch(item["sha256"])):
        problems.append(f"{here}: sha256 must be 64 lowercase hex digits")
    return problems


def _cell_problems(key: str, cell: dict, where: str, layers: dict) -> list[str]:
    here = f"{where}: cell {key!r}"
    problems = [] if _text(cell.get("name")) else [f"{here}: needs name"]
    if cell.get("level") not in LEVELS:
        problems.append(f"{here}: level must be one of {LEVELS}")
    if not (_number(cell.get("height")) and cell["height"] > 0):
        problems.append(f"{here}: height must be a positive number")
    placements = cell.get("placements")
    if not (isinstance(placements, list) and placements):
        problems.append(f"{here}: needs at least one placement")
        placements = []
    for n, place in enumerate(placements, 1):
        if not isinstance(place, dict):
            problems.append(f"{here}: placement {n} must be a table")
            continue
        for name in ("layer", "towards"):
            if place.get(name) not in layers:
                problems.append(f"{here}: unknown layer {place.get(name)!r}")
        start, end = place.get("start"), place.get("end")
        if not (_number(start) and _number(end) and 0 <= start < end <= 1):
            problems.append(f"{here}: placement {n} needs 0 <= start < end <= 1")
        if not (isinstance(place.get("copies"), int) and place["copies"] >= 1):
            problems.append(f"{here}: placement {n} needs at least one copy")
    items = cell.get("reconstructions")
    if not (isinstance(items, list) and items):
        return problems + [f"{here}: needs at least one reconstruction"]
    for n, item in enumerate(items, 1):
        problems += _reconstruction_problems(item, f"{here}: reconstruction {n}")
    return problems


def _end_problems(end, here: str, cells: dict, layers: dict, boxes: dict) -> list[str]:
    kind, _, name = str(end).partition(":")
    if kind == "cell" and name in cells or kind == "layer" and name in layers:
        return []
    if kind == "box":
        box, _, port = name.partition(".")
        if box in boxes and port in boxes[box].get("ports", {}):
            return []
    return [f"{here}: unknown end {end!r}"]


def _flow_problems(key: str, flow: dict, where: str, cells, layers, boxes) -> list[str]:
    here = f"{where}: flow {key!r}"
    problems = [] if flow.get("kind") in FLOW_KINDS else [f"{here}: kind must be one of "
                                                         f"{FLOW_KINDS}"]
    if not isinstance(flow.get("label", ""), str):
        problems.append(f"{here}: label must be text")
    for name in ("source", "target"):
        problems += _end_problems(flow.get(name), here, cells, layers, boxes)
    points = flow.get("points")
    if not (isinstance(points, list) and len(points) >= 2 and all(map(_pair, points))):
        problems.append(f"{here}: needs at least two points")
    return problems


def _flow_cells(flow: dict) -> set[str]:
    return {str(end).partition(":")[2] for end in (flow.get("source"), flow.get("target"))
            if str(end).startswith("cell:")}


def _level_problems(view: dict, where: str, cells: dict, flows: dict) -> list[str]:
    levels = view.get("levels")
    if not (isinstance(levels, dict) and set(levels) == set(LEVELS)):
        return [f"{where}: levels must be exactly {list(LEVELS)}"]
    problems = []
    for level in LEVELS:
        steps = levels[level].get("steps") if isinstance(levels[level], dict) else None
        if not (isinstance(steps, list) and steps):
            problems.append(f"{where}: {level} level needs at least one step")
            continue
        for n, step in enumerate(steps, 1):
            here = f"{where}: {level} step {n}"
            if not (isinstance(step, dict) and isinstance(step.get("flows"), list)
                    and isinstance(step.get("lit"), list) and step["flows"]):
                problems.append(f"{here}: needs flows and lit lists")
                continue
            for key in step["flows"]:
                if key not in flows:
                    problems.append(f"{here}: unknown flow {key!r}")
                elif level == "basic":
                    problems += [f"{here}: flow {key!r} uses full level cell {c!r}"
                                 for c in sorted(_flow_cells(flows[key]))
                                 if cells.get(c, {}).get("level") == "full"]
            for key in step["lit"]:
                if key not in cells:
                    problems.append(f"{here}: unknown cell {key!r}")
                elif level == "basic" and cells[key].get("level") == "full":
                    problems.append(f"{here}: {key!r} is a full level cell")
    return problems


def check_cell_sources(raw: list[dict], known_ids: set[int]) -> list[str]:
    problems = []
    seen: set[str] = set()
    for view in raw:
        where = view["_file"]
        unknown = set(view) - VIEW_FIELDS - {"_file"}
        if unknown:
            problems.append(f"{where}: unknown keys {sorted(unknown)}")
        key = view.get("key")
        if not (isinstance(key, str) and KEY.fullmatch(key)):
            problems.append(f"{where}: key must be lowercase letters, digits and hyphens")
        elif key in seen:
            problems.append(f"{where}: view {key!r} appears twice")
        elif Path(where).stem != key:
            problems.append(f"{where}: file name must be {key}.toml")
        seen.add(str(key))
        if not _text(view.get("name")):
            problems.append(f"{where}: needs name")
        structures = view.get("structures")
        if not (isinstance(structures, list) and structures
                and all(isinstance(i, int) for i in structures)):
            problems.append(f"{where}: structures must be a list of ids")
            structures = []
        problems += [f"{where}: unknown structure {i}" for i in structures if i not in known_ids]
        if view.get("plane") not in PLANES:
            problems.append(f"{where}: plane must be one of {PLANES}")
        if not (_pair(view.get("frame")) and min(view["frame"]) > 0):
            problems.append(f"{where}: frame must be two positive numbers")
        layers, found = _keyed(view.get("layers"), where, "layer")
        problems += found
        boxes, found = _keyed(view.get("boxes", []), where, "box")
        problems += found
        cells, found = _keyed(view.get("cells"), where, "cell")
        problems += found
        flows, found = _keyed(view.get("flows"), where, "flow")
        problems += found
        for key, layer in layers.items():
            problems += _layer_problems(key, layer, where)
        for key, box in boxes.items():
            problems += _box_problems(key, box, where)
        for key, cell in cells.items():
            problems += _cell_problems(key, cell, where, layers)
        for key, flow in flows.items():
            problems += _flow_problems(key, flow, where, cells, layers, boxes)
        problems += _level_problems(view, where, cells, flows)
    return problems


def raw_section_names(view: dict) -> list[str]:
    names = ["Overview"]
    for title, group in (("Cell", "cells"), ("Layer", "layers"), ("Box", "boxes")):
        names += [f"{title} {item['key']}" for item in view.get(group, [])]
    for level in LEVELS:
        steps = view["levels"][level]["steps"]
        names += [f"{level.capitalize()} step {n}" for n in range(1, len(steps) + 1)]
    return names


def check_cell_texts(knowledge_dir: Path, raw: list[dict]) -> list[str]:
    problems = []
    for view in raw:
        key = view.get("key")
        wanted = raw_section_names(view)
        paths = sorted(knowledge_dir.glob(f"*/cells-{key}.md"))
        english = knowledge_dir / "en" / f"cells-{key}.md"
        if english not in paths:
            problems.append(f"{english}: file is missing")
        for path in paths:
            try:
                entry = parse_entry(path.read_text(encoding="utf-8"), str(path))
            except KnowledgeError as exc:
                problems.append(str(exc))
                continue
            problems += [f"{path}: missing section {name!r}" for name in wanted
                         if not entry.sections.get(name)]
            problems += [f"{path}: section {name!r} names no item" for name in entry.sections
                         if name not in wanted]
    return problems


def check_cell_shapes(raw: list[dict], structures: list[Structure], shaped: set[int]) -> list[str]:
    problems = []
    for view in raw:
        for structure_id in view["structures"]:
            if not any(structure_id in s.structure_id_path and s.side in ("left", "right")
                       and s.id in shaped for s in structures):
                problems.append(f"{view['_file']}: structure {structure_id} has no shapes on "
                                f"either side")
    return problems


def _reconstruction(item: dict, here: str, cache: Path) -> Reconstruction:
    path = fetch_file(item["download"], item["sha256"], cache, here)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = flatten(parse_swc(text, here), here)
    return Reconstruction(item["id"], item["name"], item["species"], item["archive"],
                          item["doi"], item["citation"], lines)


def _view(data: dict, cache: Path, log) -> CellView:
    where = data["_file"]
    cells = []
    for cell in data["cells"]:
        log(f"fetching neurons for {data['key']} {cell['key']}")
        found = tuple(_reconstruction(item, f"{where}: cell {cell['key']!r}: reconstruction {n}",
                                      cache)
                      for n, item in enumerate(cell["reconstructions"], 1))
        cells.append(CellType(cell["key"], cell["name"], cell["level"], float(cell["height"]),
                              tuple(Placement(p["layer"], float(p["start"]), float(p["end"]),
                                              p["copies"], p["towards"])
                                    for p in cell["placements"]), found))
    layers = tuple(Layer(d["key"], d["name"], d.get("region", ""), tuple(d["colour"]),
                         tuple((float(x), float(y)) for x, y in d["points"]), float(d["width"]))
                   for d in data["layers"])
    boxes = tuple(Box(d["key"], d["name"], tuple(map(float, d["centre"])),
                      tuple(map(float, d["size"])),
                      {name: tuple(map(float, p)) for name, p in d.get("ports", {}).items()})
                  for d in data.get("boxes", []))
    flows = tuple(Flow(d["key"], d["kind"], d["source"], d["target"], d.get("label", ""),
                       tuple((float(x), float(y)) for x, y in d["points"]))
                  for d in data["flows"])
    levels = {level: tuple(CellStep(tuple(s["flows"]), tuple(s["lit"]))
                           for s in data["levels"][level]["steps"]) for level in LEVELS}
    return CellView(data["key"], data["name"], tuple(data["structures"]), data["plane"],
                    tuple(map(float, data["frame"])), layers, boxes, tuple(cells), flows, levels)


def build_cell_views(raw: list[dict], cache: Path, log=print) -> tuple[list[CellView],
                                                                        Source | None]:
    problems, views = [], []
    for data in raw:
        try:
            views.append(_view(data, cache, log))
        except BuildError as exc:
            problems += exc.problems
    if problems:
        raise BuildError(problems)
    if not views:
        return [], None
    papers = sorted({r.citation for v in views for c in v.cells for r in c.reconstructions})
    source = Source("neuromorpho", NEUROMORPHO["title"], NEUROMORPHO["authors"],
                    NEUROMORPHO["year"], f"reconstructions from {'; '.join(papers)}",
                    "CC BY 4.0", True, NEUROMORPHO["doi"], NEUROMORPHO["url"], "Neuron shapes")
    return views, source
