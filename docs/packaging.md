# Packaging Mnemosyn

`python -m tools.package` packages the app for the system it runs on: a Windows installer on
Windows, an AppImage on Linux, a disk image on an Apple Silicon Mac. It bundles Python, Qt, VTK, the code and the atlas in
`atlases/cns`, so the result needs nothing else. The files appear in `dist/`.

There are two kinds of package:

- **Shareable** (`python -m tools.package`): the atlas built without `--local`. Public test
  releases are made this way by GitHub Actions; see "A public release" below.
- **Full local** (`python -m tools.package --local`): the atlas built with `--local`, including
  sources whose authors have not yet allowed sharing (PAM50, the Brainstem Navigator, the
  Iglesias bodies, the pituitary and pineal masks). Its file name says `local-not-for-sharing`.
  It is for your own machines only: never upload it, attach it to a release, or give it to anyone.
  The command refuses to run on GitHub Actions.

The command checks that the atlas matches the kind you ask for, and builds the atlas first if
`atlases/cns` is missing.

## Full local AppImage on Linux

From the project folder, with the development setup from the README and the packaging extra:

```bash
.venv/bin/pip install -e ".[desktop,atlas-build,package]"
.venv/bin/python -m tools.build_atlas --local      # if atlases/cns is not a local build yet
.venv/bin/python -m tools.package --local
```

The result is `dist/Mnemosyn-<version>-local-not-for-sharing-x86_64.AppImage` (about 400 MB). It
runs on Linux machines with the same or a newer system library version as the one it was built
on; copy it to your other machines, `chmod +x` it and open it.

## Full local installer on Windows

You need a 64-bit Windows 10 or 11 machine and about 5 GB of free space.

1. Install **Python 3.14** from https://www.python.org/downloads/windows/ (64-bit installer).
   On the first screen tick **Add python.exe to PATH**.
2. Install **Git** from https://git-scm.com/download/win (the default choices are fine).
3. Install **Inno Setup 6** from https://jrsoftware.org/isdl.php (the default choices are fine).
4. Open **PowerShell** and get the code:

   ```powershell
   cd $HOME
   git clone https://github.com/anatuphoria/mnemosyn.git
   cd mnemosyn
   ```

5. Create the environment and install everything:

   ```powershell
   py -3.14 -m venv .venv
   .venv\Scripts\python -m pip install -e ".[desktop,atlas-build,package]"
   ```

6. Copy the two sources that cannot be downloaded by a script into one folder, for example
   `C:\mnemosyn-sources`:
   - `doi_10_5061_dryad_zw3r228d2__v20230718.zip` (the Harvard Ascending Arousal Network atlas);
     you can take it from the `sources` release on GitHub or from your Linux machine's
     `~/.cache/cns-atlas/sources/<checksum>/` folder.
   - `BrainstemNavigatorv1.0.zip` (the Brainstem Navigator), from your Linux machine's
     `~/.cache/cns-atlas/sources/<checksum>/` folder; it may not be uploaded anywhere.

7. Build the full atlas (it downloads the other sources itself; this takes several minutes):

   ```powershell
   .venv\Scripts\python -m tools.build_atlas --local --manual-dir C:\mnemosyn-sources
   ```

8. Make the installer:

   ```powershell
   .venv\Scripts\python -m tools.package --local
   ```

9. The installer is `dist\Mnemosyn-<version>-local-not-for-sharing-Setup.exe`. Run it on your
   Windows machines. Because it is not signed, Windows may say "Windows protected your PC": choose
   **More info**, then **Run anyway**. It installs for your account only, without administrator
   rights.

If a step fails, the message names what is missing; the most common causes are a Python version
other than 3.14, Inno Setup not installed, or a source file with a different name.

## A public release

1. Set the new version in `pyproject.toml` (for example `version = "0.2.0"`), run
   `python -m tools.brand` so the release badge shows it, commit both and push `main`.
2. Tag that commit and push the tag:

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. GitHub Actions builds the shareable package on Windows, Linux and macOS, opens each once to
   check it starts, and publishes a pre-release with the three files and `SHA256SUMS.txt`. The tag must match
   the version in `pyproject.toml`, or the workflow stops.
4. When the release is published, set `version = "0.2.0"` in `site/download.toml`, commit and push
   `main`. The website's Download buttons then point at the new files. They never point at a
   version before its files exist.

## The Mac package

The Mac package is `Mnemosyn-<version>-macOS-arm64.dmg`: a disk image holding `Mnemosyn.app` and a
link to the Applications folder. It runs on Apple Silicon Macs with macOS 14 or later (the
lowest version the bundled Qt and NumPy accept). It is built by GitHub Actions
on a Mac machine, because a Mac app can only be made on a Mac, and the owner has none.

The app is not signed with an Apple certificate (that needs a paid Apple Developer account). It
carries only the local signature that Apple Silicon requires to run anything, so macOS blocks it on
first open until the user chooses Open Anyway in System Settings, Privacy & Security.

Every release includes the Mac file, and the Download page offers it while `site/download.toml`
says `mac = true`. Until someone with a Mac has gone through `docs/mac-check.md`, the Mac card
carries a notice that it has not been checked on a real Mac (`MAC_NOTE` in `tools/build_site.py`);
remove the notice when the check has passed. To try a build before a release, run the Release workflow by hand and take the
`package-macOS` artifact.

## Library versions in a release

The release build installs the exact library versions listed in
`tools/package/requirements-release.txt`, so two builds of the same tag use the same libraries and a
new library version cannot enter a release unseen. The versions in that file fit each other as a
set, so one line must not be changed alone. Dependabot only proposes a change to it when a library
has a known security problem, and such a pull request needs the build check below before merging.
To refresh the whole set by hand:

```bash
pip install uv
uv pip compile pyproject.toml --extra desktop --extra atlas-build --extra package --universal \
  --python-version 3.14 --no-header --no-annotate -o tools/package/requirements-release.txt
```

After a change to that file, run the Release workflow by hand from the Actions page (it builds and
opens both packages without publishing) before tagging.
