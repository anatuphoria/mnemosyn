import random
from types import SimpleNamespace

from atlas_package import tetra, write_package
from cns_atlas import Atlas, Crossing, Pathway, Station
from cns_study.questions import (HIGHER, LAB_MODE, NORMAL, OUTCOMES, QUESTION_MODES, ROUTE_MODE,
                                 lab_items, offered, pool_for, route_items, scopes, span_text,
                                 stable_id)
from lab_helpers import toy_model
from study_atlas import study_structures


def route_atlas(root, steps, key="seeing"):
    structures = study_structures()
    meshes = {s.id: tetra(float(n)) for n, s in enumerate(structures) if s.side != "none"}
    pathway = Pathway(key, "Seeing", "eye", tuple(steps), "Senses")
    return Atlas.open(write_package(root / "pkg", structures, meshes=meshes, pathways=[pathway]))


STEPS = (Station((300,)), Crossing("The crossing"), Station((100,), side="opposite"),
         Station((200,), side="opposite"))


def test_a_route_asks_what_follows_each_station(tmp_path):
    atlas = route_atlas(tmp_path, STEPS)
    found = route_items(atlas)
    assert [(q.prompt, q.answer) for q in found] == [
        ("Seeing. After Lateral geniculate nucleus, what comes next?", "The crossing"),
        ("Seeing. After The crossing, what comes next?", "Precentral gyrus"),
        ("Seeing. After Precentral gyrus, what comes next?", "Middle temporal gyrus")]
    first, _crossing, third = found
    assert first.level == "routes" and first.scope == "Senses"
    assert first.geometry == {301} and first.reveal == frozenset()
    assert third.geometry == {102} and third.reveal == {202}
    assert set(first.options) == {"Precentral gyrus", "Middle temporal gyrus"}
    assert first.note == "Step 2 of 4 in this route."


def test_a_station_with_two_different_next_stops_is_not_asked(tmp_path):
    loop = (Station((300,)), Station((100,)), Station((300,)), Station((200,)), Station((310,)))
    asked = [q.name for q in route_items(route_atlas(tmp_path, loop))]
    assert asked == ["Seeing: after Precentral gyrus", "Seeing: after Middle temporal gyrus"]


def test_question_ids_stay_the_same_and_do_not_depend_on_position(tmp_path):
    assert stable_id("route:seeing:A>B") == stable_id("route:seeing:A>B") == 1877263606
    short = route_items(route_atlas(tmp_path / "a", STEPS[1:]))
    full = route_items(route_atlas(tmp_path / "b", STEPS))
    assert {q.id for q in short} < {q.id for q in full}
    assert len({q.id for q in full}) == len(full)


def test_route_choices_hold_the_answer_once_among_stations_of_the_route(tmp_path):
    long = (*STEPS, Station((210,)), Station((310,)), Station((400,)))
    question = route_items(route_atlas(tmp_path, long))[0]
    shown = offered(question, random.Random(3))
    assert len(shown) == len(set(shown)) == 4 and shown.count(question.answer) == 1
    assert "Lateral geniculate nucleus" not in shown


def lab_atlas(tmp_path):
    model = toy_model(tmp_path)
    return SimpleNamespace(models={model.key: model}, pathways=()), model


def test_lab_questions_come_from_the_checks_that_compare_with_normal(tmp_path):
    atlas, model = lab_atlas(tmp_path)
    removal, stressed = lab_items(atlas)
    name = model.value("x").name
    assert removal.answer == HIGHER and removal.level == "lab" and removal.scope == "toy"
    assert removal.prompt == (f"{model.name}. {model.experiment('remove_b').name}. "
                              f"On day 1 at 12:00, {name} is:")
    assert removal.note == f"In the model, {name} is at least 1.2 times normal."
    assert removal.source == ("toy", "removal", 720.0 - model.start_clock)
    assert stressed.answer == NORMAL and "after it" in stressed.prompt
    assert stressed.note == f"In the model, {name} is within 5% of normal again."
    assert offered(removal, random.Random(1)) == list(OUTCOMES)


def test_time_spans_read_as_words():
    assert [span_text(m) for m in (1, 45, 60, 90, 1380, 2880, 40320.7)] == [
        "1 minute", "45 minutes", "1 hour", "1.5 hours", "23 hours", "2 days", "28 days"]


def test_pools_and_scopes_follow_the_level(tmp_path):
    atlas = route_atlas(tmp_path, STEPS)
    assert QUESTION_MODES == {"routes": ROUTE_MODE, "lab": LAB_MODE}
    assert scopes(atlas, "routes") == [("Senses", "Senses")]
    assert len(pool_for(atlas, "routes", "Senses")) == 3
    assert pool_for(atlas, "routes", "Elsewhere") == []
    assert pool_for(atlas, "lab") == []
    assert {item.level for item in pool_for(atlas, "structures")} == {"structures"}
