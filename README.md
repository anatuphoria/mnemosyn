# CNS Atlas

A 3D atlas of the human central nervous system for studying: a desktop app, a terminal
viewer, and the tool that builds the atlas data from open, cited sources.

> **Disclaimer.** This atlas is a personal study project. It was not built or reviewed by a
> neuroanatomy specialist and may contain errors. It is not for diagnosis or treatment.
> Corrections and feedback are welcome.

## Quickstart

```bash
python -m venv .venv
.venv/bin/pip install -e ".[desktop,atlas-build,dev]"
.venv/bin/python -m tools.build_atlas    # downloads AAL3 (1.5 MB) and builds atlases/cns (about 15 s)
.venv/bin/cns-desktop                    # desktop app
.venv/bin/brain-tui                      # terminal viewer
```

On hybrid-GPU laptops, `prime-run .venv/bin/cns-desktop` uses the discrete GPU.

## Desktop app

Drag rotates, right-drag or the wheel zooms, middle- or shift-drag pans, a click selects.

| Key | Action |
|---|---|
| `H` | Hide the selection (a group hides everything inside it) |
| `I` | Isolate the selection |
| `U` | Show all |
| `R` | Reset the view |
| `F1` | About, data sources and licences |
| `Ctrl+F` | Filter the structure tree (names, abbreviations, synonyms, atlas labels) |

Tree checkboxes show and hide structures; unticking a group hides its whole subtree. The info
panel shows the description with numbered references, the geometry source and its licence.
Entries marked **Draft** have not been reviewed yet. The Activity chart shows placeholder
data until a real model exists.

## Terminal viewer

`brain-tui [--atlas PATH]` reads the same atlas package and falls back to a 36-region
procedural brain when no atlas is built. Letters are lowercase unless written with `Shift+`.

| Action | Keys |
|---|---|
| Rotate | arrows / `hjkl` or mouse-drag |
| Zoom / Pan | `+`/`-`, `wasd` or wheel / shift+drag |
| Spin | `r` |
| Select | click, `Tab` / `Shift+Tab`, `/` search (`Enter` commits, `Esc` cancels) |
| Move selected | `m` move-mode: arrows or `wasd`, `PgUp`/`PgDn` depth, `Esc` exits |
| Isolate / Hide / Unhide | `i` / `Shift+H` / `u` |
| Explode | `x` / `Shift+X` |
| Slice axial/coronal/sagittal | `1` / `2` / `3`, `,`/`.` move plane |
| Labels | `Shift+L` |
| Bookmark save/restore | `b` / `Shift+B` |
| HiFi stills / Quiz | `o` / `z` (`z` again reveals the answer) |
| Help | `?` |

## Atlas data

| Data | Source | Licence |
|---|---|---|
| Brain geometry, 166 structures | AAL3: Rolls ET, Huang CC, Lin CP, Feng J, Joliot M (2020), NeuroImage 206: 116189, doi:10.1016/j.neuroimage.2019.116189 | GNU General Public License (text in `atlases/cns/LICENSES/`) |
| Descriptions | Written for this project; every claim cites a reference | CC BY 4.0 |
| Code | This repository | Not chosen yet |

The atlas package (`atlases/cns/`, built locally, not committed) contains `metadata.json`,
`structures.json`, `sources.json`, `collections.json`, `pathways.json`, a labelled volume in
`volumes/`, packed meshes at three levels of detail in `meshes/`, and descriptions in
`knowledge/`. The format is described in `docs/specs/2026-10-11-atlas-foundation-design.md`.

To change the atlas, edit `atlas_src/` and rebuild:

- `structures.toml`: the hierarchy, ids, names, synonyms and source labels. Ids never change
  and are never reused; `ids.lock` records every published id.
- `knowledge/en/<id>.md`: one description per concept, with `status = "draft"` or
  `"reviewed"`, citing keys from `knowledge/references.toml`.
- `recipe.toml`: sources with pinned checksums and licences.

The build refuses to package a source without a redistribution licence, a description that
cites a missing reference, a reference without a DOI, URL or ISBN, a changed or reused id,
or a labelled structure without voxels.

## Performance

| Measure | Result |
|---|---|
| Desktop, 166 structures, integrated GPU | display refresh rate (144 Hz), about 1.4 ms GPU time per frame |
| Terminal viewer, simulated drag at 200x60 | about 28 to 30 frames per second |

Budgets enforced by `pytest -m perf`: opening a 5,000-structure atlas under 200 ms, search
under 10 ms per keystroke, selection to all panels under 7 ms. With the real atlas built,
`pytest -m slow` also checks start to first frame under 2 s and memory under 500 MB.

## Tests

```bash
.venv/bin/python -m pytest            # fast suite
.venv/bin/python -m pytest -m slow    # downloads AAL3, builds the real atlas, checks budgets
```

## Layout

```
cns_atlas/          atlas package loader (no Qt): model, meshes, knowledge, volume, atlas
cns_desktop/        desktop app: app, main_window, state, views/
brain_tui/          terminal viewer
tools/build_atlas/  atlas build tool: recipe, hierarchy, validate, fetch, labels, meshing, writer
atlas_src/          committed atlas sources: recipe, structures, ids.lock, knowledge, LICENSES
docs/               specs and plans
tests/
```
