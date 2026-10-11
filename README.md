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
| `C` | Centre the slice on the selection |
| `F1` | About, data sources and licences |
| `Q` | Start a quiz (Study menu) |
| `Ctrl+F` | Filter the structure tree (names, abbreviations, synonyms, atlas labels) |

Tree checkboxes show and hide structures; unticking a group hides its whole subtree. The info
panel shows the description with numbered references, the geometry source and its licence.
Entries marked **Draft** have not been reviewed yet. The Activity chart shows placeholder
data until a real model exists.

The **Slices** panel shows axial, coronal or sagittal cross-sections: coloured labels over the
Colin27 MRI template, in neurological convention (the patient's left on the screen's left,
with L/R, A/P and S/I letters on the edges). The slider moves the plane, which also appears
as a translucent sheet in the 3D view; the second slider sets label opacity. Hovering shows
the structure under the cursor, clicking selects it, and `C` (Centre slice) moves the plane
through the selected structure.

The **Study** menu starts a quiz (`Q`) or shows your progress. *Name it* highlights a
structure on both sides and asks for its name: type it (synonyms, abbreviations, any word
order and small typos count) or pick one of four. *Find it* names a structure and you click it
in 3D or in a slice. *Flashcards* show reviewed descriptions only. Choose single structures or
bigger groups, the whole atlas or one part of it, and either what is due now or a practice
round that leaves your schedule alone. Scheduling uses FSRS, the spaced repetition method Anki
uses, with at most 20 new items a day per mode. Progress is saved after every answer in
`~/.local/share/cns-atlas/progress.sqlite`. During a quiz the tree, the info panel and hover
names are hidden; `Esc` ends the quiz and restores the window.

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
| MRI template for slices | Colin 27 Average Brain (1998): Holmes CJ, Hoge R, Collins L, Woods R, Toga AW, Evans AC (1998), J Comput Assist Tomogr 22(2): 324-333, doi:10.1097/00004728-199803000-00032 | Permissive notice (text in `atlas_src/LICENSES/Colin27.txt`) |
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
| Desktop, 166 structures, integrated GPU | display refresh rate (144 Hz) |
| Terminal viewer, simulated drag at 200x60 | about 28 to 30 frames per second |

The 3D view draws every structure with one composite object and picks with the GPU, so it
scales to thousands of structures; it switches to a lighter level of detail when the scene
exceeds 3 million triangles. Budgets enforced by `pytest -m perf`: opening a 5,000-structure
atlas under 200 ms, search under 10 ms per keystroke, a slice under 5 ms. With the real atlas
built, `pytest -m slow` checks start to first frame under 2 s, app memory under 600 MB,
selection under 7 ms, a generated 3,500-structure scene at 60 fps or more, and quiz timing: a
quiz starts under 100 ms, moves to the next question under 50 ms and checks a typed answer
under 1 ms.

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
