from __future__ import annotations

import re
import tomllib
from html import escape
from typing import NamedTuple

ALIASES_FILE = "aliases.toml"
SIDED = ("left", "right")
SIDE_SUFFIX = re.compile(r" \((?:left|right)\)$")
SIDE_PREFIX = re.compile(r"^(?:left|right) ", re.IGNORECASE)
SHORTEST = 4


class Link(NamedTuple):
    start: int
    end: int
    target: int


def _phrase(text: str) -> str:
    return " ".join(text.split()).lower()


def read_aliases(path) -> tuple[dict[str, int], frozenset[str]]:
    if not path.exists():
        return {}, frozenset()
    table = tomllib.loads(path.read_text(encoding="utf-8"))
    aliases = {_phrase(k): int(v) for k, v in table.get("aliases", {}).items()}
    return aliases, frozenset(_phrase(word) for word in table.get("stop", []))


class NameIndex:
    def __init__(self, phrases: dict[str, int], home: dict[int, int],
                 stop: frozenset[str] = frozenset()) -> None:
        self.phrases = {p: t for p, t in phrases.items()
                        if len(p) >= SHORTEST and p not in stop}
        self.stop = stop
        self.home = home
        self._pattern: re.Pattern | None = None

    @classmethod
    def from_atlas(cls, atlas, lang: str = "en") -> NameIndex:
        found: dict[str, int] = {}
        clashing: set[str] = set()
        home: dict[int, int] = {}
        for structure in atlas.structures:
            target = structure.concept if structure.concept is not None else structure.id
            home[structure.id] = target
            names = [SIDE_SUFFIX.sub("", structure.name)]
            names += [SIDE_PREFIX.sub("", synonym) for synonym in structure.synonyms]
            for name in names:
                phrase = _phrase(name)
                if phrase in clashing:
                    continue
                if found.setdefault(phrase, target) != target:
                    del found[phrase]
                    clashing.add(phrase)
        aliases, stop = read_aliases(atlas.root / "knowledge" / lang / ALIASES_FILE)
        found.update((phrase, target) for phrase, target in aliases.items() if target in home)
        return cls(found, home, stop)

    def home_of(self, structure_id: int) -> int:
        return self.home.get(structure_id, structure_id)

    def _compiled(self) -> re.Pattern | None:
        if self._pattern is None and self.phrases:
            ordered = sorted(set(self.phrases) | self.stop, key=len, reverse=True)
            words = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in ordered)
            self._pattern = re.compile(rf"\b(?:{words})\b", re.IGNORECASE)
        return self._pattern

    def find(self, text: str, shown: int | None = None) -> list[Link]:
        pattern = self._compiled()
        if pattern is None:
            return []
        skip = set() if shown is None else {shown, self.home_of(shown)}
        links: list[Link] = []
        for match in pattern.finditer(text):
            target = self.phrases.get(_phrase(match.group()))
            if target is None or target in skip:
                continue
            skip.add(target)
            links.append(Link(match.start(), match.end(), target))
        return links


def linked_html(text: str, links: list[Link]) -> str:
    parts: list[str] = []
    at = 0
    for link in links:
        parts.append(escape(text[at:link.start], quote=False))
        parts.append(f"<a href='structure:{link.target}'>"
                     f"{escape(text[link.start:link.end], quote=False)}</a>")
        at = link.end
    parts.append(escape(text[at:], quote=False))
    return "".join(parts)
