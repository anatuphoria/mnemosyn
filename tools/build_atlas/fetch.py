from __future__ import annotations

import hashlib
import shutil
import ssl
import tarfile
import urllib.request
import zipfile
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
    with (urllib.request.urlopen(spec.download, context=context, timeout=60) as response,
          target.open("wb") as out):
        shutil.copyfileobj(response, out)


def manual_target(spec: SourceSpec, cache: Path) -> Path:
    return Path(cache) / spec.sha256 / Path(spec.download).name


def missing_manual(specs, cache: Path, manual_dir: Path | None = None) -> list[str]:
    problems = []
    for spec in specs:
        if not spec.manual:
            continue
        target = manual_target(spec, cache)
        given = Path(manual_dir) / target.name if manual_dir else None
        if not target.exists() and not (given and given.exists()):
            problems.append(f"source {spec.source.id}: download {target.name} from "
                            f"{spec.source.url} and put it in {target.parent}")
    return problems


def _checked(spec: SourceSpec, path: Path) -> None:
    actual = sha256_of(path)
    if actual != spec.sha256:
        raise BuildError([f"source {spec.source.id}: checksum mismatch "
                          f"(expected {spec.sha256}, got {actual})"])


def fetch(spec: SourceSpec, cache: Path = DEFAULT_CACHE, manual_dir: Path | None = None) -> Path:
    if spec.manual:
        target = manual_target(spec, cache)
        given = Path(manual_dir) / target.name if manual_dir else None
        if target.exists() and sha256_of(target) == spec.sha256:
            return target
        if given is not None and given.exists():
            _checked(spec, given)
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            shutil.copyfile(given, partial)
            partial.replace(target)
            return target
        if target.exists():
            raise BuildError([f"source {spec.source.id}: {target} does not match its checksum; "
                              f"delete it and download {target.name} again from "
                              f"{spec.source.url}"])
        raise BuildError(missing_manual([spec], cache, manual_dir))
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
    name = spec.source.id
    missing = BuildError([f"source {name}: {member} not found in {archive.name}"])
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if archive.exists() and tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tar:
            try:
                info = tar.getmember(member)
            except KeyError as exc:
                raise missing from exc
            with tar.extractfile(info) as src, partial.open("wb") as out:
                shutil.copyfileobj(src, out)
    elif archive.exists() and zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zipped:
            if member not in zipped.namelist():
                raise missing
            with zipped.open(member) as src, partial.open("wb") as out:
                shutil.copyfileobj(src, out)
    else:
        raise BuildError([f"source {name}: {archive.name} is not a tar or zip archive"])
    partial.replace(target)
    return target
