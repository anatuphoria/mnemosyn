import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

collect_ignore = []
if not importlib.util.find_spec("pyvistaqt"):
    collect_ignore.append("test_desktop.py")
    collect_ignore.append("test_desktop_tracts.py")
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
