import numpy as np
import pytest

from atlas_fixtures import TOY_STRUCTURES, write_source_tree
from cns_atlas.knowledge import load_references
from tools.build_atlas.hierarchy import (LabelRef, PlannedStructure, RawStructure, build_tree,
                                         load_structures, shade, sibling_factors, with_xrefs)
from tools.build_atlas.idlock import IdLock, load_lock, write_lock
from tools.build_atlas.recipe import BuildError, load_recipe
from tools.build_atlas.validate import (check_hierarchy, check_ids, check_knowledge,
                                        check_sources, check_voxels)


def raw(id, parent, kind="region", side="none", sources=(), labels=(), concept=None):
    return RawStructure(id=id, parent=parent, acronym=f"S{id}", name=f"S{id}", kind=kind,
                        side=side, concept=concept, color=None, synonyms=(), xrefs={},
                        sources=tuple(sources), labels=tuple(labels))


@pytest.fixture
def src(tmp_path):
    return write_source_tree(tmp_path / "src", "/nonexistent/toy.tar.gz", "0" * 64)


def test_concepts_expand_into_sided_children(src):
    raws = {r.id: r for r in load_structures(src / "structures.toml")}
    assert sorted(raws) == [1, 2, 100, 101, 102, 110, 111, 112, 120]
    left = raws[101]
    assert (left.name, left.acronym, left.side, left.concept) == (
        "Alpha gyrus (left)", "ALG-L", "left", 100)
    assert left.labels == (LabelRef("toy", 1),) and left.sources == ("toy",)
    assert left.synonyms == ("left Alpha gyrus",)
    assert raws[100].labels == () and raws[100].sources == ()
    assert raws[112].kind == "nucleus"
    assert (raws[120].side, raws[120].labels) == ("midline", (LabelRef("toy", 5),))


@pytest.mark.parametrize("record, message", [
    ('{ id = 5, parent = 1, acronym = "X", name = "X", colour = [1, 2, 3] }', "unknown keys"),
    ('{ id = 5, parent = 1, acronym = "X" }', "missing \\['name'\\]"),
    ('{ id = 5, parent = 1, acronym = "X", name = "X", midline = 1, left = 2 }', "both 'midline'"),
])
def test_bad_concept_records_are_rejected(tmp_path, record, message):
    path = tmp_path / "structures.toml"
    path.write_text(f'default_source = "toy"\nconcepts = [\n  {record},\n]\n')
    with pytest.raises(BuildError, match=message):
        load_structures(path)


def test_build_tree_is_depth_first_with_paths_and_inherited_colors(src):
    planned = build_tree(load_structures(src / "structures.toml"))
    assert [p.structure.id for p in planned] == [1, 2, 100, 101, 102, 110, 111, 112, 120]
    by_id = {p.structure.id: p.structure for p in planned}
    assert by_id[101].structure_id_path == (1, 2, 100, 101)
    assert by_id[1].rgb_triplet == (170, 170, 180)
    assert by_id[100].rgb_triplet == (102, 119, 170)
    assert by_id[101].rgb_triplet == by_id[102].rgb_triplet == (102, 119, 170)
    assert by_id[110].rgb_triplet == by_id[111].rgb_triplet == (230, 120, 120)
    assert by_id[120].rgb_triplet == (140, 157, 208)


def test_with_xrefs_adds_source_label_names(src):
    planned = build_tree(load_structures(src / "structures.toml"))
    named = {p.structure.id: p.structure for p in with_xrefs(planned, {"toy": {1: "Alpha_L"}})}
    assert named[101].xrefs == {"toy": "Alpha_L"}
    assert named[102].xrefs == {}


def test_valid_toy_hierarchy_has_no_problems(src):
    assert check_hierarchy(load_structures(src / "structures.toml")) == []


@pytest.mark.parametrize("raws, message", [
    ([raw(1, None), raw(1, None)], "id 1 is used more than once"),
    ([raw(1, None), raw(70000, 1)], "id 70000 is outside 1..65535"),
    ([raw(1, None), raw(2, None)], "expected exactly one root, found 2"),
    ([raw(1, None), raw(2, 9)], "parent 9 does not exist"),
    ([raw(1, None), raw(2, 3), raw(3, 2)], "hierarchy has a cycle"),
    ([raw(1, None, kind="lobe")], "unknown kind 'lobe'"),
    ([raw(1, None, side="up")], "unknown side 'up'"),
])
def test_hierarchy_problems(raws, message):
    assert any(message in p for p in check_hierarchy(raws))


def test_id_lock_rules():
    raws = [raw(1, None), raw(2, 1)]
    assert check_ids(raws, IdLock(frozenset({1, 2}), frozenset())) == []
    assert check_ids(raws, IdLock(frozenset({1}), frozenset({2}))) == [
        "id 2 is retired and cannot be reused"]
    problems = check_ids(raws, IdLock(frozenset({1, 2, 3}), frozenset()))
    assert problems == ["id 3 was published but is missing; add it to 'retired' in ids.lock"]
    assert check_ids(raws, IdLock(frozenset({1, 2, 3}), frozenset({3}))) == []


def test_id_lock_round_trip(tmp_path):
    path = tmp_path / "ids.lock"
    assert load_lock(path) == IdLock(frozenset(), frozenset())
    write_lock(path, IdLock(frozenset(range(1, 20)), frozenset()))
    text = path.read_text()
    assert text.startswith("published = [\n  1, 2, 3,")
    assert text.endswith("retired = []\n")
    assert load_lock(path) == IdLock(frozenset(range(1, 20)), frozenset())


def test_toy_sources_are_valid(src):
    recipe = load_recipe(src / "recipe.toml")
    assert check_sources(load_structures(src / "structures.toml"), recipe, src) == []


@pytest.mark.parametrize("old, new, message", [
    ('licence = "CC0 1.0"', 'licence = ""', "source toy: licence is missing"),
    ("redistribution = true", "redistribution = false", "source toy: redistribution is not allowed"),
    ('volume = "brain"', 'volume = "cord"', "source toy: unknown volume 'cord'"),
    ('grid_source = "toy"', 'grid_source = "other"', "volume brain: unknown grid source 'other'"),
    ("priority = 1", 'priority = 1\nlicence_file = "LICENSES/missing.txt"',
     "source toy: licence file LICENSES/missing.txt is missing"),
])
def test_source_problems(src, old, new, message):
    path = src / "recipe.toml"
    path.write_text(path.read_text().replace(old, new))
    problems = check_sources(load_structures(src / "structures.toml"), load_recipe(path), src)
    assert message in problems


def test_structure_source_problems(src):
    recipe = load_recipe(src / "recipe.toml")
    raws = [raw(1, None), raw(5, 1, labels=[LabelRef("toy", 1)]),
            raw(6, 1, sources=["elsewhere"], labels=[LabelRef("elsewhere", 2)])]
    problems = check_sources(raws, recipe, src)
    assert "structure 5: has geometry but lists no source" in problems
    assert "structure 6: unknown source 'elsewhere'" in problems


def test_recipe_missing_key(tmp_path):
    path = tmp_path / "recipe.toml"
    path.write_text('name = "x"\n')
    with pytest.raises(BuildError, match="missing key"):
        load_recipe(path)


def knowledge_problems(src):
    raws = load_structures(src / "structures.toml")
    refs = load_references(src / "knowledge" / "references.toml")
    return check_knowledge(src / "knowledge", refs, {r.id: r.concept for r in raws}, set())


def test_toy_knowledge_is_valid(src):
    assert knowledge_problems(src) == []


@pytest.mark.parametrize("name, text, message", [
    ("100.md", "+++\nid = 100\n+++\n## Function\nX [nope2000].\n", "cites missing reference [nope2000]"),
    ("999.md", "+++\nid = 999\n+++\n## Function\nX [ref2020].\n", "unknown id 999"),
    ("101.md", "+++\nid = 101\n+++\n## Function\nX [ref2020].\n", "describe concept 100 instead of 101"),
    ("120.md", "+++\nid = 110\n+++\n## Function\nX [ref2020].\n", "file name must be 110.md"),
    ("110.md", "## Function\nX.\n", "missing '+++' header"),
    ("x.md", '+++\nkey = "x"\n+++\n## Function\nX [ref2020].\n', "unknown key 'x'"),
])
def test_knowledge_problems(src, name, text, message):
    (src / "knowledge" / "en" / name).write_text(text)
    assert any(message in p for p in knowledge_problems(src))


def test_reference_without_locator(src):
    (src / "knowledge" / "references.toml").write_text(
        '[ref2020]\nauthors = "A"\ntitle = "T"\nyear = 2020\n')
    assert "reference [ref2020] has none of doi, url, isbn" in knowledge_problems(src)


def test_structure_without_voxels():
    planned = [PlannedStructure(build_tree([raw(1, None)])[0].structure, ()),
               PlannedStructure(build_tree([raw(7, None)])[0].structure, (LabelRef("toy", 3),))]
    volume = np.zeros((2, 2, 2), dtype=np.uint16)
    assert check_voxels(planned, [volume]) == ["structure 7 (S7) has no voxels"]
    volume[0, 0, 0] = 7
    assert check_voxels(planned, [volume]) == []


def test_shade_mixes_toward_white_or_black():
    assert shade((100, 200, 50), 0.0) == (100, 200, 50)
    assert shade((100, 200, 50), 0.5) == (178, 228, 152)
    assert shade((100, 200, 50), -0.5) == (50, 100, 25)


def test_sibling_factors_span_evenly_by_id():
    assert sibling_factors([7]) == {7: 0.0}
    factors = sibling_factors([30, 10, 20])
    assert list(factors) == [10, 20, 30]
    assert [round(f, 6) for f in factors.values()] == [-0.15, 0.0, 0.15]
