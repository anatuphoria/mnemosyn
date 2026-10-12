from pathlib import Path

import pytest

from atlas_fixtures import (TOY_PATHWAY_TEXTS, TOY_PATHWAYS, TOY_STRUCTURES,
                            write_extended_source_tree)
from cns_atlas import Atlas, Crossing, Relay, Station
from tools.build_atlas.hierarchy import build_tree, load_structures
from tools.build_atlas.pathways import check_pathway_texts, check_pathways, load_pathways
from tools.build_atlas.recipe import BuildError

HEAD = '[[pathways]]\nkey = "p"\nname = "N"\nstart = "s"\ngroup = "G"\n'


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "pathways.toml"
    path.write_text(text)
    return path


def planned(tmp_path: Path):
    path = tmp_path / "structures.toml"
    path.write_text(TOY_STRUCTURES)
    tree = build_tree(load_structures(path))
    return [p.structure for p in tree], {p.structure.id for p in tree if p.labels}


def text_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    folder = tmp_path / "knowledge" / "en"
    folder.mkdir(parents=True)
    for key, text in files.items():
        (folder / f"{key}.md").write_text(text)
    return tmp_path / "knowledge"


def test_a_missing_file_means_no_pathways(tmp_path):
    assert load_pathways(tmp_path / "pathways.toml") == []


def test_pathways_parse_into_steps(tmp_path):
    loop, short = load_pathways(write(tmp_path, TOY_PATHWAYS))
    assert (loop.key, loop.name, loop.start) == ("loop", "Toy loop", "alpha gyrus")
    assert loop.steps == (Station((100,)), Crossing("Toy crossing"),
                          Station((150,), "opposite"), Station((110,), "opposite"),
                          Relay("Toy relay", "opposite"), Station((120,), "midline"))
    assert short.steps == (Station((110,)),)


@pytest.mark.parametrize(("body", "message"), [
    ('[[pathways]]\nkey = "Bad Key"\nname = "N"\nstart = "s"\ngroup = "G"\n'
     'steps = [{ cross = "X" }]\n',
     "pathway Bad Key: key must be lowercase letters, digits and hyphens"),
    (HEAD + "steps = []\n", "pathway p: needs at least one step"),
    ('[[pathways]]\nkey = "p"\nname = "N"\ngroup = "G"\nsteps = [{ cross = "X" }]\n',
     "pathway p: needs a start"),
    (HEAD + 'colour = 1\nsteps = [{ cross = "X" }]\n', "pathway p: unknown keys ['colour']"),
    (HEAD + 'steps = [{ cross = "X", relay = "Y" }]\n',
     "pathway p step 1: needs exactly one of structures, cross or relay"),
    (HEAD + 'steps = [{ name = "X" }]\n',
     "pathway p step 1: needs exactly one of structures, cross or relay"),
    (HEAD + 'steps = [{ structures = [100], side = "up" }]\n',
     "pathway p step 1: unknown side 'up'"),
    (HEAD + 'steps = [{ cross = "X", side = "same" }]\n',
     "pathway p step 1: unknown keys ['side']"),
    (HEAD + "steps = [{ structures = [] }]\n",
     "pathway p step 1: structures must be a non-empty list of ids"),
    (HEAD + 'steps = [{ relay = "" }]\n', "pathway p step 1: relay needs a name"),
    (HEAD + 'steps = [{ cross = "X" }]\n' + HEAD + 'steps = [{ cross = "X" }]\n',
     "pathway p: duplicate key"),
])
def test_malformed_pathways_stop_the_build(tmp_path, body, message):
    with pytest.raises(BuildError) as error:
        load_pathways(write(tmp_path, body))
    assert message in error.value.problems


def test_stations_need_known_ids_with_a_shape_for_each_start_side(tmp_path):
    structures, shaped = planned(tmp_path)
    pathways = load_pathways(write(tmp_path, HEAD + (
        "steps = [{ structures = [100] }, { structures = [999] }, "
        '{ structures = [100], side = "midline" }, { structures = [120], side = "opposite" }, '
        '{ cross = "X" }]\n')))
    assert check_pathways(pathways, structures, shaped) == [
        "pathway p step 2: unknown structure id 999",
        "pathway p step 3: 100 has no shape to light for a left start",
        "pathway p step 3: 100 has no shape to light for a right start",
    ]


def test_a_side_without_a_shape_is_reported(tmp_path):
    structures, shaped = planned(tmp_path)
    pathways = load_pathways(write(tmp_path, HEAD + "steps = [{ structures = [110] }]\n"))
    assert check_pathways(pathways, structures, shaped - {112}) == [
        "pathway p step 1: 110 has no shape to light for a right start"]


def test_toy_texts_match_their_routes(tmp_path):
    pathways = load_pathways(write(tmp_path, TOY_PATHWAYS))
    assert check_pathway_texts(text_tree(tmp_path, TOY_PATHWAY_TEXTS), pathways) == []


def test_a_missing_description_is_reported(tmp_path):
    pathways = load_pathways(write(tmp_path, TOY_PATHWAYS))
    knowledge = text_tree(tmp_path, {"pathway-loop": TOY_PATHWAY_TEXTS["pathway-loop"]})
    missing = knowledge / "en" / "pathway-short.md"
    assert check_pathway_texts(knowledge, pathways) == [
        f"pathway short: description {missing} is missing"]


@pytest.mark.parametrize(("old", "new", "message"), [
    ("## Step 6\n", "## Step 7\n", "sections must be Overview, then Step 1 to Step 6"),
    ("## Overview\nA toy loop that crosses once [ref2020].\n\n", "",
     "sections must be Overview, then Step 1 to Step 6"),
    ("Role: Crosses the midline.\n", "", "Step 2: needs one 'Role:' line, found 0"),
    ("Lesion: Not described.\n", "Lesion: Not described.\nLesion: Again.\n",
     "Step 5: needs one 'Lesion:' line, found 2"),
    ("Role: Crosses the midline.\n", "Role: Crosses the midline.\nIt is short.\n",
     "Step 2: unexpected line 'It is short.'"),
    ("{same} alpha gyrus", "{left} alpha gyrus", "Step 1: unknown side word {left}"),
    ("A toy loop", "A {oposite} loop", "Overview: unknown side word {oposite}"),
    ("Loss on the {opposite} side.", "{Same} side.", "Step 1: unknown side word {Same}"),
    ("Runs down the {opposite}", "Runs down the {opposite side}",
     "Step 3: unknown side word {opposite side}"),
])
def test_text_problems_are_reported(tmp_path, old, new, message):
    pathways = load_pathways(write(tmp_path, TOY_PATHWAYS))
    texts = {**TOY_PATHWAY_TEXTS,
             "pathway-loop": TOY_PATHWAY_TEXTS["pathway-loop"].replace(old, new, 1)}
    problems = check_pathway_texts(text_tree(tmp_path, texts), pathways)
    assert any(p.endswith(f"pathway-loop.md: {message}") for p in problems), problems


def test_the_toy_build_packages_its_pathways(toy_pathway_atlas):
    atlas = Atlas.open(toy_pathway_atlas)
    assert [p.key for p in atlas.pathways] == ["loop", "short"]
    assert atlas.pathways[0].steps[4] == Relay("Toy relay", "opposite")
    assert atlas.pathway_text("short", "left").steps[0].role == "Sits in the left beta nucleus."
    assert "- pathways: 2\n" in (toy_pathway_atlas / "build-report.md").read_text()


def test_an_atlas_without_a_routes_file_has_no_pathways(toy_atlas):
    assert Atlas.open(toy_atlas).pathways == ()


def test_an_unknown_station_stops_the_build(tmp_path):
    from tools.build_atlas.build import build

    src = write_extended_source_tree(tmp_path, tracts=True, pathways=True)
    routes = src / "pathways.toml"
    routes.write_text(routes.read_text().replace("[120]", "[999]"))
    with pytest.raises(BuildError) as error:
        build(src, tmp_path / "out", cache=tmp_path / "cache", log=lambda *_: None)
    assert error.value.problems == ["pathway loop step 6: unknown structure id 999"]
