from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .knowledge import Entry, KnowledgeError, Reference, load_references, parse_entry, resolve
from .meshes import LODS, MeshData, MeshLod
from .model import FORMAT_VERSION, Collection, Pathway, Source, Structure
from .volume import LabelVolume

DISCLAIMER = (
    "This atlas is a personal study project. It was not built or reviewed by a neuroanatomy "
    "specialist and may contain errors. It is not for diagnosis or treatment. Corrections and "
    "feedback are welcome."
)


class AtlasError(Exception):
    pass


def _read_json(path: Path):
    if not path.exists():
        raise AtlasError(f"{path}: file is missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AtlasError(f"{path}: not valid JSON ({exc})") from exc


def _subtree_ends(structures: tuple[Structure, ...]) -> list[int]:
    ends = [len(structures)] * len(structures)
    stack: list[int] = []
    for i, s in enumerate(structures):
        while stack and structures[stack[-1]].depth >= s.depth:
            ends[stack.pop()] = i
        stack.append(i)
    return ends


class Atlas:
    def __init__(self, root: Path, metadata: dict, structures: tuple[Structure, ...],
                 sources: dict[str, Source], collections: tuple[Collection, ...],
                 pathways: tuple[Pathway, ...]) -> None:
        self.root = root
        self.metadata = metadata
        self.structures = structures
        self.sources = sources
        self.collections = collections
        self.pathways = pathways
        self._position = {s.id: i for i, s in enumerate(structures)}
        self._children: dict[int, list[int]] = {s.id: [] for s in structures}
        for s in structures:
            if s.parent is not None:
                self._children[s.parent].append(s.id)
        self._subtree_end = _subtree_ends(structures)
        meshes = root / "meshes"
        self._lods = {level: MeshLod(meshes / name) for level, name in enumerate(LODS)
                      if (meshes / name / "index.npy").exists()}
        self.volumes = tuple(
            LabelVolume(root / v["file"], v["space"], np.array(v["affine_to_world"]))
            for v in metadata.get("volumes", []))
        self._references: dict[str, Reference] | None = None
        self._entries: dict[tuple[str, int | str], Entry | None] = {}
        self._search_rows = []
        for s in structures:
            terms = tuple(t.lower() for t in (s.name, s.acronym, *s.synonyms, *s.xrefs.values()))
            self._search_rows.append((s.id, s.name.lower(), terms, "\x00".join(terms)))

    @classmethod
    def open(cls, path) -> Atlas:
        root = Path(path)
        if not root.is_dir():
            raise AtlasError(f"{root}: atlas package not found")
        metadata = _read_json(root / "metadata.json")
        version = metadata.get("format_version")
        if version != FORMAT_VERSION:
            raise AtlasError(f"{root / 'metadata.json'}: format_version {version!r} is not "
                             f"supported (expected {FORMAT_VERSION})")
        try:
            structures = tuple(Structure.from_json(d) for d in _read_json(root / "structures.json"))
            sources = {s.id: s for s in map(Source.from_json, _read_json(root / "sources.json"))}
            collections = tuple(map(Collection.from_json, _read_json(root / "collections.json")))
            pathways = tuple(map(Pathway.from_json, _read_json(root / "pathways.json")))
        except (KeyError, TypeError, ValueError) as exc:
            raise AtlasError(f"{root}: malformed record ({exc!r})") from exc
        position = {s.id: i for i, s in enumerate(structures)}
        for i, s in enumerate(structures):
            if s.parent is not None and s.parent not in position:
                raise AtlasError(f"{root / 'structures.json'}: structure {s.id} has unknown "
                                 f"parent {s.parent}")
            if s.parent is not None and position[s.parent] > i:
                raise AtlasError(f"{root / 'structures.json'}: structure {s.id} appears before "
                                 f"its parent")
        return cls(root, metadata, structures, sources, collections, pathways)

    def get(self, structure_id: int) -> Structure:
        return self.structures[self._position[structure_id]]

    def __contains__(self, structure_id: object) -> bool:
        return structure_id in self._position

    def children(self, structure_id: int) -> tuple[int, ...]:
        return tuple(self._children[structure_id])

    def ancestors(self, structure_id: int) -> tuple[int, ...]:
        return self.get(structure_id).structure_id_path[:-1]

    def subtree(self, structure_id: int) -> slice:
        i = self._position[structure_id]
        return slice(i, self._subtree_end[i])

    def has_mesh(self, structure_id: int) -> bool:
        return any(structure_id in lod for lod in self._lods.values())

    def mesh(self, structure_id: int, lod: int = 0) -> MeshData | None:
        for level in sorted(self._lods, key=lambda level: (abs(level - lod), level)):
            data = self._lods[level].get(structure_id)
            if data is not None:
                return data
        return None

    def search(self, text: str, limit: int | None = 50) -> list[int]:
        needle = " ".join(text.lower().split())
        if not needle:
            return []
        term_start = "\x00" + needle
        ranked = []
        for structure_id, name, terms, blob in self._search_rows:
            if needle not in blob:
                continue
            if needle in terms:
                rank = 0
            elif blob.startswith(needle) or term_start in blob:
                rank = 1
            else:
                rank = 2
            ranked.append((rank, name, structure_id))
        ranked.sort()
        ids = [structure_id for _, _, structure_id in ranked]
        return ids if limit is None else ids[:limit]

    @property
    def references(self) -> dict[str, Reference]:
        if self._references is None:
            path = self.root / "knowledge" / "references.toml"
            try:
                self._references = load_references(path) if path.exists() else {}
            except KnowledgeError as exc:
                raise AtlasError(str(exc)) from exc
        return self._references

    def knowledge(self, target: int | str, lang: str = "en") -> Entry | None:
        if isinstance(target, int):
            if target not in self._position:
                return None
            structure = self.get(target)
            target = structure.concept if structure.concept is not None else structure.id
        for language in dict.fromkeys((lang, "en")):
            entry = self._entry(language, target)
            if entry is not None:
                return entry
        return None

    def _entry(self, lang: str, target: int | str) -> Entry | None:
        key = (lang, target)
        if key not in self._entries:
            path = self.root / "knowledge" / lang / f"{target}.md"
            entry = None
            if path.exists():
                try:
                    parsed = parse_entry(path.read_text(encoding="utf-8"), str(path))
                except KnowledgeError as exc:
                    raise AtlasError(str(exc)) from exc
                entry = resolve(parsed, self.references)
            self._entries[key] = entry
        return self._entries[key]

    def label_at(self, point) -> int | None:
        for volume in self.volumes:
            label = volume.label_at(point)
            if label and label in self._position:
                return label
        return None
