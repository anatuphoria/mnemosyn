from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tools" / "package" / "requirements-release.txt"
PINNED = re.compile(r"^([a-z0-9][a-z0-9._-]*)==[^\s;]+(\s*;.+)?$")


def pins() -> dict[str, str]:
    lines = [line.strip() for line in PINS.read_text().splitlines() if line.strip()]
    assert all(PINNED.match(line) for line in lines)
    return {PINNED.match(line).group(1): line for line in lines}


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_every_release_library_has_one_exact_version():
    assert len(pins()) > 20


def test_every_library_the_release_asks_for_is_pinned():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    extras = project["optional-dependencies"]
    asked = project["dependencies"] + extras["desktop"] + extras["atlas-build"] + extras["package"]
    names = {canonical(re.split(r"[<>=!~\[ ]", text, maxsplit=1)[0]) for text in asked}
    assert names <= {canonical(name) for name in pins()}


def test_the_release_build_installs_from_the_pinned_list():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    installs = [line for line in workflow.splitlines() if "pip install" in line]
    assert installs
    assert all("-c tools/package/requirements-release.txt" in line for line in installs)
