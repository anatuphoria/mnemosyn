from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from cns_atlas.models import LabModel
from cns_lab.checks import block_from_row
from cns_lab.experiment import Experiment
from cns_lab.files import write
from cns_lab.times import clock, duration, moment

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = Path(__file__).with_name("experiments.toml")
FILES = ROOT / "site" / "handbook" / "experiments" / "files"
SRC = ROOT / "atlas_src"
CLOCK_KINDS = ("peak_within", "trough_within")
HIT = 0.5


@dataclass(frozen=True)
class LabFile:
    slug: str
    file: str
    system: str
    length: float
    title: str
    note: str
    blocks: tuple[dict, ...]
    asserts: tuple[dict, ...]

    def blocks_at(self, start_clock: float) -> tuple[dict, ...]:
        return tuple(_block_row(b, start_clock) for b in self.blocks)

    def asserts_at(self, start_clock: float) -> tuple[dict, ...]:
        return tuple(_assert_row(a, start_clock) for a in self.asserts)


@dataclass(frozen=True)
class AtlasClaim:
    slug: str
    kind: str
    target: str
    expect: tuple[str, ...]


def _since_start(text: str, start_clock: float) -> float:
    return moment(text) - start_clock


def _block_row(row: dict, start_clock: float) -> dict:
    out = dict(row)
    if "start" in out:
        out["start"] = _since_start(out["start"], start_clock)
    if "length" in out:
        out["length"] = duration(out["length"])
    return out


def _assert_row(row: dict, start_clock: float) -> dict:
    out = dict(row)
    for field in ("at", "by"):
        if field in out:
            out[field] = _since_start(out[field], start_clock)
    if "window" in out:
        out["window"] = [_since_start(w, start_clock) for w in out["window"]]
    if out.get("kind") in CLOCK_KINDS:
        out["expect"] = [clock(w) for w in out["expect"]]
    return out


def load(path: Path = EXPERIMENTS) -> tuple[tuple[LabFile, ...], tuple[AtlasClaim, ...]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    lab = tuple(
        LabFile(row["slug"], row["file"], row["system"], duration(row["length"]), row["title"],
                row["note"], tuple(row["blocks"]), tuple(row["asserts"]))
        for row in data.get("lab", []))
    atlas = tuple(AtlasClaim(row["slug"], row["kind"], row["target"], tuple(row["expect"]))
                  for row in data.get("atlas", []))
    return lab, atlas


def experiment(entry: LabFile, model: LabModel) -> Experiment:
    blocks = tuple(block_from_row(model, row) for row in entry.blocks_at(model.start_clock))
    return Experiment(model.key, model.version, entry.length, model.start_clock, blocks,
                      title=entry.title, note=entry.note)


@cache
def source_models() -> dict[str, LabModel]:
    from cns_atlas.knowledge import load_references
    from tools.build_atlas.hierarchy import load_structures
    from tools.build_atlas.models import load_models
    from tools.build_atlas.pathways import load_pathways

    ids = {r.id for r in load_structures(SRC / "structures.toml")}
    references = load_references(SRC / "knowledge" / "references.toml")
    routes = {p.key for p in load_pathways(SRC / "pathways.toml")}
    return {m.key: m for m in load_models(SRC / "models", SRC / "knowledge", ids, references,
                                          routes)}


def write_files(models: dict[str, LabModel], out: Path = FILES) -> list[Path]:
    lab, _atlas = load()
    written = []
    for entry in lab:
        path = out / entry.slug / entry.file
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, experiment(entry, models[entry.system]))
        written.append(path)
    return written



def _territory_claim(atlas, claim: AtlasClaim) -> tuple[bool, str]:
    from cns_atlas.lesions import hits, territory_lesion

    found = next((s for s in atlas.structures if s.name == claim.target), None)
    if found is None:
        return False, f"no territory named {claim.target!r}"
    hit = {atlas.get(i).name: share for i, share in hits(atlas, territory_lesion(atlas, found.id))
           .items()}
    missing = [name for name in claim.expect if hit.get(name, 0.0) < HIT]
    return not missing, f"{claim.target} misses {missing}" if missing else claim.target


def _route_claim(atlas, claim: AtlasClaim) -> tuple[bool, str]:
    from cns_atlas.model import Crossing, Station

    route = next((p for p in atlas.pathways if p.key == claim.target), None)
    if route is None:
        return False, f"no route {claim.target!r}"
    crossed = False
    for step in route.steps:
        if isinstance(step, Crossing) or (isinstance(step, Station) and step.crossing):
            crossed = True
        elif crossed and isinstance(step, Station) and step.side == "same":
            return False, f"{route.name} returns to the same side after crossing"
    return crossed, route.name if crossed else f"{route.name} never crosses"


def check_atlas_claim(atlas, claim: AtlasClaim) -> tuple[bool, str]:
    if claim.kind == "territory":
        return _territory_claim(atlas, claim)
    if claim.kind == "route" and claim.expect == ("crosses",):
        return _route_claim(atlas, claim)
    return False, f"unknown claim {claim.kind} {claim.expect}"
