import json
import re
import shutil
import tomllib
from pathlib import Path

from tools.build_site import build_site

REPO = Path(__file__).resolve().parent.parent


def test_site_pages_come_from_the_repo(tmp_path):
    build_site(REPO, tmp_path)
    structures = tomllib.loads((REPO / "atlas_src/structures.toml").read_text())
    recipe = tomllib.loads((REPO / "atlas_src/recipe.toml").read_text())
    sources = recipe["sources"] + recipe.get("tracts", []) + recipe.get("templates", [])
    page = (tmp_path / "atlas/structures.md").read_text()
    assert all(f"| {c['name']} | {c['acronym']} |" in page for c in structures["concepts"])
    page = (tmp_path / "atlas/sources.md").read_text()
    assert all(f"{{ #{s['id']} }}" in page for s in sources)
    home = (tmp_path / "index.md").read_text()
    assert f"<span>{len(structures['concepts'])}</span>structures" in home
    assert "@" not in re.sub(r"\S+@\S+", "", home)
    decisions = (tmp_path / "decisions.md").read_text()
    assert "](specs/" not in decisions and "](design/" in decisions
    design = (tmp_path / "design/index.md").read_text()
    assert all(spec.name in design for spec in (REPO / "docs/specs").glob("*.md"))
    assert (tmp_path / "download.md").read_text().startswith("# Download")
    assert not (tmp_path / "install.md").exists()
    assert (tmp_path / "stylesheets/extra.css").exists()


def test_site_marks_local_only_sources(tmp_path):
    build_site(REPO, tmp_path)
    recipe = tomllib.loads((REPO / "atlas_src/recipe.toml").read_text())
    sources = recipe["sources"] + recipe.get("tracts", []) + recipe.get("templates", [])
    local = [s for s in sources if s.get("local_only")]
    page = (tmp_path / "atlas/sources.md").read_text()
    assert page.count("Local builds only") == len(local)


def test_readme_code_spans_stay_on_one_line():
    in_code = False
    for number, line in enumerate((REPO / "README.md").read_text().splitlines(), 1):
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code:
            assert line.count("`") % 2 == 0, f"README.md:{number}: {line}"


def review_settings(tmp_path, **changes):
    repo = tmp_path / "repo"
    skipped = (".git", ".venv", "atlases", "build", "dist", "review", "*.pyc", "__pycache__")
    shutil.copytree(REPO, repo, ignore=shutil.ignore_patterns(*skipped))
    settings = tomllib.loads((repo / "site/review.toml").read_text())
    settings.update(changes)
    lines = [f"{key} = {json.dumps(value)}" for key, value in settings.items()
             if not isinstance(value, list)]
    for key in ("editions", "reviewers"):
        for row in settings.get(key, []):
            lines += [f"\n[[{key}]]"] + [f"{k} = {json.dumps(v)}" for k, v in row.items()]
    (repo / "site/review.toml").write_text("\n".join(lines) + "\n")
    return repo


def test_the_review_page_offers_the_booklet_and_the_steps(tmp_path):
    build_site(REPO, tmp_path / "out")
    page = (tmp_path / "out/review.md").read_text()
    settings = tomllib.loads((REPO / "site/review.toml").read_text())
    latest = settings["editions"][0]
    assert (REPO / "site" / latest["file"]).exists() and f"]({latest['file']})" in page
    assert all(f"edition {e['edition']}" in page.lower() for e in settings["editions"])
    assert "answer form link is never published" in page
    assert settings["contact"] in page and "delet" in page.lower()


def test_the_request_form_is_embedded_once_its_link_is_set(tmp_path):
    url = "https://docs.google.com/forms/d/e/abc/viewform"
    build_site(review_settings(tmp_path, request_form=url), tmp_path / "out")
    page = (tmp_path / "out/review.md").read_text()
    assert f'src="{url}?embedded=true"' in page and "open soon" not in page


def test_without_a_form_link_requests_open_soon_by_email(tmp_path):
    build_site(review_settings(tmp_path, request_form=""), tmp_path / "out")
    page = (tmp_path / "out/review.md").read_text()
    assert "open soon" in page and "<iframe" not in page


def test_reviewers_are_listed_only_from_the_credit_list(tmp_path):
    build_site(review_settings(tmp_path, reviewers=[]), tmp_path / "out")
    assert "first reviews" in (tmp_path / "out/reviewers.md").read_text()
    people = [{"name": "Dr A. Name", "institution": "Some University"}, {"name": "B. Other"}]
    build_site(review_settings(tmp_path / "b", reviewers=people), tmp_path / "out2")
    page = (tmp_path / "out2/reviewers.md").read_text()
    assert "Dr A. Name, Some University" in page and "- B. Other\n" in page


def test_the_home_page_invites_specialists_without_changing_its_layout(tmp_path):
    build_site(REPO, tmp_path / "out")
    home = (tmp_path / "out/index.md").read_text()
    assert "Help us review it](review.md)" in home
    assert home.count('<div class="start" markdown>') == 1
    assert home.count("](download.md)") == 2 and "](guide.md)" in home
    assert "install.md" not in home and "[Download](download.md)" in home


def test_the_review_pages_are_in_the_navigation():
    nav = (REPO / "mkdocs.yml").read_text()
    assert "review.md" in nav and "reviewers.md" in nav
    assert "Download: download.md" in nav and "install.md" not in nav


def download_settings(tmp_path, released):
    repo = review_settings(tmp_path)
    (repo / "site/download.toml").write_text(f"released = {str(released).lower()}\n")
    return repo


def test_the_download_page_links_this_versions_files(tmp_path):
    build_site(download_settings(tmp_path, True), tmp_path / "out")
    page = (tmp_path / "out/download.md").read_text()
    base = "https://github.com/anatuphoria/mnemosyn/releases/download/v0.1.0/"
    assert f"]({base}Mnemosyn-0.1.0-Setup.exe)" in page
    assert f"]({base}Mnemosyn-0.1.0-x86_64.AppImage)" in page
    assert "releases/tag/v0.1.0" in page and "SHA256SUMS.txt" in page
    assert "Windows 10" in page and "OpenGL 3.2" in page
    assert "Run anyway" in page and "chmod +x" in page
    assert "shareable" in page.lower() and "test version" in page.lower()
    assert "## Build from source" in page and "pip install" in page


def test_before_the_first_release_the_buttons_say_coming_soon(tmp_path):
    build_site(download_settings(tmp_path, False), tmp_path / "out")
    page = (tmp_path / "out/download.md").read_text()
    assert "coming soon" in page.lower() and "releases/download" not in page
    assert "## Build from source" in page
