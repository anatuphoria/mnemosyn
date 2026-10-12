import shutil
from pathlib import Path

import numpy as np
import pytest

from cns_atlas import Atlas
from cns_atlas.knowledge import CITATION, load_references, parse_entry
from cns_atlas.model import Station
from cns_atlas.pathways import resolve
from tools.build_atlas.hierarchy import build_tree, load_structures
from tools.build_atlas.pathways import check_pathway_texts, check_pathways, load_pathways
from tools.build_atlas.recipe import load_recipe
from tools.build_atlas.validate import (check_hierarchy, check_knowledge, check_sources,
                                        check_templates)

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
AAL3_EMPTY_LABELS = {35, 36, 81, 82}
PATHWAY_KEYS = ["visual", "auditory", "papez", "motor", "touch", "pain", "basal-ganglia",
                "cerebellar"]
REAL_ATLAS = SRC.parent / "atlases" / "cns"


def test_hierarchy_sources_and_knowledge_are_valid():
    raws = load_structures(SRC / "structures.toml")
    recipe = load_recipe(SRC / "recipe.toml")
    references = load_references(SRC / "knowledge" / "references.toml")
    assert check_hierarchy(raws) == []
    assert check_sources(raws, recipe, SRC) == []
    concepts = {r.id: r.concept for r in raws}
    keys = {f"pathway-{p.key}" for p in load_pathways(SRC / "pathways.toml")}
    assert check_knowledge(SRC / "knowledge", references, concepts, keys) == []


def test_every_aal3_label_maps_to_exactly_one_structure():
    raws = load_structures(SRC / "structures.toml")
    values = [ref.value for r in raws for ref in r.labels if ref.source == "aal3"]
    assert sorted(values) == sorted(set(range(1, 171)) - AAL3_EMPTY_LABELS)
    assert {ref.source for r in raws for ref in r.labels} == {"aal3", "neudorfer2020", "hcp1065"}


NEUDORFER_LABELS = set(range(1, 11)) | set(range(13, 39)) | set(range(41, 55))


def test_every_hypothalamus_label_is_mapped_or_dropped():
    raws = load_structures(SRC / "structures.toml")
    spec = next(s for s in load_recipe(SRC / "recipe.toml").sources
                if s.source.id == "neudorfer2020")
    mapped = [ref.value for r in raws for ref in r.labels if ref.source == "neudorfer2020"]
    assert len(mapped) == len(set(mapped)) == 42
    assert set(mapped) | set(spec.drop) == NEUDORFER_LABELS
    assert not set(mapped) & set(spec.drop)
    assert spec.priority == 0 and spec.mesh_grid == "native"


def test_every_tract_file_is_mapped_or_dropped():
    raws = load_structures(SRC / "structures.toml")
    tracts = load_recipe(SRC / "recipe.toml").tracts[0]
    mapped = [ref.value for r in raws for ref in r.labels if ref.source == "hcp1065"]
    assert len(tracts.names) == 80 and len(mapped) == len(set(mapped)) == 77
    assert set(mapped) | set(tracts.drop) == set(tracts.names)


def test_new_regions_have_the_planned_concepts():
    raws = load_structures(SRC / "structures.toml")
    tracts = [r for r in raws if r.kind == "tract" and r.concept is None]
    assert len(tracts) == 43
    from_neudorfer = {r.concept or r.id for r in raws if "neudorfer2020" in r.sources}
    assert len(from_neudorfer) == 21
    assert all(2500 <= i < 2700 or 3000 <= i < 3500 for i in from_neudorfer)


def test_acronyms_are_unique():
    raws = load_structures(SRC / "structures.toml")
    acronyms = [r.acronym for r in raws]
    assert len(acronyms) == len(set(acronyms))


def test_every_description_cites_a_reference():
    paths = sorted((SRC / "knowledge").glob("*/*.md"))
    assert len(paths) == 13
    for path in paths:
        assert parse_entry(path.read_text(encoding="utf-8"), str(path)).citations, path


@pytest.mark.slow
def test_real_build(tmp_path):
    from tools.build_atlas.build import build

    src = shutil.copytree(SRC, tmp_path / "src")
    atlas = Atlas.open(build(src, tmp_path / "cns", log=lambda *_: None))
    assert [p.key for p in atlas.pathways] == PATHWAY_KEYS
    geometry = [s for s in atlas.structures if atlas.has_mesh(s.id)]
    assert len(geometry) == 285
    assert atlas.tracts is not None and len(atlas.tracts.ids) == 77
    assert atlas.get(3001).xrefs == {"hcp1065": "Cortico_Spinal_Tract_L"}
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


def test_pathways_light_shapes_on_both_sides_and_match_their_texts():
    pathways = load_pathways(SRC / "pathways.toml")
    assert [p.key for p in pathways] == PATHWAY_KEYS
    planned = build_tree(load_structures(SRC / "structures.toml"))
    shaped = {p.structure.id for p in planned if p.labels}
    assert check_pathways(pathways, [p.structure for p in planned], shaped) == []
    assert check_pathway_texts(SRC / "knowledge", pathways) == []


def test_pathway_texts_are_drafts_citing_a_reference_in_every_section():
    paths = sorted((SRC / "knowledge" / "en").glob("pathway-*.md"))
    assert len(paths) == 8
    for path in paths:
        entry = parse_entry(path.read_text(encoding="utf-8"), str(path))
        assert entry.status == "draft", path
        for name, body in entry.sections.items():
            assert CITATION.search(body), f"{path}: {name}"


@pytest.mark.slow
def test_the_built_atlas_pathways_light_and_read_on_both_sides():
    if not (REAL_ATLAS / "pathways.json").exists():
        pytest.skip("real atlas not built; run python -m tools.build_atlas")
    atlas = Atlas.open(REAL_ATLAS)
    assert [p.key for p in atlas.pathways] == PATHWAY_KEYS
    for pathway in atlas.pathways:
        for side in ("left", "right"):
            for step in pathway.steps:
                if isinstance(step, Station):
                    assert resolve(atlas, step, side), (pathway.key, step, side)
            text = atlas.pathway_text(pathway.key, side)
            assert len(text.steps) == len(pathway.steps)
            words = [text.overview, *(t.role for t in text.steps), *(t.lesion for t in text.steps)]
            assert all(word and "{" not in word for word in words), pathway.key
