from __future__ import annotations

import argparse
import re
import shutil
import tomllib
from pathlib import Path

LOCK = ' :material-lock-outline:{ title="local builds only" }'


def _sections(readme: str) -> dict[str, str]:
    return dict(re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", readme, re.DOTALL | re.MULTILINE))


def _sources(recipe: dict) -> list[dict]:
    return recipe["sources"] + recipe.get("tracts", []) + recipe.get("templates", [])


def _structures_page(structures: dict, local: set[str]) -> str:
    groups = {g["id"]: g for g in structures["groups"]}
    children: dict[int, list[dict]] = {}
    for item in structures["groups"][1:] + structures["concepts"]:
        children.setdefault(item["parent"], []).append(item)

    def colour(item: dict | None) -> str:
        while item:
            if "color" in item:
                return "rgb({}, {}, {})".format(*item["color"])
            item = groups.get(item.get("parent"))
        return "#888"

    def walk(group_id: int, depth: int) -> list[str]:
        lines = []
        for child in children.get(group_id, []):
            if child["id"] not in groups:
                continue
            lines.append(f"\n{'#' * min(depth, 6)} {child['name']}\n")
            rows = [c for c in children.get(child["id"], []) if c["id"] not in groups]
            if rows:
                lines.append("| | Name | Acronym | Kind | Sides | Source |\n|---|---|---|---|---|---|")
            for c in rows:
                src = c.get("source", structures["default_source"])
                sides = "left and right" if "left" in c and "right" in c else "midline"
                lines.append(f'| <span class="dot" style="background:{colour(c)}"></span> '
                             f"| {c['name']} | {c['acronym']} | {c.get('kind', 'region')} | {sides} "
                             f"| [{src}](sources.md#{src}){LOCK if src in local else ''} |")
            lines += walk(child["id"], depth + 1)
        return lines

    head = (f"# Structures\n\n{len(structures['concepts'])} structures in {len(groups)} groups, "
            "generated from `atlas_src/structures.toml`. :material-lock-outline: marks shapes that "
            "appear in local builds only, until their authors allow sharing.\n")
    return head + "\n".join(walk(1, 2)) + "\n"


def _sources_page(sources: list[dict], local: set[str]) -> str:
    intro = ("Every source is downloaded from its publisher and checked against a pinned checksum. "
             "Generated from `atlas_src/recipe.toml`.\n")
    lines = ["# Data sources\n", intro]
    for s in sources:
        lines.append(f"## {s.get('provides', s['title'])} {{ #{s['id']} }}\n")
        if s["id"] in local:
            lines.append('!!! note "Local builds only"\n    No licence for sharing yet; the authors '
                         "have been asked for permission.\n")
        cite = f"{s.get('authors', '')} ({s.get('year', '')}). *{s['title']}*."
        if s.get("doi"):
            cite += f" [doi:{s['doi']}](https://doi.org/{s['doi']})"
        lines += [cite + "\n", f"- **Licence:** {s.get('licence', 'none stated')}"]
        if s.get("url"):
            lines.append(f"- **Page:** <{s['url']}>")
        lines.append(f"- **Id:** `{s['id']}`\n")
    return "\n".join(lines)


def build_site(repo: Path, out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(repo / "site", out)
    (out / "atlas").mkdir()
    (out / "design").mkdir()
    sections = _sections((repo / "README.md").read_text())
    structures = tomllib.loads((repo / "atlas_src/structures.toml").read_text())
    sources = _sources(tomllib.loads((repo / "atlas_src/recipe.toml").read_text()))
    local = {s["id"] for s in sources if s.get("local_only")}
    decisions = (repo / "docs/decisions.md").read_text()
    counts = {"structures": len(structures["concepts"]), "groups": len(structures["groups"]),
              "shared": len(sources) - len(local),
              "decisions": len(re.findall(r"^\| \d+ \|", decisions, re.MULTILINE))}
    home = (out / "index.md").read_text()
    for key, value in counts.items():
        home = home.replace(f"@{key}@", str(value))
    (out / "index.md").write_text(home)
    (out / "install.md").write_text("# Install\n" + sections["Quickstart"])
    (out / "guide.md").write_text("# Using the app\n" + sections["Desktop app"])
    (out / "performance.md").write_text("# Performance\n" + sections["Performance"])
    (out / "atlas/structures.md").write_text(_structures_page(structures, local))
    (out / "atlas/sources.md").write_text(_sources_page(sources, local))
    (out / "decisions.md").write_text(decisions.replace("](specs/", "](design/"))
    index = ["# Design documents\n", "The full design behind each part of Mnemosyn, oldest first.\n"]
    for spec in sorted((repo / "docs/specs").glob("*.md")):
        shutil.copy(spec, out / "design" / spec.name)
        title = spec.read_text().splitlines()[0].lstrip("# ")
        index.append(f"- {spec.name[:10]}: [{title}]({spec.name})")
    (out / "design/index.md").write_text("\n".join(index) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.build_site",
                                     description="Write the website pages for MkDocs")
    parser.add_argument("--out", type=Path, default=Path("build/site-docs"))
    args = parser.parse_args(argv)
    build_site(Path.cwd(), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
