import shutil
from pathlib import Path

import numpy as np
import pytest

from cns_atlas import Atlas
from cns_atlas.knowledge import CITATION, load_references, parse_entry
from cns_atlas.model import Relay, Station
from cns_atlas.pathways import lights
from tools.build_atlas.hierarchy import build_tree, load_structures
from tools.build_atlas.pathways import check_pathway_texts, check_pathways, load_pathways
from tools.build_atlas.timelines import load_timelines
from tools.build_atlas.recipe import load_recipe
from tools.build_atlas.validate import (check_hierarchy, check_knowledge, check_sources,
                                        check_templates)

SRC = Path(__file__).resolve().parent.parent / "atlas_src"
AAL3_EMPTY_LABELS = {35, 36, 81, 82}
PATHWAY_KEYS = ["visual", "auditory", "papez", "motor", "touch", "pain", "basal-ganglia",
                "cerebellar", "dopamine", "serotonin", "noradrenaline", "acetylcholine", "fear",
                "stress", "body-clock", "hunger", "memory", "decision"]
BEHAVIOUR = ["dopamine", "serotonin", "noradrenaline", "acetylcholine", "fear", "stress",
             "body-clock", "hunger", "memory", "decision"]
REAL_ATLAS = SRC.parent / "atlases" / "cns"
OPEN_CENTRES = {2051: (-5.0, -35.0, -10.0), 2801: (-13.0, -41.0, -44.0),
                2901: (-14.0, -60.0, -34.0), 2040: (0.0, -30.0, -8.0)}


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
    assert {ref.source for r in raws for ref in r.labels} == {
        "aal3", "neudorfer2020", "hcp1065", "tang2024", "razavi2021", "edlow2023",
        "diedrichsen2009", "sitek2019", "bianciardi2024"}


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
    assert len(paths) == 25
    for path in paths:
        assert parse_entry(path.read_text(encoding="utf-8"), str(path)).citations, path


@pytest.mark.slow
def test_real_build(tmp_path):
    from tools.build_atlas.build import build

    src = shutil.copytree(SRC, tmp_path / "src")
    atlas = Atlas.open(build(src, tmp_path / "cns", log=lambda *_: None))
    assert [p.key for p in atlas.pathways] == PATHWAY_KEYS
    assert 2700 not in atlas and atlas.local_only == ()
    stress = {p.key: p for p in atlas.pathways}["stress"]
    assert stress.steps[2] == Relay("Pituitary gland")
    assert {p.key: p for p in atlas.pathways}["body-clock"].steps[3] == Relay("Pineal gland")
    geometry = [s for s in atlas.structures if atlas.has_mesh(s.id)]
    assert len(geometry) == 306
    routes = {p.key: p for p in atlas.pathways}
    assert Relay("Nucleus of the solitary tract") in routes["hunger"].steps
    assert Station((2800,)) in routes["auditory"].steps
    assert 2830 not in atlas and 2810 not in atlas
    labels = np.asarray(atlas.volumes[0].data)
    for structure_id, centre in OPEN_CENTRES.items():
        mean = np.asarray(atlas.mesh(structure_id).vertices).mean(axis=0)
        assert np.allclose(mean, centre, atol=6.0), (structure_id, mean)
        assert (labels == structure_id).any(), structure_id
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
    assert len(paths) == 18
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
            for step, ids in zip(pathway.steps, lights(atlas, pathway, side)):
                if isinstance(step, Station):
                    assert ids, (pathway.key, step, side)
            text = atlas.pathway_text(pathway.key, side)
            assert len(text.steps) == len(pathway.steps)
            words = [text.overview, *(t.role for t in text.steps),
                     *(t.lesion or t.disorders for t in text.steps)]
            assert all(word and "{" not in word for word in words), pathway.key
    assert set(atlas.timelines) == {"stress", "body-clock", "hunger"}
    for s in atlas.structures:
        if atlas.has_mesh(s.id):
            normals = np.asarray(atlas.mesh(s.id).normals, dtype=np.float32)
            assert (np.linalg.norm(normals, axis=1) > 0.5).all(), s.name


def test_the_glands_are_local_only_midline_structures():
    local = {s.source.id: s for s in load_recipe(SRC / "recipe.toml").sources if s.local_only}
    assert list(local) == ["tang2024", "razavi2021", "bianciardi2024"]
    for spec in (local["tang2024"], local["razavi2021"]):
        assert not spec.source.redistribution and spec.mesh_grid == "native"
        assert spec.priority == -1 and spec.volume == "brain"
    assert local["razavi2021"].mask and not local["tang2024"].mask
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert raws[2700].side == raws[2710].side == "midline"
    assert (raws[24].parent, raws[2700].parent, raws[2710].parent) == (20, 20, 24)
    assert raws[24].kind == "group"


@pytest.mark.slow
def test_a_local_build_adds_the_two_glands(tmp_path):
    from tools.build_atlas.build import build

    src = shutil.copytree(SRC, tmp_path / "src")
    atlas = Atlas.open(build(src, tmp_path / "cns", log=lambda *_: None, local=True))
    assert atlas.local_only == ("tang2024", "razavi2021", "bianciardi2024")
    assert len([s for s in atlas.structures if atlas.has_mesh(s.id)]) == 326
    hunger = {p.key: p for p in atlas.pathways}["hunger"]
    assert Station((2830,), fallback="Nucleus of the solitary tract") in hunger.steps
    labels = np.asarray(atlas.volumes[0].data)
    for structure_id, centre in ((2700, (0.0, 3.0, -32.0)), (2710, (0.0, -30.0, 4.0)),
                                 (2811, (-5.0, -37.0, -52.0))):
        mean = np.asarray(atlas.mesh(structure_id).vertices).mean(axis=0)
        assert np.allclose(mean, centre, atol=3.0), (structure_id, mean)
        assert (labels == structure_id).any(), structure_id


def test_behaviour_routes_and_timelines_are_valid():
    pathways = load_pathways(SRC / "pathways.toml")
    behaviour = [p for p in pathways if p.group == "Behaviour"]
    assert [p.key for p in behaviour] == BEHAVIOUR
    assert all(p.sides == "both" and p.texts == "behaviour" for p in behaviour)
    references = load_references(SRC / "knowledge" / "references.toml")
    timelines = load_timelines(SRC / "timelines", pathways, references)
    assert sorted(t.route for t in timelines) == ["body-clock", "hunger", "stress"]
    assert all(t.status == "draft" and t.note for t in timelines)


def test_the_stress_route_starts_at_the_amygdala_and_the_peduncles_cross():
    routes = {p.key: p for p in load_pathways(SRC / "pathways.toml")}
    assert [s.structures for s in routes["stress"].steps if isinstance(s, Station)] == [
        (1400,), (2510,), (2700,), (1350,), (1090, 1300)]
    cerebellar = routes["cerebellar"].steps
    assert cerebellar[3].crossing and cerebellar[6].crossing


NEW_NUCLEI = {2040: ("edlow2023", 31), 2050: ("sitek2019", 31), 2060: ("edlow2023", 31),
              2070: ("edlow2023", 31), 2080: ("bianciardi2024", 31),
              2090: ("bianciardi2024", 31), 2110: ("edlow2023", 32), 2120: ("edlow2023", 32),
              2130: ("edlow2023", 32), 2140: ("sitek2019", 32), 2150: ("bianciardi2024", 32),
              2230: ("bianciardi2024", 33), 2240: ("bianciardi2024", 33),
              2800: ("sitek2019", 34), 2810: ("bianciardi2024", 34),
              2820: ("bianciardi2024", 34), 2830: ("bianciardi2024", 34),
              2840: ("bianciardi2024", 34), 2850: ("bianciardi2024", 34),
              2900: ("diedrichsen2009", 43), 2910: ("diedrichsen2009", 43)}
NUCLEUS_STATIONS = {"auditory": Station((2800,)), "cerebellar": Station((2900,), "opposite"),
                    "acetylcholine": Station((2070, 2110)), "fear": Station((2040,)),
                    "hunger": Station((2830,), fallback="Nucleus of the solitary tract")}


def test_brainstem_nuclei_come_from_one_source_each():
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert (raws[34].parent, raws[43].parent) == (30, 40)
    assert raws[34].kind == raws[43].kind == "group"
    for structure_id, (source, parent) in NEW_NUCLEI.items():
        raw = raws[structure_id]
        assert raw.parent == parent and raw.kind == "nucleus", structure_id
        kids = [r for r in raws.values() if r.concept == structure_id] or [raw]
        assert {ref.source for r in kids for ref in r.labels} == {source}, structure_id
    assert {raws[i].side for i in (2040, 2230, 2240)} == {"midline"}


def test_the_new_sources_rank_below_the_old_and_mesh_natively():
    specs = {s.source.id: s for s in load_recipe(SRC / "recipe.toml").sources}
    new = ("edlow2023", "diedrichsen2009", "sitek2019", "bianciardi2024")
    assert max(specs[n].priority for n in new) < min(
        s.priority for n, s in specs.items() if n not in new)
    for name in new[:3]:
        spec = specs[name]
        assert spec.priority == -2 and spec.mesh_grid == "native", name
        assert spec.source.redistribution and not spec.local_only, name
    navigator = specs["bianciardi2024"]
    assert navigator.priority == -3 and navigator.mesh_grid == "native"
    assert navigator.local_only and navigator.manual and not navigator.source.redistribution
    assert specs["edlow2023"].manual and specs["sitek2019"].crop
    assert set(specs["diedrichsen2009"].drop) == set(range(1, 29)) | {33, 34}
    assert set(specs["sitek2019"].drop) == {7, 8}


def test_the_words_only_stations_now_name_their_nuclei():
    routes = {p.key: p for p in load_pathways(SRC / "pathways.toml")}
    stations = {key: [s for s in routes[key].steps if isinstance(s, Station)
                      and set(s.structures) & set(NEW_NUCLEI)] for key in NUCLEUS_STATIONS}
    for key, station in NUCLEUS_STATIONS.items():
        assert station in stations[key], key
    assert Station((2050,), "opposite") in stations["auditory"]
    gone = {"Cochlear nuclei", "Inferior colliculus", "Dentate nucleus", "Periaqueductal grey",
            "Pedunculopontine and laterodorsal tegmental nuclei", "Nucleus of the solitary tract"}
    assert not [s for p in routes.values() for s in p.steps
                if isinstance(s, Relay) and s.name in gone]


@pytest.mark.slow
def test_reading_the_auditory_atlas_stays_under_1_gb():
    import subprocess
    import sys

    from tools.build_atlas.fetch import DEFAULT_CACHE, fetch

    spec = next(s for s in load_recipe(SRC / "recipe.toml").sources if s.source.id == "sitek2019")
    path = fetch(spec, DEFAULT_CACHE)
    code = ("import sys; from tools.build_atlas.labels import load_label_image; "
            "load_label_image(sys.argv[1], name='sitek2019', cropped=True); "
            "print(open('/proc/self/status').read().split('VmHWM:')[1].split()[0])")
    run = subprocess.run([sys.executable, "-c", code, str(path)], check=True, cwd=SRC.parent,
                         capture_output=True, text=True)
    assert int(run.stdout.split()[-1]) < 1024 * 1024
