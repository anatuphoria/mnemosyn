import numpy as np
import pytest

pv = pytest.importorskip("pyvista")

from atlas_fixtures import write_extended_source_tree  # noqa: E402
from cns_atlas import Atlas  # noqa: E402
from tools.build_atlas.build import build  # noqa: E402
from tools.build_atlas.hierarchy import load_structures  # noqa: E402
from tools.build_atlas.meshing import cut_levels, surface  # noqa: E402
from tools.build_atlas.recipe import load_recipe  # noqa: E402
from tools.build_atlas.validate import check_sources  # noqa: E402

BANDS = [(1, -np.inf, 15.0), (2, 15.0, 25.0), (3, 25.0, np.inf)]


def cord_surface():
    grid = np.indices((20, 20, 40))
    mask = ((grid[0] - 10) ** 2 + (grid[1] - 10) ** 2 <= 25) & (grid[2] >= 5) & (grid[2] < 35)
    return surface(mask.astype(np.uint8), np.eye(4), 1, 20, 0.1, 1.0)


def as_polydata(data):
    faces = np.c_[np.full(len(data.faces), 3), data.faces].ravel()
    return pv.PolyData(np.asarray(data.vertices, dtype=float), faces)


def edge_points(data):
    edges = as_polydata(data).extract_feature_edges(boundary_edges=True, feature_edges=False,
                                                    manifold_edges=False,
                                                    non_manifold_edges=False)
    return np.asarray(edges.points)


def rounded(points):
    return {tuple(p) for p in np.round(points, 3)}


@pytest.fixture(scope="module")
def pieces():
    return cut_levels(cord_surface(), BANDS, 4000, (1.0, 0.25, 0.05), 64)[0]


def test_cut_pieces_have_no_end_caps_and_meet_their_neighbours(pieces):
    for level in range(3):
        middle = edge_points(pieces[2][level])
        assert len(middle) and np.all(np.isclose(middle[:, 2], 15.0, atol=1e-3)
                                      | np.isclose(middle[:, 2], 25.0, atol=1e-3))
        lower = edge_points(pieces[1][level])
        assert np.allclose(lower[:, 2], 15.0, atol=1e-3)
        assert rounded(lower) == rounded(middle[np.isclose(middle[:, 2], 15.0, atol=1e-3)])


def test_pieces_enclose_the_whole_surface():
    mesh = cord_surface()
    cut = cut_levels(mesh, BANDS, 10 ** 6, (1.0,), 64)[0]
    assert sum(as_polydata(cut[i][0]).area for i in (1, 2, 3)) == pytest.approx(mesh.area,
                                                                               rel=0.01)


def test_seam_normals_match_on_both_sides(pieces):
    def seam(data):
        points = np.asarray(data.vertices, dtype=float)
        keep = np.isclose(points[:, 2], 15.0, atol=1e-3)
        return {tuple(p): n for p, n in zip(np.round(points[keep], 3),
                                            np.asarray(data.normals, dtype=float)[keep])}
    lower, middle = seam(pieces[1][0]), seam(pieces[2][0])
    assert lower and all(np.allclose(lower[p], middle[p], atol=0.02) for p in lower)


def quiet_build(src, out, cache, **kwargs):
    return build(src, out, cache=cache, log=lambda *_: None, **kwargs)


def test_a_toy_build_meshes_segments_from_the_cord_mask(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, spine=True, cord=True)
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    upper = np.asarray(atlas.mesh(200).vertices)[:, 2]
    lower = np.asarray(atlas.mesh(210).vertices)[:, 2]
    top = -230.0 + 59 + 0.5
    assert upper.max() < top + 1.0 and lower.min() < -230.0 + 12
    assert upper.min() == pytest.approx(lower.max(), abs=1e-3)
    assert sorted(np.unique(np.asarray(atlas.volumes[1].data)).tolist()) == [0, 200, 210, 220]
    assert "toyspine-cord" not in {s for st in atlas.structures for s in st.sources}


def problems_for(src):
    return check_sources(load_structures(src / "structures.toml"),
                         load_recipe(src / "recipe.toml"), src)


def edit(path, old, new):
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))


def test_outline_of_must_name_a_label_source_and_map_no_structures(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, spine=True, cord=True)
    assert problems_for(src) == []
    edit(src / "recipe.toml", 'outline_of = "toyspine"', 'outline_of = "toyspine-t2"')
    assert "source toyspine-cord: outline_of 'toyspine-t2' is not a label source" in (
        problems_for(src))
    edit(src / "recipe.toml", 'outline_of = "toyspine-t2"', 'outline_of = "toyspine"')
    edit(src / "structures.toml", 'source = "toyspine", midline = 2',
         'source = "toyspine-cord", midline = 1')
    assert "source toyspine-cord: an outline source cannot have structures" in problems_for(src)


def test_inside_keeps_a_shape_within_the_cord_outline(tmp_path):
    import nibabel as nib

    from atlas_fixtures import SPINE_AFFINE, SPINE_SHAPE, sha256_file

    src = write_extended_source_tree(tmp_path, tracts=False, spine=True, cord=True)
    tract = tmp_path / "upstream" / "toy_spine_wm.nii.gz"
    old = sha256_file(tract)
    mask = np.zeros(SPINE_SHAPE, dtype=np.uint8)
    mask[3:10, 6:10, 40:60] = 1
    nib.save(nib.Nifti1Image(mask, SPINE_AFFINE), tract)
    edit(src / "recipe.toml", old, sha256_file(tract))
    plain = Atlas.open(quiet_build(src, tmp_path / "plain", tmp_path / "cache", local=True))
    edit(src / "recipe.toml", "mask = true\n", 'mask = true\ninside = "toyspine-cord"\n')
    assert problems_for(src) == []
    atlas = Atlas.open(quiet_build(src, tmp_path / "out", tmp_path / "cache", local=True))
    assert np.asarray(plain.mesh(220).vertices)[:, 0].max() > 3.0
    assert np.asarray(atlas.mesh(220).vertices)[:, 0].max() < 8.0 - 6 + 0.5
    voxels = [(np.asarray(a.volumes[1].data) == 220).sum() for a in (plain, atlas)]
    assert voxels[0] == voxels[1] > 0


def test_inside_must_name_an_outline_source(tmp_path):
    src = write_extended_source_tree(tmp_path, tracts=False, spine=True, cord=True)
    edit(src / "recipe.toml", "mask = true\n", 'mask = true\ninside = "toyspine"\n')
    assert "source toyspine-wm: inside 'toyspine' is not an outline source of volume spine" in (
        problems_for(src))


def test_an_empty_cord_piece_is_named():
    from cns_atlas.meshes import MeshData
    from tools.build_atlas.build import empty_pieces

    empty = MeshData(np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float16),
                     np.zeros((0, 3), np.uint32))
    full = MeshData(np.zeros((3, 3), np.float32), np.zeros((3, 3), np.float16),
                    np.array([[0, 1, 2]], np.uint32))
    pieces = {200: [full], 201: [empty]}
    cuts = [(200, -10.0, 0.0), (201, 0.0, 12.5)]
    assert empty_pieces(pieces, cuts, {200: "Upper segment", 201: "Lower segment"}) == [
        "structure Lower segment: its cord piece between 0.0 and 12.5 mm has no surface"]
