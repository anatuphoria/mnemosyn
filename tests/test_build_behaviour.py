from dataclasses import replace

import pytest

from atlas_fixtures import (TOY_BEHAVIOUR_PATHWAYS, TOY_BEHAVIOUR_TEXTS, TOY_PATHWAY_TEXTS,
                            TOY_PATHWAYS, TOY_STRUCTURES, TOY_TIMELINE,
                            write_extended_source_tree)
from cns_atlas import Atlas, Relay, Station
from tools.build_atlas.build import build
from tools.build_atlas.hierarchy import build_tree, load_structures
from tools.build_atlas.pathways import (check_pathway_texts, check_pathways, for_package,
                                        load_pathways)
from tools.build_atlas.recipe import BuildError
from tools.build_atlas.timelines import load_timelines

HEAD = '[[pathways]]\nkey = "p"\nname = "N"\nstart = "s"\ngroup = "G"\n'
REFS = {"ref2020": None}


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


def routes(tmp_path):
    return load_pathways(write(tmp_path, "pathways.toml", TOY_PATHWAYS + TOY_BEHAVIOUR_PATHWAYS))


def test_routes_read_group_sides_and_texts(tmp_path):
    loop, _short, mood = routes(tmp_path)
    assert (loop.group, loop.sides, loop.texts) == ("Sensory and motor", "one", "lesion")
    assert (mood.group, mood.sides, mood.texts) == ("Behaviour", "both", "behaviour")


@pytest.mark.parametrize(("body", "message"), [
    ('[[pathways]]\nkey = "p"\nname = "N"\nstart = "s"\nsteps = [{ cross = "X" }]\n',
     "pathway p: needs a group"),
    (HEAD + 'sides = "three"\nsteps = [{ cross = "X" }]\n', "pathway p: unknown sides 'three'"),
    (HEAD + 'texts = "poems"\nsteps = [{ cross = "X" }]\n', "pathway p: unknown texts 'poems'"),
    (HEAD + 'sides = "both"\nsteps = [{ structures = [100], side = "opposite" }]\n',
     "pathway p step 1: a both-sides route takes no side"),
])
def test_route_kind_errors(tmp_path, body, message):
    with pytest.raises(BuildError) as error:
        load_pathways(write(tmp_path, "pathways.toml", body))
    assert message in error.value.problems


def text_tree(tmp_path, files):
    folder = tmp_path / "knowledge" / "en"
    folder.mkdir(parents=True)
    for key, text in files.items():
        (folder / f"{key}.md").write_text(text)
    return tmp_path / "knowledge"


def test_behaviour_texts_match_their_style(tmp_path):
    knowledge = text_tree(tmp_path, {**TOY_PATHWAY_TEXTS, **TOY_BEHAVIOUR_TEXTS})
    assert check_pathway_texts(knowledge, routes(tmp_path)) == []


@pytest.mark.parametrize(("old", "new", "message"), [
    ("Disorders: Toy worry.", "Lesion: Toy worry.",
     "Step 3: needs one 'Disorders:' line, found 0"),
    ("Drugs: Toy tea.", "Drugs: Toy tea.\nDrugs: More tea.",
     "Step 4: needs at most one 'Drugs:' line, found 2"),
    ("Reaches the alpha gyrus.", "Reaches the {same} alpha gyrus.",
     "Step 3: side word {same} in a both-sides route"),
])
def test_behaviour_text_problems(tmp_path, old, new, message):
    text = TOY_BEHAVIOUR_TEXTS["pathway-mood"].replace(old, new, 1)
    knowledge = text_tree(tmp_path, {**TOY_PATHWAY_TEXTS, "pathway-mood": text})
    problems = check_pathway_texts(knowledge, routes(tmp_path))
    assert any(p.endswith(f"pathway-mood.md: {message}") for p in problems), problems


def test_both_sides_stations_need_a_shape_somewhere(tmp_path):
    path = write(tmp_path, "structures.toml", TOY_STRUCTURES)
    tree = build_tree(load_structures(path))
    structures, shaped = [p.structure for p in tree], {p.structure.id for p in tree if p.labels}
    both = load_pathways(write(tmp_path, "pathways.toml", HEAD + (
        'sides = "both"\nsteps = [{ structures = [100] }, { structures = [777] }]\n')))
    assert check_pathways(both, structures, shaped - {101, 102}) == [
        "pathway p step 1: 100 has no shape to light",
        "pathway p step 2: unknown structure id 777"]
    assert check_pathways(both, structures, shaped, left_out={777}) == []


def test_for_package_turns_left_out_stations_into_text_steps(tmp_path):
    mood = routes(tmp_path)[2]
    mood = replace(mood, steps=(Station((110, 170)), Station((170,)), Relay("Toy relay")))
    packed = for_package([mood], {110: "Beta nucleus", 170: "Toy gland"}, {170})[0]
    assert packed.steps == (Station((110,)), Relay("Toy gland"), Relay("Toy relay"))


def test_toy_timeline_loads(tmp_path):
    folder = tmp_path / "timelines"
    folder.mkdir()
    (folder / "mood.toml").write_text(TOY_TIMELINE)
    (timeline,) = load_timelines(folder, routes(tmp_path), REFS)
    assert timeline.route == "mood" and timeline.step_at(25) == 2


@pytest.mark.parametrize(("old", "new", "message"), [
    ('route = "mood"', 'route = "nope"', "unknown route 'nope'"),
    ("duration = 60", "duration = 0", "duration must be a positive number"),
    ("play_seconds = 6", "play_seconds = -1", "play_seconds must be a positive number"),
    ("[[0, 0.1], [20, 1.0], [60, 0.2]]", "[[0, 0.1], [20, 1.5], [60, 0.2]]",
     "curve 1: levels must be between 0 and 1"),
    ("[[0, 0.1], [20, 1.0], [60, 0.2]]", "[[0, 0.1], [30, 1.0], [20, 0.2]]",
     "curve 1: times must increase"),
    ("[[0, 0.1], [20, 1.0], [60, 0.2]]", "[[0, 0.1], [20, 1.0], [70, 0.2]]",
     "curve 1: times must be within 0 and the duration"),
    ("time = 40\nstep = 4", "time = 10\nstep = 4", "marks must be in time order"),
    ("time = 40\nstep = 4", "time = 40\nstep = 9", "mark 3: no step 9 in route 'mood'"),
    ("Toy curves [ref2020].", "Toy curves [nobody].", "cites missing reference [nobody]"),
    ("time = 20\nstep = 3", "time = 0\nstep = 3", "marks must be in time order"),
    ('route = "mood"', 'route = ["mood"]', "unknown route ['mood']"),
    ("time = 40\nstep = 4", "time = 70\nstep = 4", "marks must be within 0 and the duration"),
    ('[[curves]]\nname = "Toy hormone"\ncolor = [235, 200, 90]\n'
     'points = [[0, 0.1], [20, 1.0], [60, 0.2]]\n', "", "needs at least one curve"),
])
def test_timeline_errors(tmp_path, old, new, message):
    folder = tmp_path / "timelines"
    folder.mkdir()
    (folder / "mood.toml").write_text(TOY_TIMELINE.replace(old, new, 1))
    with pytest.raises(BuildError) as error:
        load_timelines(folder, routes(tmp_path), REFS)
    assert any(p.endswith(message) for p in error.value.problems), error.value.problems


def test_a_timeline_file_must_be_named_after_its_route(tmp_path):
    folder = tmp_path / "timelines"
    folder.mkdir()
    (folder / "other.toml").write_text(TOY_TIMELINE)
    with pytest.raises(BuildError) as error:
        load_timelines(folder, routes(tmp_path), REFS)
    assert error.value.problems == [f"{folder / 'other.toml'}: file name must be mood.toml"]


def test_the_toy_build_packages_routes_and_timelines(toy_behaviour_atlas):
    atlas = Atlas.open(toy_behaviour_atlas)
    assert [p.key for p in atlas.pathways] == ["loop", "short", "mood"]
    assert atlas.pathways[2].sides == "both" and atlas.timelines["mood"].duration == 60.0


def test_a_normal_build_turns_gland_stations_into_text_steps(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=True, pathways=True, local=True,
                                     behaviour=True)
    normal = Atlas.open(build(src, tmp_path / "n", cache=tmp_path / "c", log=lambda *_: None))
    local = Atlas.open(build(src, tmp_path / "l", cache=tmp_path / "c", log=lambda *_: None,
                             local=True))
    gland = {p.key: p for p in normal.pathways}["gland"]
    assert gland.steps == (Station((110,)), Relay("Toy gland"))
    assert {p.key: p for p in local.pathways}["gland"].steps == (Station((110,)), Station((170,)))


def test_a_station_whose_shape_is_not_meshed_stops_the_build(tmp_path, monkeypatch):
    import tools.build_atlas.build as build_module

    real_surface, real_levels = build_module.surface, build_module.levels

    def surface(data, affine, label, *rest):
        mesh = real_surface(data, affine, label, *rest)
        mesh.field_data["label"] = [label]
        return mesh

    def levels(mesh, *rest):
        if mesh.field_data["label"][0] == 120:
            return [], 0
        return real_levels(mesh, *rest)

    monkeypatch.setattr(build_module, "surface", surface)
    monkeypatch.setattr(build_module, "levels", levels)
    src = write_extended_source_tree(tmp_path, tracts=True, pathways=True)
    with pytest.raises(BuildError) as error:
        build(src, tmp_path / "out", cache=tmp_path / "c", log=lambda *_: None)
    assert error.value.problems == [
        "pathway loop step 6: 120 has no shape to light for a left start",
        "pathway loop step 6: 120 has no shape to light for a right start"]
