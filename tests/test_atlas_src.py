import shutil
from pathlib import Path

import numpy as np
import pytest

from cns_atlas import Atlas
from cns_atlas.knowledge import load_references, parse_entry
from tools.build_atlas.hierarchy import build_tree, load_structures
from tools.build_atlas.recipe import load_recipe
from tools.build_atlas.validate import (check_hierarchy, check_knowledge, check_sources,
                                        check_templates)

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
AAL3_EMPTY_LABELS = {35, 36, 81, 82}


def test_hierarchy_sources_and_knowledge_are_valid():
    raws = load_structures(SRC / "structures.toml")
    recipe = load_recipe(SRC / "recipe.toml")
    references = load_references(SRC / "knowledge" / "references.toml")
    assert check_hierarchy(raws) == []
    assert check_sources(raws, recipe, SRC) == []
    concepts = {r.id: r.concept for r in raws}
    assert check_knowledge(SRC / "knowledge", references, concepts, set()) == []


def test_every_aal3_label_maps_to_exactly_one_structure():
    raws = load_structures(SRC / "structures.toml")
    values = [ref.value for r in raws for ref in r.labels]
    assert sorted(values) == sorted(set(range(1, 171)) - AAL3_EMPTY_LABELS)
    assert {ref.source for r in raws for ref in r.labels} == {"aal3"}


def test_acronyms_are_unique():
    raws = load_structures(SRC / "structures.toml")
    acronyms = [r.acronym for r in raws]
    assert len(acronyms) == len(set(acronyms))


def test_every_description_cites_a_reference():
    paths = sorted((SRC / "knowledge").glob("*/*.md"))
    assert len(paths) == 5
    for path in paths:
        assert parse_entry(path.read_text(encoding="utf-8"), str(path)).citations, path


@pytest.mark.slow
def test_real_build(tmp_path):
    from tools.build_atlas.build import build

    src = shutil.copytree(SRC, tmp_path / "src")
    atlas = Atlas.open(build(src, tmp_path / "cns", log=lambda *_: None))
    geometry = [s for s in atlas.structures if atlas.has_mesh(s.id)]
    assert len(geometry) == 166
    assert atlas.get(1351).xrefs == {"aal3": "Hippocampus_L"}
    assert atlas.get(2200).xrefs == {"aal3": "Raphe_D"}
    for s in geometry:
        x = float(np.asarray(atlas.mesh(s.id).vertices)[:, 0].mean())
        if s.side == "left":
            assert x < 0, s.name
        if s.side == "right":
            assert x > 0, s.name
    template = atlas.template
    assert template is not None and template.shape == atlas.volumes[0].shape
    labelled = np.asarray(atlas.volumes[0].data) > 0
    intensity = np.asarray(template.data, dtype=float)
    assert intensity[labelled].mean() > 2 * intensity[~labelled].mean()


def test_frontal_concepts_have_distinct_shades_and_sides_match():
    planned = {p.structure.id: p.structure for p in build_tree(load_structures(SRC / "structures.toml"))}
    frontal = [s for s in planned.values() if s.parent == 13]
    assert len({s.rgb_triplet for s in frontal}) == len(frontal) == 16
    for s in frontal:
        assert planned[s.id + 1].rgb_triplet == planned[s.id + 2].rgb_triplet == s.rgb_triplet


def test_colin27_template_is_declared_and_valid():
    recipe = load_recipe(SRC / "recipe.toml")
    assert [t.source.id for t in recipe.templates] == ["colin27"]
    assert check_templates(recipe, SRC) == []
