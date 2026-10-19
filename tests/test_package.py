import json
import os
import subprocess

import pytest

from atlas_package import TOY_SOURCE, tetra, tiny_structures, write_package
from tools import package


def test_file_names_say_the_system_and_whether_they_may_be_shared():
    assert package.file_name("0.1.0", "linux", False) == "Mnemosyn-0.1.0-x86_64.AppImage"
    assert package.file_name("0.1.0", "windows", False) == "Mnemosyn-0.1.0-Setup.exe"
    assert (package.file_name("0.1.0", "linux", True)
            == "Mnemosyn-0.1.0-local-not-for-sharing-x86_64.AppImage")
    assert (package.file_name("0.1.0", "windows", True)
            == "Mnemosyn-0.1.0-local-not-for-sharing-Setup.exe")


def test_the_version_comes_from_the_project_file():
    assert package.project_version() == "0.1.0"


def toy_atlas(root, local):
    path = write_package(root, tiny_structures(), meshes={101: tetra()}, sources=[TOY_SOURCE])
    if local:
        metadata = json.loads((path / "metadata.json").read_text())
        metadata["local_only"] = [TOY_SOURCE.id]
        (path / "metadata.json").write_text(json.dumps(metadata))
    return path


def test_local_packages_are_never_made_on_github(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(package.PackageError, match="never made on GitHub Actions"):
        package.check(toy_atlas(tmp_path / "pkg", True), local=True)


def test_a_local_atlas_needs_the_local_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    local = toy_atlas(tmp_path / "local", True)
    with pytest.raises(package.PackageError, match="is a local build; add --local"):
        package.check(local, local=False)
    package.check(local, local=True)


def test_a_shareable_atlas_is_not_packaged_as_local(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    shared = toy_atlas(tmp_path / "shared", False)
    with pytest.raises(package.PackageError, match="is a shareable build; build it with --local"):
        package.check(shared, local=True)
    package.check(shared, local=False)


def test_a_missing_atlas_is_built_first(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(package, "build_atlas",
                        lambda src, out, local, log: calls.append((out, local)))
    package.ensure_atlas(tmp_path / "missing", local=True, log=lambda *_: None)
    assert calls == [(tmp_path / "missing", True)]


@pytest.mark.slow
def test_the_packaged_app_reaches_its_first_frame(tmp_path):
    atlas = package.ROOT / "atlases" / "cns"
    if not (atlas / "metadata.json").exists():
        pytest.skip("real atlas not built")
    local = package.is_local(atlas)
    folder = package.package(atlas, tmp_path / "dist", local=local, log=lambda *_: None,
                             wrap=False)
    env = {"HOME": os.environ["HOME"], "QT_QPA_PLATFORM": "offscreen", "PATH": "/usr/bin:/bin"}
    result = subprocess.run([str(folder / package.EXECUTABLE), "--first-frame"], env=env,
                            capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "first frame:" in result.stdout
