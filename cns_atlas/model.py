from __future__ import annotations

from dataclasses import dataclass, field

FORMAT_VERSION = 1
KINDS = ("group", "region", "nucleus", "tract", "ventricle", "nerve-root")
SIDES = ("left", "right", "midline", "none")


@dataclass(frozen=True)
class Structure:
    id: int
    acronym: str
    name: str
    structure_id_path: tuple[int, ...]
    rgb_triplet: tuple[int, int, int]
    kind: str = "region"
    side: str = "none"
    concept: int | None = None
    synonyms: tuple[str, ...] = ()
    xrefs: dict[str, str] = field(default_factory=dict, hash=False)
    sources: tuple[str, ...] = ()

    @property
    def parent(self) -> int | None:
        return self.structure_id_path[-2] if len(self.structure_id_path) > 1 else None

    @property
    def depth(self) -> int:
        return len(self.structure_id_path) - 1

    def to_json(self) -> dict:
        data = {
            "id": self.id,
            "acronym": self.acronym,
            "name": self.name,
            "structure_id_path": list(self.structure_id_path),
            "rgb_triplet": list(self.rgb_triplet),
            "kind": self.kind,
            "side": self.side,
            "synonyms": list(self.synonyms),
            "xrefs": dict(sorted(self.xrefs.items())),
            "sources": list(self.sources),
        }
        if self.concept is not None:
            data["concept"] = self.concept
        return data

    @classmethod
    def from_json(cls, data: dict) -> Structure:
        concept = data.get("concept")
        return cls(
            id=int(data["id"]),
            acronym=str(data["acronym"]),
            name=str(data["name"]),
            structure_id_path=tuple(int(i) for i in data["structure_id_path"]),
            rgb_triplet=tuple(int(c) for c in data["rgb_triplet"]),
            kind=str(data.get("kind", "region")),
            side=str(data.get("side", "none")),
            concept=int(concept) if concept is not None else None,
            synonyms=tuple(str(s) for s in data.get("synonyms", ())),
            xrefs={str(k): str(v) for k, v in data.get("xrefs", {}).items()},
            sources=tuple(str(s) for s in data.get("sources", ())),
        )


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    authors: str
    year: int
    version: str
    licence: str
    redistribution: bool
    doi: str = ""
    url: str = ""

    def citation(self) -> str:
        return f"{self.authors} ({self.year}). {self.title}, version {self.version}."

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "version": self.version,
            "doi": self.doi,
            "url": self.url,
            "licence": self.licence,
            "redistribution": self.redistribution,
        }

    @classmethod
    def from_json(cls, data: dict) -> Source:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            authors=str(data["authors"]),
            year=int(data["year"]),
            version=str(data["version"]),
            licence=str(data.get("licence", "")),
            redistribution=data.get("redistribution") is True,
            doi=str(data.get("doi", "")),
            url=str(data.get("url", "")),
        )


@dataclass(frozen=True)
class Collection:
    key: str
    name: str
    members: tuple[int, ...]

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "members": list(self.members)}

    @classmethod
    def from_json(cls, data: dict) -> Collection:
        return cls(str(data["key"]), str(data["name"]), tuple(int(i) for i in data["members"]))


@dataclass(frozen=True)
class Pathway:
    key: str
    name: str
    steps: tuple[int, ...]

    def to_json(self) -> dict:
        return {"key": self.key, "name": self.name, "steps": list(self.steps)}

    @classmethod
    def from_json(cls, data: dict) -> Pathway:
        return cls(str(data["key"]), str(data["name"]), tuple(int(i) for i in data["steps"]))
