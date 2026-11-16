from __future__ import annotations

import codecs
import datetime
import re
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

SECTIONS = ("Function", "Connections", "Clinical")
STATUSES = ("draft", "reviewed")
BOM = codecs.BOM_UTF8.decode()
CITATION = re.compile(r"\[([a-z][a-z0-9_-]*)\](?!\()")
STEP_SECTION = re.compile(r"Step [1-9][0-9]*")


def _section_allowed(name: str, target: int | str) -> bool:
    if isinstance(target, str) and target.startswith("pathway-"):
        return name == "Overview" or STEP_SECTION.fullmatch(name) is not None
    return name in SECTIONS


class KnowledgeError(ValueError):
    pass


@dataclass(frozen=True)
class Reference:
    key: str
    authors: str
    title: str
    year: int
    journal: str = ""
    volume: str = ""
    pages: str = ""
    edition: str = ""
    publisher: str = ""
    doi: str = ""
    url: str = ""
    isbn: str = ""

    @property
    def has_locator(self) -> bool:
        return bool(self.doi or self.url or self.isbn)

    @property
    def link(self) -> str:
        return f"https://doi.org/{self.doi}" if self.doi else self.url

    def citation(self) -> str:
        parts = [f"{self.authors} ({self.year}). {self.title}."]
        if self.journal:
            detail = self.journal
            if self.volume:
                detail += f" {self.volume}"
            if self.pages:
                detail += f": {self.pages}"
            parts.append(f"{detail}.")
        if self.edition:
            parts.append(f"{self.edition} edition.")
        if self.publisher:
            parts.append(f"{self.publisher}.")
        if self.isbn:
            parts.append(f"ISBN {self.isbn}.")
        if self.doi:
            parts.append(f"doi:{self.doi}")
        return " ".join(parts)


REFERENCE_FIELDS = {f.name for f in fields(Reference)} - {"key"}


@dataclass(frozen=True)
class Reviewer:
    key: str
    name: str = ""
    speciality: str = ""
    institution: str = ""

    def label(self) -> str:
        if not self.name:
            return f"a specialist in {self.speciality}" if self.speciality else "a specialist"
        return ", ".join(part for part in (self.name, self.speciality, self.institution) if part)


REVIEWER_FIELDS = {f.name for f in fields(Reviewer)} - {"key"}


@dataclass(frozen=True)
class Entry:
    target: int | str
    status: str
    sections: dict[str, str]
    citations: tuple[str, ...]
    references: tuple[Reference, ...] = ()
    reviewed_on: str = ""
    reviewed_by: tuple[str, ...] = ()
    reviewers: tuple[Reviewer, ...] = ()

    def review_line(self) -> str:
        if self.status != "reviewed":
            return "not yet reviewed"
        who = " and ".join(r.label() for r in self.reviewers)
        when = ""
        if self.reviewed_on:
            day = datetime.date.fromisoformat(self.reviewed_on)
            when = f"{day.day} {day.strftime('%B %Y')}"
        return " ".join(part for part in (f"by {who}" if who else "", f"on {when}" if when else "")
                        if part)

    def numbered(self, text: str) -> str:
        order = {key: n for n, key in enumerate(self.citations, 1)}
        return CITATION.sub(
            lambda m: f"[{order[m.group(1)]}]" if m.group(1) in order else m.group(0), text)


def parse_entry(text: str, origin: str) -> Entry:
    text = text.removeprefix(BOM).replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    if not text.startswith("+++\n"):
        raise KnowledgeError(f"{origin}: missing '+++' header")
    end = text.find("\n+++\n", 3)
    if end < 0:
        raise KnowledgeError(f"{origin}: header is not closed with '+++'")
    try:
        header = tomllib.loads(text[4:end])
    except tomllib.TOMLDecodeError as exc:
        raise KnowledgeError(f"{origin}: invalid header: {exc}") from exc
    if ("id" in header) == ("key" in header):
        raise KnowledgeError(f"{origin}: header needs exactly one of 'id' or 'key'")
    target = header.get("id", header.get("key"))
    if "id" in header and not isinstance(target, int):
        raise KnowledgeError(f"{origin}: 'id' must be an integer")
    if "key" in header and not isinstance(target, str):
        raise KnowledgeError(f"{origin}: 'key' must be a string")
    status = header.get("status", "draft")
    if status not in STATUSES:
        raise KnowledgeError(f"{origin}: status must be one of {STATUSES}")
    reviewed_on = header.get("reviewed_on", "")
    if isinstance(reviewed_on, datetime.date):
        reviewed_on = reviewed_on.isoformat()
    try:
        datetime.date.fromisoformat(reviewed_on or "2000-01-01")
    except (TypeError, ValueError) as exc:
        raise KnowledgeError(f"{origin}: 'reviewed_on' must be a date like 2026-11-20") from exc
    reviewed_by = header.get("reviewed_by", [])
    if not isinstance(reviewed_by, list) or not all(isinstance(k, str) for k in reviewed_by):
        raise KnowledgeError(f"{origin}: 'reviewed_by' must be a list of reviewer keys")
    sections: dict[str, str] = {}
    current = None
    for line in text[end + 5:].split("\n"):
        if line.startswith("## "):
            current = line[3:].strip()
            if not _section_allowed(current, target):
                raise KnowledgeError(f"{origin}: unknown section '{current}'")
            if current in sections:
                raise KnowledgeError(f"{origin}: section '{current}' appears twice")
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
        elif line.strip():
            raise KnowledgeError(f"{origin}: text before the first section")
    sections = {name: body.strip() for name, body in sections.items()}
    citations = tuple(dict.fromkeys(CITATION.findall("\n".join(sections.values()))))
    return Entry(target=target, status=status, sections=sections, citations=citations,
                 reviewed_on=reviewed_on, reviewed_by=tuple(reviewed_by))


def load_reviewers(path: Path) -> dict[str, Reviewer]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise KnowledgeError(f"{path}: {exc}") from exc
    reviewers = {}
    for key, values in data.items():
        unknown = set(values) - REVIEWER_FIELDS
        if unknown:
            raise KnowledgeError(f"{path}: [{key}] unknown fields {sorted(unknown)}")
        reviewers[key] = Reviewer(key=key, **{k: str(v) for k, v in values.items()})
    return reviewers


def review_problems(entry: Entry, reviewers: dict[str, Reviewer], origin: str) -> list[str]:
    problems = [f"{origin}: unknown reviewer [{key}]" for key in entry.reviewed_by
                if key not in reviewers]
    if entry.status == "reviewed" and not (entry.reviewed_by and entry.reviewed_on):
        problems.append(f"{origin}: a reviewed text needs 'reviewed_by' and 'reviewed_on'")
    if entry.status == "draft" and (entry.reviewed_by or entry.reviewed_on):
        problems.append(f"{origin}: a draft cannot name a reviewer or a review date")
    return problems


def load_references(path: Path) -> dict[str, Reference]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise KnowledgeError(f"{path}: {exc}") from exc
    references = {}
    for key, values in data.items():
        unknown = set(values) - REFERENCE_FIELDS
        if unknown:
            raise KnowledgeError(f"{path}: [{key}] unknown fields {sorted(unknown)}")
        missing = {"authors", "title", "year"} - set(values)
        if missing:
            raise KnowledgeError(f"{path}: [{key}] missing {sorted(missing)}")
        cleaned = {k: int(v) if k == "year" else str(v) for k, v in values.items()}
        references[key] = Reference(key=key, **cleaned)
    return references


def resolve(entry: Entry, references: dict[str, Reference],
            reviewers: dict[str, Reviewer] | None = None) -> Entry:
    found = tuple(references[key] for key in entry.citations if key in references)
    people = tuple(reviewers[key] for key in entry.reviewed_by if key in reviewers) if reviewers else ()
    return replace(entry, references=found, reviewers=people)
