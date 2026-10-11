from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .recipe import read_toml


@dataclass(frozen=True)
class IdLock:
    published: frozenset[int]
    retired: frozenset[int]


def load_lock(path: Path) -> IdLock:
    if not path.exists():
        return IdLock(frozenset(), frozenset())
    data = read_toml(path)
    return IdLock(frozenset(int(i) for i in data.get("published", [])),
                  frozenset(int(i) for i in data.get("retired", [])))


def _block(name: str, ids: frozenset[int]) -> str:
    values = sorted(ids)
    if not values:
        return f"{name} = []\n"
    rows = [", ".join(str(v) for v in values[i:i + 16]) for i in range(0, len(values), 16)]
    return f"{name} = [\n" + "".join(f"  {row},\n" for row in rows) + "]\n"


def write_lock(path: Path, lock: IdLock) -> None:
    path.write_text(_block("published", lock.published) + _block("retired", lock.retired),
                    encoding="utf-8")
