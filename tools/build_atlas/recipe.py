from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from cns_atlas.model import Source


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


def read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildError([f"{path}: file is missing"]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise BuildError([f"{path}: {exc}"]) from exc


def _source_spec(s: dict) -> SourceSpec:
    source = Source(id=s["id"], title=s["title"], authors=s["authors"], year=int(s["year"]),
                    version=str(s["version"]), licence=s.get("licence", ""),
                    redistribution=s.get("redistribution") is True,
                    doi=s.get("doi", ""), url=s.get("url", ""))
    return SourceSpec(source=source, download=s["download"], sha256=s["sha256"].lower(),
                      member=s.get("member", ""), label_names=s.get("label_names", ""),
                      volume=s["volume"], priority=int(s.get("priority", 0)),
                      verify_tls=s.get("verify_tls", True) is not False,
                      licence_file=s.get("licence_file", ""))


def load_recipe(path: Path) -> Recipe:
    data = read_toml(path)
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
        )
    except KeyError as exc:
        raise BuildError([f"{path}: missing key {exc}"]) from exc
