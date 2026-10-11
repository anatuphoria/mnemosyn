from __future__ import annotations

import hashlib
import shutil
import ssl
import tarfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .recipe import BuildError, SourceSpec

DEFAULT_CACHE = Path.home() / ".cache" / "cns-atlas" / "sources"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(spec: SourceSpec, target: Path) -> None:
    url = urlparse(spec.download)
    if url.scheme in ("", "file"):
        shutil.copyfile(Path(url.path), target)
        return
    context = ssl.create_default_context()
    if not spec.verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(spec.download, context=context, timeout=60) as response:
        with target.open("wb") as out:
            shutil.copyfileobj(response, out)


def fetch(spec: SourceSpec, cache: Path = DEFAULT_CACHE) -> Path:
    folder = Path(cache) / spec.sha256
    archive = folder / Path(urlparse(spec.download).path).name
    if archive.exists() and sha256_of(archive) == spec.sha256:
        return archive
    folder.mkdir(parents=True, exist_ok=True)
    partial = archive.with_name(archive.name + ".part")
    try:
        _download(spec, partial)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise BuildError([f"source {spec.source.id}: download failed: {exc}"]) from exc
    actual = sha256_of(partial)
    if actual != spec.sha256:
        partial.unlink()
        raise BuildError([f"source {spec.source.id}: checksum mismatch "
                          f"(expected {spec.sha256}, got {actual})"])
    partial.replace(archive)
    return archive


def member_path(spec: SourceSpec, archive: Path, member: str) -> Path:
    if not member:
        return archive
    target = archive.parent / "extracted" / member
    if target.exists():
        return target
    if not archive.exists() or not tarfile.is_tarfile(archive):
        raise BuildError([f"source {spec.source.id}: {archive.name} is not a tar archive"])
    with tarfile.open(archive) as tar:
        try:
            info = tar.getmember(member)
        except KeyError as exc:
            raise BuildError([f"source {spec.source.id}: {member} not found in "
                              f"{archive.name}"]) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        with tar.extractfile(info) as src, partial.open("wb") as out:
            shutil.copyfileobj(src, out)
    partial.replace(target)
    return target
