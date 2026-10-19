from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

from cns_atlas import Atlas

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCAL_TAG = "local-not-for-sharing"
EXECUTABLE = "Mnemosyn.exe" if sys.platform == "win32" else "Mnemosyn"
APPIMAGETOOL = ("https://github.com/AppImage/appimagetool/releases/download/1.9.1/"
                "appimagetool-x86_64.AppImage")
APPIMAGETOOL_SHA256 = "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
INNO_SETUP = (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
              / "Inno Setup 6" / "ISCC.exe")


class PackageError(Exception):
    pass


def project_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def system_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise PackageError(f"packages are made on Windows or Linux, not on {sys.platform}")


def file_name(version: str, system: str, local: bool) -> str:
    tag = f"-{LOCAL_TAG}" if local else ""
    if system == "windows":
        return f"Mnemosyn-{version}{tag}-Setup.exe"
    return f"Mnemosyn-{version}{tag}-x86_64.AppImage"


def is_local(atlas: Path) -> bool:
    return bool(Atlas.open(atlas).local_only)


def check(atlas: Path, local: bool) -> None:
    if local and os.environ.get("GITHUB_ACTIONS") == "true":
        raise PackageError("--local packages are never made on GitHub Actions")
    if not (atlas / "metadata.json").exists():
        return
    if is_local(atlas) and not local:
        raise PackageError(f"{atlas} is a local build; add --local to package it for your own "
                           "machines")
    if local and not is_local(atlas):
        raise PackageError(f"{atlas} is a shareable build; build it with --local first")


def build_atlas(src: Path, out: Path, local: bool, log) -> None:
    from tools.build_atlas.build import build

    build(src, out, local=local, log=log)


def ensure_atlas(atlas: Path, local: bool, log) -> None:
    if not (atlas / "metadata.json").exists():
        log(f"building the atlas into {atlas}")
        build_atlas(ROOT / "atlas_src", atlas, local, log)


def bundle(atlas: Path, work: Path, version: str, log) -> Path:
    import PyInstaller.__main__

    (work / "VERSION").write_text(version + "\n", encoding="utf-8")
    os.environ["MNEMOSYN_ATLAS"] = str(atlas.resolve())
    os.environ["MNEMOSYN_VERSION_FILE"] = str(work / "VERSION")
    log("bundling with PyInstaller")
    PyInstaller.__main__.run([str(HERE / "mnemosyn.spec"), "--noconfirm", "--log-level", "WARN",
                              "--distpath", str(work / "dist"), "--workpath",
                              str(work / "build")])
    return work / "dist" / "Mnemosyn"


def _download_appimagetool(log) -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mnemosyn"
    tool = cache / "appimagetool-1.9.1-x86_64.AppImage"
    if not tool.exists():
        log("downloading appimagetool")
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(APPIMAGETOOL) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != APPIMAGETOOL_SHA256:
            raise PackageError("appimagetool download does not match its pinned checksum")
        tool.write_bytes(data)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def wrap_linux(folder: Path, target: Path, log) -> Path:
    appdir = folder.parent / "Mnemosyn.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(folder, appdir)
    run = appdir / "AppRun"
    run.write_text('#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/Mnemosyn" "$@"\n',
                   encoding="utf-8")
    run.chmod(0o755)
    shutil.copy(HERE / "mnemosyn.desktop", appdir / "mnemosyn.desktop")
    shutil.copy(HERE / "mnemosyn.png", appdir / "mnemosyn.png")
    log("making the AppImage")
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(_download_appimagetool(log)), "--no-appstream", str(appdir), str(target)],
                   env=env, check=True, capture_output=True)
    return target


def wrap_windows(folder: Path, target: Path, version: str, log) -> Path:
    compiler = shutil.which("iscc") or (str(INNO_SETUP) if INNO_SETUP.exists() else None)
    if compiler is None:
        raise PackageError("Inno Setup 6 is not installed; install it from jrsoftware.org")
    log("making the installer")
    subprocess.run([compiler, f"/DAppVersion={version}", f"/DSourceDir={folder}",
                    f"/DOutputDir={target.parent}", f"/DOutputName={target.stem}",
                    f"/DIconFile={HERE / 'mnemosyn.ico'}", str(HERE / "mnemosyn.iss")],
                   check=True, capture_output=True)
    return target


def package(atlas: Path, out: Path, local: bool, log=print, wrap: bool = True) -> Path:
    system = system_name()
    check(atlas, local)
    ensure_atlas(atlas, local, log)
    check(atlas, local)
    version = project_version()
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="mnemosyn-package-", dir=out))
    folder = bundle(atlas, work, version, log)
    if not wrap:
        return folder
    target = out / file_name(version, system, local)
    target.unlink(missing_ok=True)
    if system == "windows":
        wrap_windows(folder, target, version, log)
    else:
        wrap_linux(folder, target, log)
    shutil.rmtree(work, ignore_errors=True)
    log(f"made {target} ({target.stat().st_size / 1e6:.0f} MB)")
    return target
