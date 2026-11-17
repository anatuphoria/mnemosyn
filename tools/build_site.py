from __future__ import annotations

import argparse
import re
import shutil
import textwrap
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
        lines.append('<div class="source" markdown>\n')
        if s["id"] in local:
            lines.append('<span class="chip gold">Local builds only</span> No licence for sharing '
                         "yet; the authors have been asked for permission.\n")
        cite = f"{s.get('authors', '')} ({s.get('year', '')}). *{s['title']}*."
        if s.get("doi"):
            cite += f" [doi:{s['doi']}](https://doi.org/{s['doi']})"
        lines += [cite + "\n", '<div class="meta" markdown>\n',
                  f"- **Licence** {s.get('licence', 'none stated')}"]
        if s.get("url"):
            lines.append(f"- **Page** <{s['url']}>")
        lines.append(f"- **Id** `{s['id']}`\n\n</div>\n\n</div>\n")
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


PLATFORMS = (
    ("windows", ":material-microsoft-windows:", "Windows", "Setup.exe", "Installer",
     "64-bit Windows 10 or later."),
    ("linux", ":material-linux:", "Linux", "x86_64.AppImage", "AppImage",
     "A 64-bit distribution from 2022 or later with a desktop, such as Ubuntu 22.04, Debian 12 "
     "or Fedora 36."),
    ("mac", ":material-apple:", "Mac", "macOS-arm64.dmg", "Disk image",
     "Apple Silicon (M1 or later) with macOS 14 or later. Intel Macs are not supported."),
)
OPENING = {
    "windows": """Run the installer. This test version is not signed yet, so Windows may show
"Windows protected your PC": choose **More info**, then **Run anyway**. Mnemosyn installs for your
account only, without administrator rights, and appears in the Start menu. Some antivirus programs
may also flag an unsigned app; that is a false alarm.""",
    "linux": """Make the file runnable, then open it:

```bash
chmod +x Mnemosyn-{version}-x86_64.AppImage
./Mnemosyn-{version}-x86_64.AppImage
```""",
    "mac": """Open the disk image and drag Mnemosyn onto the Applications folder beside it. This
test version is not signed with an Apple certificate, so the first time you open it macOS says it
could not check the app. Close that message, open **System Settings**, then
**Privacy & Security**, scroll down to the line about Mnemosyn and choose **Open Anyway**. You
only do this once. On a Mac managed by a school or an employer this choice may be switched off.

Use Cmd wherever the handbook says Ctrl.""",
}


ELSEWHERE = {
    "mobile": (":material-monitor:", "Mnemosyn runs on a computer",
               "It is a desktop app for {systems}, with a 3D view that needs a "
               "keyboard and a mouse or trackpad. Open this page on a computer, or send yourself "
               "the link."),
    "mac-intel": (":material-apple:", "This Mac needs Apple Silicon",
                  "The Mac version runs on M1 or later. This Mac seems to have an Intel "
                  "processor, so it cannot run it yet."),
}


def _file_name(platform: tuple, version: str) -> str:
    return f"Mnemosyn-{version}-{platform[3]}"


def _get_panel(platform: tuple, version: str, base: str) -> str:
    key, icon, name, _suffix, _kind, needs = platform
    file = _file_name(platform, version)
    return (f'<div class="get" data-os="{key}" hidden markdown>\n\n{icon}\n{{ .get-icon }}\n\n'
            f"Mnemosyn for {name}\n{{ .get-name }}\n\nVersion {version}. {needs}\n"
            f"{{ .get-needs }}\n\n[:material-download: Download for {name}]({base}/{file})"
            f"{{ .md-button .md-button--primary }} <span class=\"get-file\">{file}</span>\n"
            f"{{ .get-action }}\n\nNot on {name}? [All downloads](#all-downloads) are listed "
            "below.\n{ .get-other }\n\n</div>")


def _elsewhere_panel(key: str, systems: str) -> str:
    icon, title, text = ELSEWHERE[key]
    text = text.replace("{systems}", systems)
    return (f'<div class="get get-elsewhere" data-os="{key}" hidden markdown>\n\n{icon}\n'
            f"{{ .get-icon }}\n\n{title}\n{{ .get-name }}\n\n{text}\n{{ .get-needs }}\n\n"
            "[All downloads](#all-downloads) are listed below.\n{ .get-other }\n\n</div>")


def _file_row(platform: tuple, version: str, base: str) -> str:
    key, icon, name, _suffix, kind, needs = platform
    if version:
        file = _file_name(platform, version)
        action = f"[:material-download: {kind}]({base}/{file}){{ .md-button }}"
        detail = f"{needs} <span class=\"file-name\">{file}</span>"
    else:
        action, detail = "Coming soon", needs
    return (f'<div class="file" data-os="{key}" markdown>\n\n{icon}\n{{ .file-icon }}\n\n'
            f"{name}\n{{ .file-system }}\n\n{detail}\n{{ .file-needs }}\n\n{action}\n"
            "{ .file-action }\n\n</div>")


def _tabs(parts: dict[str, str]) -> str:
    return "\n\n".join(f'=== "{name}"\n\n' + textwrap.indent(text, "    ")
                        for name, text in parts.items())


def _download_page(version: str, quickstart: str, mac: bool = False) -> str:
    base = f"{RELEASES}/download/v{version}"
    platforms = [p for p in PLATFORMS if mac or p[0] != "mac"]
    rows = "\n\n".join(_file_row(p, version, base) for p in platforms)
    panels = ""
    if version:
        found = [_get_panel(p, version, base) for p in platforms]
        names = [p[2] for p in platforms]
        systems = ", ".join(names[:-1]) + " and " + names[-1]
        found += [_elsewhere_panel(k, systems) for k in ELSEWHERE if mac or k != "mac-intel"]
        panels = "\n\n".join(found) + "\n\n"
        details = (f"Version {version}, a test version. Sizes and the `SHA256SUMS.txt` checksum "
                   f"file are on the [release page]({RELEASES}/tag/v{version}).")
    else:
        details = "The first test version is coming soon. When it is out, it will appear here."
    opening = _tabs({p[2]: OPENING[p[0]].replace("{version}", version) for p in platforms})
    checks = {"Windows": "```powershell\nGet-FileHash Mnemosyn-*-Setup.exe\n```",
              "Linux": "```bash\nsha256sum Mnemosyn-*\n```"}
    if mac:
        checks["Mac"] = "```bash\nshasum -a 256 Mnemosyn-*.dmg\n```"
    return f"""# Download

Free, for study, and it works without an internet connection.
{{ .lede }}

{panels}## All downloads

<div class="files" markdown>

{rows}

</div>

{details} The download contains the shareable atlas: the spinal cord, the glands and the brainstem bodies come
from sources that have not yet allowed sharing, so they are not included.
{{ .release-line }}

Every system needs graphics that support OpenGL 3.2, which almost every computer from the last ten
years has.
{{ .release-line }}

## Opening it the first time

{opening}

Your quiz progress is kept in your user folder, so it survives updates.

## Privacy

Mnemosyn does not connect to the internet and has no account, no tracking and no usage reports.
It keeps three things, all on your computer and only there: your quiz progress, your settings (such
as the window layout) and a log of errors, which you can attach if you report a problem. **Help**,
then **Open data folder** shows where they are. Mnemosyn does not look for updates by itself;
**Help**, then **Check for a newer version** opens this page in your browser.

## Check your download

To make sure a file arrived whole and unchanged, compare its checksum with `SHA256SUMS.txt` on the
release page.

{_tabs(checks)}

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
    for pattern in ("screenshot*.png", "teaser.mp4", "teaser-poster.jpg"):
        for shot in sorted((repo / "brand").glob(pattern)):
            shutil.copy(shot, out / "assets" / shot.name)
    (out / "atlas").mkdir()
    (out / "design").mkdir()
    structures = tomllib.loads((repo / "atlas_src/structures.toml").read_text())
    sources = _sources(tomllib.loads((repo / "atlas_src/recipe.toml").read_text()))
    local = {s["id"] for s in sources if s.get("local_only")}
    decisions = (repo / "docs/decisions.md").read_text()
    counts = {"structures": len(structures["concepts"]), "groups": len(structures["groups"]),
              "shared": len(sources) - len(local),
              "pathways": len(tomllib.loads((repo / "atlas_src/pathways.toml").read_text())
                              ["pathways"]),
              "decisions": len(re.findall(r"^\| \d+ \|", decisions, re.MULTILINE))}
    home = (out / "index.md").read_text()
    for key, value in counts.items():
        home = home.replace(f"@{key}@", str(value))
    (out / "index.md").write_text(home)
    review = tomllib.loads((out / "review.toml").read_text())
    (out / "review.toml").unlink()
    (out / "review.md").write_text(_review_page(review))
    (out / "reviewers.md").write_text(_reviewers_page(review))
    download = tomllib.loads((out / "download.toml").read_text())
    published = download.get("version", "")
    (out / "download.toml").unlink()
    from_source = (out / "build-from-source.md").read_text()
    (out / "build-from-source.md").unlink()
    (out / "download.md").write_text(_download_page(published, from_source,
                                                     download.get("mac", False)))
    (out / "atlas/structures.md").write_text(_structures_page(structures, local))
    (out / "atlas/sources.md").write_text(_sources_page(sources, local))
    dated = re.sub(r"^(\| \d+ \| )(\d{4}-\d\d-\d\d)( \|)", r'\1<span class="when">\2</span>\3',
                   decisions, flags=re.MULTILINE)
    (out / "decisions.md").write_text(dated.replace("](specs/", "](design/"))
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
