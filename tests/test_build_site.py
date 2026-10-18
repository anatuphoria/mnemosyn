import re
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
    assert (tmp_path / "install.md").read_text().startswith("# Install")
    assert (tmp_path / "stylesheets/extra.css").exists()


def test_site_marks_local_only_sources(tmp_path):
    build_site(REPO, tmp_path)
    recipe = tomllib.loads((REPO / "atlas_src/recipe.toml").read_text())
    sources = recipe["sources"] + recipe.get("tracts", []) + recipe.get("templates", [])
    local = [s for s in sources if s.get("local_only")]
    page = (tmp_path / "atlas/sources.md").read_text()
    assert page.count("Local builds only") == len(local)
