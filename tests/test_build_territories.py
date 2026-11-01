import pytest

from atlas_fixtures import place_territories, sha256_file, territory_volume, write_extended_source_tree
from cns_atlas import Atlas
from cns_atlas.lesions import territories
from tools.build_atlas.build import build

pytest.importorskip("pyvista")


def build_with_territories(root, local=True, present=True):
    cache = root / "cache"
    path = place_territories(root, cache) if present else None
    sha = sha256_file(path) if path else "0" * 64
    src = write_extended_source_tree(root, tracts=True, pathways=True, territories=sha)
    lines = []
    out = build(src, root / "out" / "toy", cache=cache, log=lines.append, local=local)
    return Atlas.open(out), lines


def test_territories_land_in_their_own_volume_as_their_own_kind(tmp_path):
    atlas, _lines = build_with_territories(tmp_path)
    found = territories(atlas)
    assert [s.name for s in found] == ["Toy artery A territory (left)",
                                       "Toy artery A territory (right)",
                                       "Toy artery B territory (left)",
                                       "Toy artery B territory (right)"]
    assert {s.kind for s in found} == {"territory"}
    assert atlas.territories is not None and atlas.territories.shape == territory_volume().shape
    assert "territories" not in {v.name for v in atlas.volumes}
    assert not any(atlas.has_mesh(s.id) for s in found)


def test_territories_are_left_out_of_a_shareable_build(tmp_path):
    atlas, _lines = build_with_territories(tmp_path, local=False)
    assert atlas.territories is None and territories(atlas) == []
    assert "toyart" not in atlas.sources


def test_a_missing_optional_manual_source_is_skipped_not_fatal(tmp_path):
    atlas, lines = build_with_territories(tmp_path, present=False)
    assert atlas.territories is None and territories(atlas) == []
    assert any("toyart" in line and "toy_arteries.nii.gz" in line for line in lines), lines


def test_a_territory_lesion_covers_that_territory_on_the_brain_grid(tmp_path):
    from cns_atlas.lesions import territory_lesion

    atlas, _lines = build_with_territories(tmp_path)
    left = next(s for s in territories(atlas) if s.name == "Toy artery A territory (left)")
    lesion = territory_lesion(atlas, left.id)
    brain = atlas.volumes[0]
    mask = lesion.masks[brain.name]
    assert mask.shape == brain.shape and mask.any()
    assert (mask == (atlas.territories.data == left.id)).all()


def test_territories_do_not_trim_the_brainstem_bodies(tmp_path):
    import numpy as np

    plain = write_extended_source_tree(tmp_path / "plain", tracts=False, shells=True)
    without = Atlas.open(build(plain, tmp_path / "plain" / "out", cache=tmp_path / "plain" / "cache",
                               log=lambda *_: None, local=True))
    cache = tmp_path / "with" / "cache"
    sha = sha256_file(place_territories(tmp_path / "with", cache))
    src = write_extended_source_tree(tmp_path / "with", tracts=False, shells=True, territories=sha)
    with_them = Atlas.open(build(src, tmp_path / "with" / "out", cache=cache,
                                 log=lambda *_: None, local=True))
    for body in (230, 240):
        a = np.asarray(without.mesh(body).vertices)
        b = np.asarray(with_them.mesh(body).vertices)
        assert a.shape == b.shape and np.allclose(a.mean(axis=0), b.mean(axis=0)), body
