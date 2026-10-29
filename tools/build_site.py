from __future__ import annotations

import argparse
import re
import shutil
import tomllib
from pathlib import Path

LOCK = ' :material-lock-outline:{ title="local builds only" }'


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


def _review_page(settings: dict) -> str:
    editions = settings.get("editions", [])
    latest = editions[0]
    form = settings.get("request_form", "")
    contact = settings["contact"]
    lines = ["# Review the atlas\n",
             "Mnemosyn asks specialists in neuroanatomy, neurology, neurosurgery, psychiatry and "
             "related fields to check its anatomy and clinical texts before students learn from "
             "them. The booklet explains what we are unsure of, chapter by chapter, and asks 50 "
             "numbered questions.\n",
             "## How to take part\n",
             "1. Download the booklet below and read it.",
             "2. Ask for access to the answer form with the request form on this page, giving the "
             "date from which you would like to answer.",
             f"3. Your request reaches us by email. We reply to you from {contact} with the link "
             "to the answer form, on or before the date you asked for. The answer form link is "
             "never published here.",
             "4. Answer the questions in your own time; the form saves your answers when you "
             "submit it.\n",
             "## The booklet\n",
             f"[:material-download: Download edition {latest['edition']} "
             f"({latest['date']})]({latest['file']}){{ .md-button .md-button--primary }}\n",
             "| Edition | Date | What changed |", "|---|---|---|"]
    lines += [f"| Edition {e['edition']} | {e['date']} | {e['changes']} |" for e in editions]
    lines += ["", "## Ask for access\n"]
    if form:
        lines.append(f'<iframe class="request-form" src="{form}?embedded=true" '
                     'title="Request access to the review">Loading the form</iframe>\n')
    else:
        lines.append(f"Requests open soon. Until then, write to [{contact}](mailto:{contact}) "
                     "with your name, speciality and the date you would like to start.\n")
    lines += ["## Your data\n",
              "The request form keeps your name, email address, speciality, institution if you "
              "give it, the date you asked for and your consent to be contacted. It is stored in "
              "a private Google Sheet owned by the project and used only to send you the answer "
              "form link and to keep in touch about the review. We keep it until the review ends "
              f"or until you ask us to delete it: write to [{contact}](mailto:{contact}).\n",
              "Reviewers who choose to be credited are listed on the "
              "[Reviewers](reviewers.md) page. Nobody is listed without that choice.\n"]
    return "\n".join(lines)


RELEASES = "https://github.com/anatuphoria/mnemosyn/releases"


def _download_page(version: str, quickstart: str) -> str:
    base = f"{RELEASES}/download/v{version}"
    if version:
        buttons = (f"[:material-microsoft-windows: Windows installer]("
                   f"{base}/Mnemosyn-{version}-Setup.exe){{ .md-button .md-button--primary }} "
                   f"[:material-linux: Linux AppImage]({base}/Mnemosyn-{version}-x86_64.AppImage)"
                   "{ .md-button .md-button--primary }")
        details = (f"Version {version}, a test version. Sizes and the `SHA256SUMS.txt` checksum "
                   f"file are on the [release page]({RELEASES}/tag/v{version}).")
    else:
        buttons = "The first test version is coming soon."
        details = "When it is out, it will appear here."
    return f"""# Download

{buttons}

{details} The download contains the shareable atlas: the spinal cord, the glands and the brainstem bodies come
from sources that have not yet allowed sharing, so they are not included.

## Requirements

- Windows: 64-bit Windows 10 or later.
- Linux: a 64-bit distribution from 2022 or later with a desktop, such as Ubuntu 22.04, Debian 12
  or Fedora 36.
- Graphics that support OpenGL 3.2, which almost every computer from the last ten years has.

## Opening it the first time

**Windows.** Run the installer. This test version is not signed yet, so Windows may show
"Windows protected your PC": choose **More info**, then **Run anyway**. Mnemosyn installs for your
account only, without administrator rights, and appears in the Start menu. Some antivirus programs
may also flag an unsigned app; that is a false alarm.

**Linux.** Make the file runnable, then open it:

```bash
chmod +x Mnemosyn-{version}-x86_64.AppImage
./Mnemosyn-{version}-x86_64.AppImage
```

Your quiz progress is kept in your user folder, so it survives updates.

## Build from source
{quickstart}"""


def _reviewers_page(settings: dict) -> str:
    people = settings.get("reviewers", [])
    if not people:
        return ("# Reviewers\n\nThe list of reviewers starts when the first reviews are in. "
                "Only reviewers who choose to be credited are listed.\n")
    rows = [f"- {p['name']}, {p['institution']}" if p.get("institution") else f"- {p['name']}"
            for p in people]
    return ("# Reviewers\n\nSpecialists who reviewed the atlas and chose to be credited.\n\n"
            + "\n".join(rows) + "\n")


def build_site(repo: Path, out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(repo / "site", out)
    for shot in sorted((repo / "brand").glob("screenshot*.png")):
        shutil.copy(shot, out / "assets" / shot.name)
    (out / "atlas").mkdir()
    (out / "design").mkdir()
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
    review = tomllib.loads((out / "review.toml").read_text())
    (out / "review.toml").unlink()
    (out / "review.md").write_text(_review_page(review))
    (out / "reviewers.md").write_text(_reviewers_page(review))
    published = tomllib.loads((out / "download.toml").read_text()).get("version", "")
    (out / "download.toml").unlink()
    from_source = (out / "build-from-source.md").read_text()
    (out / "build-from-source.md").unlink()
    (out / "download.md").write_text(_download_page(published, from_source))
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
