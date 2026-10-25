from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge import Entry, Reference

LEVELS = ("basic", "full")
FLOW_KINDS = ("excitatory", "inhibitory")

Point = tuple[float, float]


def _point(data) -> Point:
    x, y = data
    return float(x), float(y)


def _points(data) -> tuple[Point, ...]:
    return tuple(_point(p) for p in data)


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float, float], ...]

    def to_json(self) -> list:
        return [list(p) for p in self.points]

    @classmethod
    def from_json(cls, data) -> Polyline:
        return cls(tuple((float(x), float(y), float(w)) for x, y, w in data))


@dataclass(frozen=True)
class Reconstruction:
    neuromorpho_id: int
    name: str
    species: str
    archive: str
    doi: str
    citation: str
    lines: tuple[Polyline, ...]

    def to_json(self) -> dict:
        return {"id": self.neuromorpho_id, "name": self.name, "species": self.species,
                "archive": self.archive, "doi": self.doi, "citation": self.citation,
                "lines": [line.to_json() for line in self.lines]}

    @classmethod
    def from_json(cls, data: dict) -> Reconstruction:
        return cls(int(data["id"]), str(data["name"]), str(data["species"]),
                   str(data["archive"]), str(data["doi"]), str(data["citation"]),
                   tuple(Polyline.from_json(line) for line in data["lines"]))


@dataclass(frozen=True)
class Placement:
    layer: str
    start: float
    end: float
    copies: int
    towards: str

    def to_json(self) -> dict:
        return {"layer": self.layer, "start": self.start, "end": self.end,
                "copies": self.copies, "towards": self.towards}

    @classmethod
    def from_json(cls, data: dict) -> Placement:
        return cls(str(data["layer"]), float(data["start"]), float(data["end"]),
                   int(data["copies"]), str(data["towards"]))


@dataclass(frozen=True)
class CellType:
    key: str
    name: str
    level: str
    height: float
    placements: tuple[Placement, ...]
    reconstructions: tuple[Reconstruction, ...]

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "level": self.level, "height": self.height,
                "placements": [p.to_json() for p in self.placements],
                "reconstructions": [r.to_json() for r in self.reconstructions]}

    @classmethod
    def from_json(cls, data: dict) -> CellType:
        level = str(data["level"])
        if level not in LEVELS:
            raise ValueError(f"unknown cell level {level!r}")
        return cls(str(data["key"]), str(data["name"]), level, float(data["height"]),
                   tuple(Placement.from_json(p) for p in data["placements"]),
                   tuple(Reconstruction.from_json(r) for r in data["reconstructions"]))


@dataclass(frozen=True)
class Layer:
    key: str
    name: str
    region: str
    colour: tuple[int, int, int]
    points: tuple[Point, ...]
    width: float

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "region": self.region,
                "colour": list(self.colour), "points": [list(p) for p in self.points],
                "width": self.width}

    @classmethod
    def from_json(cls, data: dict) -> Layer:
        return cls(str(data["key"]), str(data["name"]), str(data["region"]),
                   tuple(int(c) for c in data["colour"]), _points(data["points"]),
                   float(data["width"]))


@dataclass(frozen=True)
class Box:
    key: str
    name: str
    centre: Point
    size: Point
    ports: dict[str, Point] = field(default_factory=dict, hash=False)

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "centre": list(self.centre),
                "size": list(self.size),
                "ports": {name: list(p) for name, p in self.ports.items()}}

    @classmethod
    def from_json(cls, data: dict) -> Box:
        return cls(str(data["key"]), str(data["name"]), _point(data["centre"]),
                   _point(data["size"]),
                   {str(name): _point(p) for name, p in data["ports"].items()})


@dataclass(frozen=True)
class Flow:
    key: str
    kind: str
    source: str
    target: str
    label: str
    points: tuple[Point, ...]

    def to_json(self) -> dict:
        return {"key": self.key, "kind": self.kind, "source": self.source,
                "target": self.target, "label": self.label,
                "points": [list(p) for p in self.points]}

    @classmethod
    def from_json(cls, data: dict) -> Flow:
        kind = str(data["kind"])
        if kind not in FLOW_KINDS:
            raise ValueError(f"unknown flow kind {kind!r}")
        return cls(str(data["key"]), kind, str(data["source"]), str(data["target"]),
                   str(data["label"]), _points(data["points"]))


@dataclass(frozen=True)
class CellStep:
    flows: tuple[str, ...]
    lit: tuple[str, ...]

    def to_json(self) -> dict:
        return {"flows": list(self.flows), "lit": list(self.lit)}

    @classmethod
    def from_json(cls, data: dict) -> CellStep:
        return cls(tuple(str(f) for f in data["flows"]), tuple(str(c) for c in data["lit"]))


@dataclass(frozen=True)
class CellView:
    key: str
    name: str
    structures: tuple[int, ...]
    plane: str
    frame: Point
    layers: tuple[Layer, ...]
    boxes: tuple[Box, ...]
    cells: tuple[CellType, ...]
    flows: tuple[Flow, ...]
    levels: dict[str, tuple[CellStep, ...]] = field(hash=False)

    def cells_at(self, level: str) -> tuple[CellType, ...]:
        if level not in LEVELS:
            raise ValueError(f"unknown level {level!r}")
        return self.cells if level == "full" else tuple(c for c in self.cells
                                                        if c.level == "basic")

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "structures": list(self.structures),
                "plane": self.plane, "frame": list(self.frame),
                "layers": [layer.to_json() for layer in self.layers],
                "boxes": [box.to_json() for box in self.boxes],
                "cells": [cell.to_json() for cell in self.cells],
                "flows": [flow.to_json() for flow in self.flows],
                "levels": {level: [step.to_json() for step in steps]
                           for level, steps in self.levels.items()}}

    @classmethod
    def from_json(cls, data: dict) -> CellView:
        levels = {str(level): tuple(CellStep.from_json(s) for s in steps)
                  for level, steps in data["levels"].items()}
        if set(levels) != set(LEVELS):
            raise ValueError(f"levels must be {LEVELS}, got {sorted(levels)}")
        return cls(str(data["key"]), str(data["name"]),
                   tuple(int(i) for i in data["structures"]), str(data["plane"]),
                   _point(data["frame"]),
                   tuple(Layer.from_json(d) for d in data["layers"]),
                   tuple(Box.from_json(d) for d in data["boxes"]),
                   tuple(CellType.from_json(d) for d in data["cells"]),
                   tuple(Flow.from_json(d) for d in data["flows"]), levels)


@dataclass(frozen=True)
class CellText:
    status: str
    overview: str
    items: dict[str, str] = field(hash=False)
    steps: dict[str, tuple[str, ...]] = field(hash=False)
    references: tuple[Reference, ...] = ()


def item_sections(view: CellView) -> dict[str, str]:
    groups = (("Cell", "cell", view.cells), ("Layer", "layer", view.layers),
              ("Box", "box", view.boxes))
    return {f"{prefix}:{item.key}": f"{title} {item.key}"
            for title, prefix, group in groups for item in group}


def step_sections(view: CellView, level: str) -> list[str]:
    return [f"{level.capitalize()} step {n}" for n in range(1, len(view.levels[level]) + 1)]


def section_names(view: CellView) -> list[str]:
    return ["Overview", *item_sections(view).values(),
            *(name for level in LEVELS for name in step_sections(view, level))]


def text_for(entry: Entry, view: CellView) -> CellText:
    def show(name: str) -> str:
        return entry.numbered(entry.sections.get(name, ""))

    items = {item: show(name) for item, name in item_sections(view).items()}
    steps = {level: tuple(map(show, step_sections(view, level))) for level in LEVELS}
    return CellText(entry.status, show("Overview"), items, steps, entry.references)
