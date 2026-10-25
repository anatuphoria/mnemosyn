import itertools
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from cns_atlas import Atlas
from cns_atlas.knowledge import CITATION, load_references, parse_entry
from cns_atlas.model import Relay, Station
from cns_atlas.pathways import lights
from tools.build_atlas.cells import check_cell_sources, check_cell_texts, load_cell_sources
from tools.build_atlas.colours import NEAR_MM, delta_e
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
    keys |= {f"cells-{v['key']}" for v in load_cell_sources(SRC / "cells")}
    assert check_knowledge(SRC / "knowledge", references, concepts, keys) == []


def test_every_aal3_label_maps_to_exactly_one_structure():
    raws = load_structures(SRC / "structures.toml")
    values = [ref.value for r in raws for ref in r.labels if ref.source == "aal3"]
    assert sorted(values) == sorted(set(range(1, 171)) - AAL3_EMPTY_LABELS)
    assert {ref.source for r in raws for ref in r.labels} == {
        "aal3", "neudorfer2020", "hcp1065", "tang2024", "razavi2021", "edlow2023",
        "diedrichsen2009", "sitek2019", "bianciardi2024", "iglesias2015", "pam50", "pam50-atlas",
        "pam50-gm"}


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
    spinal = [r for r in tracts if 5500 <= r.id < 5700]
    assert len(tracts) - len(spinal) == 43 and len(spinal) == 15
    from_neudorfer = {r.concept or r.id for r in raws if "neudorfer2020" in r.sources}
    assert len(from_neudorfer) == 21
    assert all(2500 <= i < 2700 or 3000 <= i < 3500 for i in from_neudorfer)


def test_acronyms_are_unique():
    raws = load_structures(SRC / "structures.toml")
    acronyms = [r.acronym for r in raws]
    assert len(acronyms) == len(set(acronyms))


def test_every_description_cites_a_reference():
    paths = sorted((SRC / "knowledge").glob("*/*.md"))
    assert len(paths) == 26
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
    assert [v.name for v in atlas.volumes] == ["brain"]
    assert Relay("Dorsal horn") in {p.key: p for p in atlas.pathways}["pain"].steps
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
    assert [t.source.id for t in recipe.templates] == ["colin27", "pam50-t2"]
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
    assert list(local) == ["tang2024", "razavi2021", "bianciardi2024", "iglesias2015", "pam50",
                           "pam50-atlas", "pam50-gm", "pam50-cord"]
    for spec in (local["tang2024"], local["razavi2021"]):
        assert not spec.source.redistribution and spec.mesh_grid == "native"
        assert spec.priority == -1 and spec.volume == "brain"
    assert local["razavi2021"].mask and not local["tang2024"].mask
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert raws[2700].side == raws[2710].side == "midline"
    assert (raws[24].parent, raws[2700].parent, raws[2710].parent) == (20, 20, 24)
    assert raws[24].kind == "group"


def touching_concepts(voxels, ids, minimum=50):
    counts = {}
    for axis in range(3):
        moved = np.moveaxis(voxels, axis, 0)
        a, b = moved[:-1].ravel(), moved[1:].ravel()
        keep = (a != b) & np.isin(a, ids) & np.isin(b, ids)
        for p, q in zip(a[keep] // 10 * 10, b[keep] // 10 * 10):
            if p != q:
                key = (min(p, q), max(p, q))
                counts[key] = counts.get(key, 0) + 1
    return [key for key, n in counts.items() if n >= minimum]


@pytest.mark.slow
def test_a_local_build_adds_the_two_glands(tmp_path):
    from tools.build_atlas.build import build

    src = shutil.copytree(SRC, tmp_path / "src")
    atlas = Atlas.open(build(src, tmp_path / "cns", log=lambda *_: None, local=True))
    assert atlas.local_only == ("tang2024", "razavi2021", "bianciardi2024", "iglesias2015",
                                "pam50", "pam50-atlas", "pam50-gm", "pam50-cord", "pam50-t2")
    assert len([s for s in atlas.structures if atlas.has_mesh(s.id)]) == 395
    for structure_id, centre in ((2250, (0.0, -23.0, -13.0)), (2260, (0.0, -28.0, -33.0)),
                                 (2270, (0.0, -41.0, -55.0))):
        assert atlas.get(structure_id).kind == "shell"
        mean = np.asarray(atlas.mesh(structure_id).vertices).mean(axis=0)
        assert np.allclose(mean, centre, atol=4.0), (structure_id, mean)
    spine = next(v for v in atlas.volumes if v.name == "spine")
    assert nib.aff2axcodes(spine.affine) == ("R", "A", "S")
    assert 55 <= spine.shape[0] <= 75 and 950 <= spine.shape[2] <= 991
    assert "spine" in atlas.templates and atlas.fills["spine"].shape == spine.shape
    fill = np.asarray(atlas.fills["spine"].data)
    assert all((fill == 5000 + 10 * n).sum() >= 40 for n in range(1, 31))
    assert (fill == 5010).sum() == 4105
    for structure_id, z in ((5010, -73.0), (5300, -540.0)):
        mean = np.asarray(atlas.mesh(structure_id).vertices).mean(axis=0)
        assert abs(mean[2] - z) < 4.0, (structure_id, mean)
    for s in atlas.structures:
        if s.side == "left" and atlas.has_mesh(s.id) and s.id >= 5000:
            assert np.asarray(atlas.mesh(s.id).vertices)[:, 0].mean() < 0, s.name
    z = {i: np.asarray(atlas.mesh(i).vertices)[:, 2] for i in range(5010, 5310, 10)}
    assert all(atlas.get(i).kind == "cover" for i in z)
    assert all(abs(z[i].min() - z[i + 10].max()) < 1e-3 for i in range(5010, 5300, 10))
    for s in atlas.structures:
        if s.id >= 5400 and atlas.has_mesh(s.id):
            assert np.asarray(atlas.mesh(s.id).vertices)[:, 2].max() < z[5010].max() + 1.0, s.name
    voxels = np.asarray(spine.data)
    for concept in range(5500, 5650, 10):
        assert atlas.has_mesh(concept + 1) and atlas.has_mesh(concept + 2), concept
        left, right = (voxels == concept + 1).sum(), (voxels == concept + 2).sum()
        assert abs(int(left) - int(right)) <= 0.05 * max(left, right), (concept, left, right)
    import pyvista as pv
    from vtkmodules.vtkFiltersCore import vtkImplicitPolyDataDistance

    cord = pv.merge([pv.PolyData(np.asarray(atlas.mesh(i).vertices, dtype=float),
                                 np.c_[np.full(len(atlas.mesh(i).faces), 3),
                                       atlas.mesh(i).faces].ravel()) for i in z]).clean()
    distance = vtkImplicitPolyDataDistance()
    distance.SetInput(cord)
    for s in atlas.structures:
        if 5400 <= s.id < 5430 and atlas.has_mesh(s.id):
            points = np.asarray(atlas.mesh(s.id).vertices, dtype=float)[::7]
            assert max(distance.EvaluateFunction(*p) for p in points) < 0.1, s.name
    tract_ids = [s.id for s in atlas.structures if 5500 <= s.id < 5660]
    for a, b in touching_concepts(voxels, tract_ids):
        assert delta_e(atlas.get(a).rgb_triplet, atlas.get(b).rgb_triplet) >= 20, (a, b)
    members = [s for s in atlas.structures if 30 in s.structure_id_path[:-1]
               and s.kind not in ("group", "shell") and s.concept is None]
    centres = {}
    for s in members:
        own = [s.id] + [t.id for t in atlas.structures if t.concept == s.id]
        points = [np.asarray(atlas.mesh(i).vertices).mean(axis=0) for i in own if atlas.has_mesh(i)]
        if points:
            centres[s.id] = np.array(points)
    near = [(a, b) for a, b in itertools.combinations(sorted(centres), 2)
            if np.linalg.norm(centres[a][:, None] - centres[b][None], axis=-1).min() < NEAR_MM]
    assert all(delta_e(atlas.get(a).rgb_triplet, atlas.get(b).rgb_triplet) >= 15
               for a, b in near), near
    routes = {p.key: p for p in atlas.pathways}
    for key, station in SPINAL_STATIONS.items():
        assert station in routes[key].steps, key
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
        s.priority for n, s in specs.items() if n not in (*new, "iglesias2015"))
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


SPINAL_STATIONS = {
    "motor": Station((5520,), "opposite", fallback="Lateral corticospinal tract in the spinal cord"),
    "touch": Station((5500, 5510), fallback="Dorsal column and gracile and cuneate nuclei"),
    "pain": Station((5420,), fallback="Dorsal horn")}


def test_the_spinal_cord_is_local_only_on_its_own_volume():
    recipe = load_recipe(SRC / "recipe.toml")
    spine = next(v for v in recipe.volumes if v.name == "spine")
    assert (spine.space, spine.grid_source) == ("PAM50", "pam50")
    specs = {s.source.id: s for s in (*recipe.sources, *recipe.templates)}
    for name in ("pam50", "pam50-atlas", "pam50-gm", "pam50-cord", "pam50-t2"):
        assert specs[name].local_only and specs[name].volume == "spine", name
    assert specs["pam50"].crop and specs["pam50"].margin == 10.0 and specs["pam50"].fill
    tracts, grey, cord = specs["pam50-atlas"], specs["pam50-gm"], specs["pam50-cord"]
    assert tracts.tiles == 0.5 and tracts.within == "pam50" and tracts.threshold is None
    assert not tracts.separate and tracts.mesh_grid == "native"
    assert sorted(n for n, _ in tracts.members) == [f"A{i:02d}" for i in range(30)]
    assert grey.threshold == 0.3 and grey.separate and grey.within == "pam50"
    assert grey.priority == 2 and grey.mesh_grid == "native" and grey.inside == "pam50-cord"
    assert sorted(n for n, _ in grey.members) == [f"A{i:02d}" for i in range(30, 36)]
    assert cord.outline_of == "pam50" and cord.member.endswith("template/PAM50_cord.nii.gz")
    assert (cord.download, cord.sha256) == (specs["pam50"].download, specs["pam50"].sha256)
    assert cord.crop and cord.margin == 10.0 and cord.mesh_grid == "native"


def test_the_spinal_tree_has_30_segments_6_horns_and_30_tracts():
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert raws[3].parent == 1 and raws[80].parent == 3
    segments = [r for r in raws.values() if r.labels and r.labels[0].source == "pam50"]
    assert [r.acronym for r in segments] == (
        [f"C{i}" for i in range(1, 9)] + [f"T{i}" for i in range(1, 13)]
        + [f"L{i}" for i in range(1, 6)] + [f"S{i}" for i in range(1, 6)])
    assert all(r.kind == "cover" for r in segments)
    tracts = [r for r in raws.values() if r.labels and r.labels[0].source == "pam50-atlas"]
    grey = [r for r in raws.values() if r.labels and r.labels[0].source == "pam50-gm"]
    assert len(grey) == 6 and all(r.kind == "nucleus" for r in grey)
    assert len(tracts) == 30 and all(r.kind == "tract" for r in tracts)
    atlas_kids = tracts + grey
    assert all(r.labels[0].value == f"A{int(r.labels[0].value[1:]):02d}" for r in atlas_kids)
    assert all(int(r.labels[0].value[1:]) % 2 == (r.side == "right") for r in atlas_kids)


def test_the_spinal_stations_are_drawn_with_their_old_names():
    routes = {p.key: p for p in load_pathways(SRC / "pathways.toml")}
    for key, station in SPINAL_STATIONS.items():
        assert station in routes[key].steps, key


def test_brain_tracts_sit_inside_brain():
    raws = load_structures(SRC / "structures.toml")
    by_id = {r.id: r for r in raws}
    assert by_id[70].parent == 2
    paths = {p.structure.id: p.structure.structure_id_path for p in build_tree(raws)}
    tracts = [r.id for r in raws if r.kind == "tract" and 3000 <= r.id < 3500]
    assert tracts and all(2 in paths[i] for i in tracts)


PROVIDES = {"aal3": "Brain regions", "colin27": "MRI template for brain slices",
            "neudorfer2020": "Hypothalamic nuclei", "hcp1065": "Brain white matter tracts",
            "tang2024": "Pituitary gland", "razavi2021": "Pineal gland",
            "edlow2023": "Brainstem arousal nuclei", "diedrichsen2009": "Deep cerebellar nuclei",
            "sitek2019": "Auditory brainstem nuclei", "bianciardi2024": "Brainstem nuclei",
            "pam50": "Spinal cord segments", "pam50-atlas": "Spinal tracts",
            "pam50-gm": "Spinal grey matter", "pam50-cord": "Spinal cord surface",
            "pam50-t2": "MRI template for spinal cord slices",
            "iglesias2015": "Brainstem body"}


def test_every_source_says_what_it_provides():
    recipe = load_recipe(SRC / "recipe.toml")
    specs = (*recipe.sources, *recipe.templates, *recipe.tracts)
    assert {s.source.id: s.source.provides for s in specs} == PROVIDES


def test_the_brainstem_bodies_are_local_shells():
    sources = load_recipe(SRC / "recipe.toml").sources
    spec = next(s for s in sources if s.source.id == "iglesias2015")
    assert spec.local_only and not spec.source.redistribution and spec.volume == "brain"
    assert spec.parts == (1, 2, 4) and spec.threshold == 0.5 and spec.trim_outside == 30
    assert spec.mesh_grid == "native"
    others = [s.priority for s in sources if s.volume == "brain" and s is not spec]
    assert spec.priority < min(others)
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    bodies = {2250: (31, 4, "Midbrain body"), 2260: (32, 2, "Pons body"),
              2270: (34, 1, "Medulla body")}
    for structure_id, (parent, value, name) in bodies.items():
        r = raws[structure_id]
        assert (r.parent, r.kind, r.side, r.name) == (parent, "shell", "midline", name)
        assert [(ref.source, ref.value) for ref in r.labels] == [("iglesias2015", value)]


ASCENDING = {5500, 5510, 5530, 5560, 5570}
DESCENDING = {5520, 5540, 5550, 5580, 5590, 5600, 5610, 5620, 5630, 5640}


def test_spinal_tracts_are_blue_going_up_and_red_going_down():
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert {i for i, r in raws.items() if r.parent == 80} == ASCENDING | DESCENDING
    for structure_id in ASCENDING:
        red, green, blue = raws[structure_id].color
        assert blue > max(red, green), raws[structure_id].name
    for structure_id in DESCENDING:
        red, green, blue = raws[structure_id].color
        assert red > max(green, blue), raws[structure_id].name
    assert len({raws[i].color for i in ASCENDING | DESCENDING}) == 15


def test_segment_regions_alternate_and_crowded_groups_get_distinct_colours():
    raws = {r.id: r for r in load_structures(SRC / "structures.toml")}
    assert all(raws[g].palette == "alternate" and raws[g].color for g in (5, 6, 7, 8))
    assert len({raws[g].color for g in (5, 6, 7, 8)}) == 4
    assert all(raws[g].palette == "distinct" for g in (21, 22, 30, 43))


def test_hippocampus_cell_view_is_complete():
    raw = load_cell_sources(SRC / "cells")
    assert [v["key"] for v in raw] == ["hippocampus"]
    assert check_cell_sources(raw, {r.id for r in load_structures(SRC / "structures.toml")}) == []
    assert check_cell_texts(SRC / "knowledge", raw) == []
    view = raw[0]
    assert view["structures"] == [1350]
    assert {c["key"] for c in view["cells"]} == {"granule", "ca3-pyramidal", "ca1-pyramidal",
                                                 "basket", "olm", "hipp"}
    assert len(view["levels"]["basic"]["steps"]) == 4
    assert len(view["levels"]["full"]["steps"]) == 8
    assert all(r["download"].startswith("https://neuromorpho.org/") for c in view["cells"]
               for r in c["reconstructions"])
    basket = next(c for c in view["cells"] if c["key"] == "basket")
    assert len(basket["placements"]) == 2
