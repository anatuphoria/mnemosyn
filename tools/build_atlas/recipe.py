from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from cns_atlas.model import Source

MESH_GRIDS = ("label", "native")


class BuildError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class SourceSpec:
    source: Source
    download: str
    sha256: str
    member: str
    label_names: str
    volume: str
    priority: int
    verify_tls: bool = True
    licence_file: str = ""
    drop: tuple = ()
    mesh_grid: str = "label"
    local_only: bool = False
    mask: bool = False
    members: tuple[tuple[str, str], ...] = ()
    manual: bool = False
    crop: bool = False
    threshold: float | None = None
    margin: float = 0.0
    separate: bool = False
    fill: bool = False

    @property
    def member_values(self) -> dict[str, int]:
        return {name: value for value, (name, _) in enumerate(self.members, 1)}


@dataclass(frozen=True)
class TractSpec:
    source: Source
    download: str
    files: tuple[tuple[str, str], ...]
    labels: str
    drop: tuple[str, ...] = ()
    verify_tls: bool = True
    licence_file: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.files)

    def file_spec(self, name: str) -> SourceSpec:
        return SourceSpec(source=self.source, download=self.download.replace("{name}", name),
                          sha256=dict(self.files)[name], member="", label_names="",
                          volume=self.labels, priority=0, verify_tls=self.verify_tls)


@dataclass(frozen=True)
class VolumeSpec:
    name: str
    space: str
    grid_source: str


@dataclass(frozen=True)
class Recipe:
    name: str
    version: str
    species: str
    citation: str
    atlas_link: str
    licence: str
    lod0_max_faces: int
    lod_fractions: tuple[float, ...]
    min_faces: int
    smoothing_iterations: int
    smoothing_pass_band: float
    sources: tuple[SourceSpec, ...]
    volumes: tuple[VolumeSpec, ...]
    templates: tuple[SourceSpec, ...] = ()
    tracts: tuple[TractSpec, ...] = ()


def read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildError([f"{path}: file is missing"]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise BuildError([f"{path}: {exc}"]) from exc


def _source(s: dict) -> Source:
    return Source(id=s["id"], title=s["title"], authors=s["authors"], year=int(s["year"]),
                  version=str(s["version"]), licence=s.get("licence", ""),
                  redistribution=s.get("redistribution") is True,
                  doi=s.get("doi", ""), url=s.get("url", ""))


def _source_spec(s: dict) -> SourceSpec:
    return SourceSpec(source=_source(s), download=s["download"], sha256=s["sha256"].lower(),
                      member=s.get("member", ""), label_names=s.get("label_names", ""),
                      volume=s["volume"], priority=int(s.get("priority", 0)),
                      verify_tls=s.get("verify_tls", True) is not False,
                      licence_file=s.get("licence_file", ""), drop=tuple(s.get("drop", ())),
                      mesh_grid=str(s.get("mesh_grid", "label")),
                      local_only=s.get("local_only") is True, mask=s.get("mask") is True,
                      threshold=float(s["threshold"]) if "threshold" in s else None,
                      margin=float(s.get("margin", 0)), separate=s.get("separate") is True,
                      fill=s.get("fill") is True,
                      members=tuple((str(k), str(v)) for k, v in s.get("members", {}).items()),
                      manual=s.get("manual") is True, crop=s.get("crop") is True)


def _tract_spec(t: dict) -> TractSpec:
    files = tuple(sorted((str(name), str(sha).lower()) for name, sha in t.get("files", {}).items()))
    return TractSpec(source=_source(t), download=t["download"], files=files, labels=t["labels"],
                     drop=tuple(str(name) for name in t.get("drop", ())),
                     verify_tls=t.get("verify_tls", True) is not False,
                     licence_file=t.get("licence_file", ""))


def load_recipe(path: Path) -> Recipe:
    data = read_toml(path)
    misplaced = [f"{kind} {t.get('id')}: only label sources and templates can be local-only"
                 for kind in ("tracts",) for t in data.get(kind, [])
                 if isinstance(t, dict) and "local_only" in t]
    if misplaced:
        raise BuildError(misplaced)
    try:
        return Recipe(
            name=data["name"],
            version=data["version"],
            species=data["species"],
            citation=data.get("citation", "unpublished"),
            atlas_link=data.get("atlas_link", ""),
            licence=data["licence"],
            lod0_max_faces=int(data["lod0_max_faces"]),
            lod_fractions=tuple(float(f) for f in data["lod_fractions"]),
            min_faces=int(data["min_faces"]),
            smoothing_iterations=int(data["smoothing_iterations"]),
            smoothing_pass_band=float(data["smoothing_pass_band"]),
            sources=tuple(_source_spec(s) for s in data.get("sources", [])),
            volumes=tuple(VolumeSpec(v["name"], v["space"], v["grid_source"])
                          for v in data.get("volumes", [])),
            templates=tuple(_source_spec(t) for t in data.get("templates", [])),
            tracts=tuple(_tract_spec(t) for t in data.get("tracts", [])),
        )
    except KeyError as exc:
        raise BuildError([f"{path}: missing key {exc}"]) from exc
