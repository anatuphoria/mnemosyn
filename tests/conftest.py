import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

collect_ignore = []
if not importlib.util.find_spec("pyvistaqt"):
    collect_ignore.append("test_desktop.py")
    collect_ignore.append("test_desktop_tracts.py")
    collect_ignore.append("test_desktop_pathways.py")
    collect_ignore.append("test_desktop_focus.py")
    collect_ignore.append("test_desktop_behaviour.py")
if not importlib.util.find_spec("pyvista"):
    collect_ignore.append("test_build_atlas.py")


@pytest.fixture(scope="session")
def toy_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    from atlas_fixtures import build_toy_atlas

    return build_toy_atlas(tmp_path_factory.mktemp("toy"))


@pytest.fixture(scope="session")
def toy_tract_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    from atlas_fixtures import build_extended_toy_atlas

    return build_extended_toy_atlas(tmp_path_factory.mktemp("toytracts"), tracts=True)


@pytest.fixture(scope="session")
def toy_pathway_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    from atlas_fixtures import build_extended_toy_atlas

    return build_extended_toy_atlas(tmp_path_factory.mktemp("toypathways"), tracts=True,
                                    pathways=True)


@pytest.fixture(scope="session")
def toy_behaviour_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    from atlas_fixtures import build_extended_toy_atlas

    return build_extended_toy_atlas(tmp_path_factory.mktemp("toybehaviour"), tracts=True,
                                    pathways=True, behaviour=True)


@pytest.fixture(scope="session")
def toy_spine_atlas(tmp_path_factory):
    pytest.importorskip("pyvista")
    from atlas_fixtures import write_extended_source_tree
    from tools.build_atlas.build import build

    root = tmp_path_factory.mktemp("toyspine")
    src = write_extended_source_tree(root, tracts=False, spine=True)
    return build(src, root / "out" / "toy", cache=root / "cache", log=lambda *_: None,
                 local=True)
