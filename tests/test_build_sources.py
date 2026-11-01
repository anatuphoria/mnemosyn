import hashlib
import io
import tarfile
import zipfile
from urllib.error import HTTPError

import nibabel as nib
import numpy as np
import pytest

from cns_atlas.model import Source, Structure
from tools.build_atlas import fetch as fetch_module
from tools.build_atlas.fetch import fetch, member_path
from tools.build_atlas.hierarchy import LabelRef, PlannedStructure
from tools.build_atlas.labels import mapping_for, merge, read_label_names, source_values
from tools.build_atlas.recipe import BuildError, SourceSpec


def spec_for(download, sha256, member=""):
    source = Source("toy", "Toy", "A", 2024, "1", "CC0 1.0", True)
    return SourceSpec(source=source, download=str(download), sha256=sha256, member=member,
                      label_names="", volume="brain", priority=1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_tar(path, members: dict[str, bytes]):
    with tarfile.open(path, "w:gz") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return path


def test_fetch_copies_verifies_and_reuses_cache(tmp_path):
    original = tmp_path / "data.bin"
    original.write_bytes(b"atlas bytes")
    spec = spec_for(original, sha(b"atlas bytes"))
    cached = fetch(spec, tmp_path / "cache")
    assert cached.read_bytes() == b"atlas bytes"
    assert cached.parent.name == spec.sha256
    original.unlink()
    assert fetch(spec, tmp_path / "cache") == cached


def test_fetch_rejects_checksum_mismatch_and_leaves_nothing(tmp_path):
    original = tmp_path / "data.bin"
    original.write_bytes(b"tampered")
    spec = spec_for(original, sha(b"expected"))
    with pytest.raises(BuildError, match="checksum mismatch"):
        fetch(spec, tmp_path / "cache")
    assert list((tmp_path / "cache" / spec.sha256).iterdir()) == []


def test_fetch_reports_download_failure(tmp_path):
    with pytest.raises(BuildError, match="download failed"):
        fetch(spec_for(tmp_path / "missing.bin", "0" * 64), tmp_path / "cache")


def flaky_urlopen(failures):
    calls = []

    def urlopen(url, context=None, timeout=None):
        calls.append(url)
        if len(calls) <= len(failures):
            raise failures[len(calls) - 1]
        return io.BytesIO(b"atlas bytes")
    return urlopen, calls


def test_fetch_retries_a_dropped_download(tmp_path, monkeypatch):
    urlopen, calls = flaky_urlopen([ConnectionResetError("reset"), TimeoutError("slow")])
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module.time, "sleep", lambda seconds: None)
    spec = spec_for("https://example.org/data.bin", sha(b"atlas bytes"))
    assert fetch(spec, tmp_path / "cache").read_bytes() == b"atlas bytes"
    assert len(calls) == 3


def test_fetch_gives_up_after_the_last_attempt(tmp_path, monkeypatch):
    urlopen, calls = flaky_urlopen([ConnectionResetError("reset")] * fetch_module.ATTEMPTS)
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module.time, "sleep", lambda seconds: None)
    with pytest.raises(BuildError, match="download failed"):
        fetch(spec_for("https://example.org/data.bin", "0" * 64), tmp_path / "cache")
    assert len(calls) == fetch_module.ATTEMPTS


def test_fetch_does_not_retry_a_missing_file(tmp_path, monkeypatch):
    missing = HTTPError("https://example.org/data.bin", 404, "Not Found", None, None)
    urlopen, calls = flaky_urlopen([missing])
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch_module.time, "sleep", lambda seconds: None)
    with pytest.raises(BuildError, match="download failed"):
        fetch(spec_for("https://example.org/data.bin", "0" * 64), tmp_path / "cache")
    assert len(calls) == 1


def test_member_path_extracts_once(tmp_path):
    archive = make_tar(tmp_path / "a.tar.gz", {"DIR/table.txt": b"1 Alpha_L 1\n"})
    spec = spec_for(archive, sha(archive.read_bytes()))
    cached = fetch(spec, tmp_path / "cache")
    member = member_path(spec, cached, "DIR/table.txt")
    assert member.read_bytes() == b"1 Alpha_L 1\n"
    assert member_path(spec, cached, "DIR/table.txt") == member
    with pytest.raises(BuildError, match="not found"):
        member_path(spec, cached, "DIR/other.txt")
    with pytest.raises(BuildError, match="is not a tar or zip archive"):
        member_path(spec, tmp_path / "a.tar.gz.nottar", "x")


def test_read_label_names_handles_aal_tables(tmp_path):
    path = tmp_path / "labels.txt"
    path.write_text("1 Precentral_L 1\n2 Precentral_R 2\n35 Cingulate_Ant_L\n\nnot a row\n")
    assert read_label_names(path) == {1: "Precentral_L", 2: "Precentral_R", 35: "Cingulate_Ant_L"}


def planned(structure_id, source, value):
    s = Structure(structure_id, f"S{structure_id}", f"S{structure_id}", (structure_id,), (1, 2, 3))
    return PlannedStructure(s, (LabelRef(source, value),))


def test_mapping_and_source_values():
    plan = [planned(101, "a", 1), planned(102, "a", 2), planned(201, "b", 1)]
    assert mapping_for("a", plan) == {1: 101, 2: 102}
    image = nib.Nifti1Image(np.array([[[0, 1], [2, 2]]], dtype=np.int32), np.eye(4))
    assert source_values(image) == {1, 2}


def test_merge_maps_values_and_higher_priority_wins():
    grid_data = np.zeros((4, 4, 4), dtype=np.int32)
    grid_data[:2] = 1
    grid = nib.Nifti1Image(grid_data, np.eye(4))
    coarse = np.zeros((2, 2, 2), dtype=np.int32)
    coarse[0, 0, 0] = 7
    coarse_image = nib.Nifti1Image(coarse, np.diag([2.0, 2.0, 2.0, 1.0]))
    merged = merge(grid, [(2, coarse_image, {7: 70}), (1, grid, {1: 10})])
    assert merged.dtype == np.uint16 and merged.shape == (4, 4, 4)
    assert merged[0, 0, 0] == 70
    assert merged[0, 3, 3] == 10
    assert merged[3, 3, 3] == 0
    lower = merge(grid, [(0, coarse_image, {7: 70}), (1, grid, {1: 10})])
    assert lower[0, 0, 0] == 10


def test_interrupted_extraction_is_not_reused(tmp_path, monkeypatch):
    payload = b"x" * 4096
    archive = make_tar(tmp_path / "a.tar.gz", {"DIR/volume.nii": payload})
    spec = spec_for(archive, sha(archive.read_bytes()))
    cached = fetch(spec, tmp_path / "cache")

    def interrupted(src, dst, *args, **kwargs):
        dst.write(src.read(100))
        raise KeyboardInterrupt

    monkeypatch.setattr("tools.build_atlas.fetch.shutil.copyfileobj", interrupted)
    with pytest.raises(KeyboardInterrupt):
        member_path(spec, cached, "DIR/volume.nii")
    monkeypatch.undo()
    assert member_path(spec, cached, "DIR/volume.nii").read_bytes() == payload


def make_zip(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return path


def test_member_path_extracts_from_zip(tmp_path):
    archive = make_zip(tmp_path / "t.zip", {"colin.nii": b"template bytes"})
    spec = spec_for(archive, sha(archive.read_bytes()))
    cached = fetch(spec, tmp_path / "cache")
    assert member_path(spec, cached, "colin.nii").read_bytes() == b"template bytes"
    with pytest.raises(BuildError, match="not found"):
        member_path(spec, cached, "other.nii")


def test_labels_stored_with_a_tiny_scale_are_rounded(tmp_path):
    from tools.build_atlas.labels import load_label_image

    data = np.zeros((4, 4, 4), dtype=np.float32)
    data[1, 1, 1], data[2, 2, 2] = 1.0000152, 16.000244
    path = tmp_path / "scaled.nii.gz"
    nib.save(nib.Nifti1Image(data, np.eye(4)), path)
    image = load_label_image(path, name="scaled")
    assert sorted(np.unique(np.asarray(image.dataobj)).tolist()) == [0, 1, 16]
    data[3, 3, 3] = 2.4
    nib.save(nib.Nifti1Image(data, np.eye(4)), path)
    with pytest.raises(BuildError, match="not whole numbers"):
        load_label_image(path, name="scaled")


def test_a_label_image_with_a_single_volume_in_a_fourth_axis_becomes_3d(tmp_path):
    from tools.build_atlas.labels import load_label_image

    data = np.zeros((4, 4, 4, 1), dtype=np.int16)
    data[1, 1, 1, 0] = 3
    path = tmp_path / "four.nii.gz"
    nib.save(nib.Nifti1Image(data, np.eye(4)), path)
    image = load_label_image(path, name="four")
    assert image.shape == (4, 4, 4) and np.asarray(image.dataobj)[1, 1, 1] == 3
