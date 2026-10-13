import pytest

from cns_atlas.model import Pathway, Relay, Station, step_from_json, step_to_json
from tools.build_atlas.pathways import for_package, load_pathways
from tools.build_atlas.recipe import BuildError


def routes(tmp_path, step):
    path = tmp_path / "pathways.toml"
    path.write_text(f"""\
[[pathways]]
key = "k"
name = "K"
start = "x"
group = "Behaviour"
sides = "both"
texts = "behaviour"
steps = [{step}]
""")
    return path


def test_a_station_reads_and_writes_its_fallback():
    station = Station((5,), fallback="Old name")
    assert step_to_json(station) == {"structures": [5], "side": "same", "fallback": "Old name"}
    assert step_from_json(step_to_json(station)) == station
    assert "fallback" not in step_to_json(Station((5,)))


def test_the_route_file_takes_a_fallback(tmp_path):
    [route] = load_pathways(routes(tmp_path, '{ structures = [110], fallback = "Toy words" }'))
    assert route.steps == (Station((110,), fallback="Toy words"),)


@pytest.mark.parametrize(("step", "message"), [
    ('{ structures = [110], fallback = "" }', "pathway k step 1: fallback needs a name"),
    ('{ relay = "R", fallback = "x" }', "pathway k step 1: unknown keys ['fallback']"),
])
def test_bad_fallbacks_stop_the_build(tmp_path, step, message):
    with pytest.raises(BuildError) as error:
        load_pathways(routes(tmp_path, step))
    assert message in error.value.problems


def test_for_package_uses_the_fallback_name():
    route = Pathway("k", "K", "x", (Station((5,), fallback="Old name"), Station((6,))),
                    "Behaviour", "both", "behaviour")
    [out] = for_package([route], {5: "New", 6: "Six"}, {5, 6})
    assert out.steps == (Relay("Old name"), Relay("Six"))
