# Packaging: downloads for Windows and Linux (sub-project F)

Date: 2026-10-19
Status: approved by the owner on 2026-10-19
Branch: `packaging`, merged into `main` when the first test release works

## 1. Why

Today only someone who can install Python and build the atlas can use Mnemosyn. Students need a
download that opens like any other app. The owner also needs a full package, with the sources not
yet cleared for sharing, to test on his own other machines.

## 2. What is built (decided by the owner)

- **Windows and Linux only.** No macOS version (owner's choice: Apple's paid signing is out, and an
  unsigned Mac app is too awkward to open on current macOS).
- **No code signing for now.** This is a test version, not production. Windows shows SmartScreen
  on first launch ("More info", then "Run anyway"); some antivirus programs may flag the unsigned
  app. Signing (for example the free SignPath Foundation programme) is for later and must be a
  step that can be switched on without changing the rest.
- **Two kinds of package:**
  - **Shared test release** (public): built by GitHub Actions from a version tag, with the
    shareable atlas only (no PAM50 spinal cord, glands, Brainstem Navigator or Iglesias bodies).
    Published on GitHub Releases as a pre-release.
  - **Full local package** (the owner's own machines only): built on the owner's computer with
    the local atlas, never uploaded to GitHub, never attached to a release, never offered on the
    website. The local-only rule changes from "never packaged" to "never shared" (decision log).

## 3. The packages

| | Windows | Linux |
|---|---|---|
| File | `Mnemosyn-<version>-Setup.exe` | `Mnemosyn-<version>-x86_64.AppImage` |
| Full local file | `Mnemosyn-<version>-local-not-for-sharing-Setup.exe` | `Mnemosyn-<version>-local-not-for-sharing-x86_64.AppImage` |
| Starts with | an installer: Start menu entry, uninstaller, no admin rights needed (per-user install) | one file: mark it runnable and open it |

- Each contains Python, Qt, VTK, Mnemosyn's code and the atlas, so nothing else is needed.
- Quiz progress stays in each system's per-user data folder (as today), so it survives updates
  and uninstalling.
- The full local package shows "local build, not for sharing" in the window title and the About
  box, as local builds already do.
- While the version is below 1.0 the About box and the Download page call it a test version.

## 4. One command

`python -m tools.package` builds the package for the system it runs on, from the atlas in
`atlases/cns` (building it first if it is missing); `--local` makes the full local package and
refuses to run on GitHub Actions. The same command is used by the release workflow, on the owner's
Linux laptop and on a Windows machine. Builder's call: the bundling tool (PyInstaller is the
expected choice for PySide6 and VTK), Inno Setup for the Windows installer, appimagetool for the
AppImage.

## 5. Releases

- Pushing a tag `v<version>` (for example `v0.1.0`) runs a workflow with a Windows and a Linux job.
  Each builds the shareable atlas, packages the app, starts the packaged app once headless to check
  it reaches its first frame, and attaches the file and its SHA-256 checksum to a GitHub Release
  marked pre-release, with one `SHA256SUMS.txt` listing both files.
- The atlas build needs the Harvard Ascending Arousal Network atlas, which can only be downloaded
  by hand from Dryad. It is CC0, so the workflow fetches a copy kept as an asset of a dedicated
  GitHub release of this repository (builder's call how; the checksum pin stays).
- The version comes from `pyproject.toml`; the tag must match it or the workflow stops.

## 6. The website

- **Install** becomes **Download**: one button each for Windows and Linux, pointing at the files
  of the published version set in `site/download.toml` (set by hand once a release is published,
  so the buttons never point at files that do not exist yet; GitHub's "latest" link skips
  pre-releases); requirements (64-bit Windows 10 or later; a 64-bit Linux from 2022 or later;
  OpenGL 3.2 graphics); a link to the release page, which lists sizes and the checksums file; the
  first-launch steps; and one plain line that this is the shareable atlas. Today's developer
  quickstart moves to a "Build from source" section of the same page. While no version is set, the
  page says the first test version is coming soon.
- The home page's Install button and first "Start here" card point at the Download page with the
  same look; the layout does not change.

## 7. Instructions for the owner

`docs/packaging.md` (committed, linked from the README) explains:
- making the full local AppImage on Linux (one command);
- making the full local Windows installer on a Windows machine, step by step: installing Python
  and Inno Setup, getting the code, installing the dependencies, copying the hand-downloaded
  sources (Harvard arousal atlas, Brainstem Navigator) into the source cache, building the local
  atlas, running the package command, and where the installer appears;
- making a public release (bump the version, tag, push).

The builder checks the Windows steps as far as possible without a Windows machine; the first real
run on the owner's Windows machine is their test.

## 8. Limits

- Each download under 600 MB.
- A release workflow finishes within 30 minutes.
- The packaged app reaches its first frame within 3 seconds on the owner's laptop (2 s when run
  from source today); its own memory stays under the existing 400 MB limit.
- Every existing test still passes from source; a smoke test runs the packaged app on both
  systems in the workflow.

## 9. Out of scope

macOS; code signing; automatic updates (students download a new version from the website);
installing through package managers (winget, Flathub); the terminal viewer.

## 10. Decisions to log

Windows and Linux only; unsigned test releases; local-only sources may be packaged for the owner's
own machines but never shared; releases from version tags as pre-releases below 1.0.
