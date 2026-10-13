# Mnemosyn

A 3D atlas of the human central nervous system for studying: a desktop app, a terminal
viewer, and the tool that builds the atlas data from open, cited sources.

The name joins Mnemosyne, the Greek goddess of memory, with the synapse, where memories are
stored: an atlas of the brain that helps you remember it.

> **Disclaimer.** This atlas is a personal study project. It was not built or reviewed by a
> neuroanatomy specialist and may contain errors. It is not for diagnosis or treatment.
> Corrections and feedback are welcome.

## Quickstart

```bash
python -m venv .venv
.venv/bin/pip install -e ".[desktop,atlas-build,dev]"
.venv/bin/python -m tools.build_atlas    # downloads the open atlases and builds atlases/cns (about 40 s)
.venv/bin/python -m tools.build_atlas --local    # also adds sources not yet allowed to be shared
.venv/bin/mnemosyn                       # desktop app
.venv/bin/brain-tui                      # terminal viewer
```

On hybrid-GPU laptops, `prime-run .venv/bin/mnemosyn` uses the discrete GPU.

## Desktop app

Drag rotates, right-drag or the wheel zooms, middle- or shift-drag pans, a click selects.

| Key | Action |
|---|---|
| `H` | Hide the selection (a group hides everything inside it) |
| `I` | Isolate the selection |
| `U` | Show all |
| `T` | Show or hide all tracts |
| `R` | Reset the view |
| `C` | Centre the slice on the selection |
| `F1` | About, data sources and licences |
| `Q` | Start a quiz (Study menu) |
| `Left` / `Right` | Previous or next step of a pathway (Pathways panel) |
| `Esc` | Leave the pathway, or end a quiz |
| `Space` | Play or pause the current pathway (Pathways or Activity panel) |
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
`~/.local/share/mnemosyn/progress.sqlite`. During a quiz the tree, the info panel and hover
names are hidden; `Esc` ends the quiz and restores the window.

**Tracts** (43 white-matter pathways: 41 from the HCP-1065 atlas, among them the
corticospinal tract, the lemnisci, the cerebellar peduncles and seven cranial nerves, and the
mammillothalamic tract and inferior thalamic peduncle from the hypothalamus atlas) are hidden
when the app opens. `T` shows or hides them all, the tree shows single tracts, and selecting a
tract shows it. In slices, visible tracts are outlined in their colour, and hovering or
clicking where tracts overlap picks the smallest. Quizzes have a Tracts level of their own;
while a tract is named, the grey matter around it is dimmed.

The **Pathways** panel, a tab next to Structures, follows routes station by station in two
groups. Sensory and motor: the visual and auditory pathways, the Papez circuit, voluntary
movement, touch and position, pain and temperature, and the basal ganglia and cerebellar motor
loops. Behaviour: the dopamine, serotonin, noradrenaline and acetylcholine systems, the fear
circuit, the stress axis, the body clock, hunger, memory, and decision and self-control.
For a sensory or motor route, choose a pathway and a start side (Left or Right): everything
off the route fades and cannot be clicked, the route's tracts are shown, and the current
station is highlighted with its role and the effect of a lesion there, with references. Back
and Next in the Activity panel (or the arrow keys) move along the route and the slice
follows; crossings and relays the atlas has no shape for are steps of their own. Leaving
(`Esc` or the Leave button) restores the view as it was. Behaviour routes light both sides and
show, for each step, its role, the disorders linked to it and the drugs that act there.

While a pathway is open, the Activity panel holds the playback controls: Back, Play / Pause,
Next, a speed choice (½×, 1×, 2×) and the current step. Play (`Space`) steps through a route on
its own; the stress axis, body clock and hunger routes also play a schematic hormone timeline
in the chart, where a cursor follows the steps, the time is shown next to the controls, and a
click in the plot jumps to that moment. All pathway texts and timelines are drafts awaiting
review.

## Terminal viewer

`brain-tui [--atlas PATH]` reads the same atlas package and falls back to a 36-region
procedural brain when no atlas is built (a `--atlas` path that does not exist is an error).
Descriptions show numbered citations with their references, and drafts are marked. Letters are lowercase unless written with `Shift+`.

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
| Brain geometry, 166 structures | AAL3: Rolls ET, Huang CC, Lin CP, Feng J, Joliot M (2020), NeuroImage 206: 116189, doi:10.1016/j.neuroimage.2019.116189 | GNU General Public License (text in `atlas_src/LICENSES/GPL-3.0.txt`) |
| Hypothalamic region, 21 structures | Neudorfer C, Germann J, Elias GJB, Gramer R, Boutet A, Lozano AM (2020), Scientific Data 7: 305, doi:10.1038/s41597-020-00644-6 | CC BY 4.0 (notice in `atlas_src/LICENSES/CC-BY-4.0.txt`) |
| Tracts, 41 | HCP-1065 tractography atlas: Yeh FC et al. (2018), NeuroImage 178: 57-68, doi:10.1016/j.neuroimage.2018.05.027 | CC BY-SA 4.0 (notice in `atlas_src/LICENSES/CC-BY-SA-4.0.txt`) |
| Pituitary gland (local builds only) | Tang K (2024), pituitary mask on the MNI ICBM152 2009a template, github.com/kvttt/Pituitary_Segmentation | No licence stated; used only in local builds until the author allows sharing |
| Pineal gland (local builds only) | Razavi F, Raminfard S, Kalantar Hormozi H, Sisakhti M, Batouli SAH (2021), Frontiers in Neuroinformatics 15: 554229, doi:10.3389/fninf.2021.554229 | No licence stated for the atlas files; used only in local builds until the authors allow sharing |
| Brainstem arousal nuclei, 6 structures | Harvard Ascending Arousal Network Atlas 2.0: Edlow BL, Kinney HC (2023), Dryad, doi:10.5061/dryad.zw3r228d2 (downloaded by hand) | CC0 1.0 (notice in `atlas_src/LICENSES/CC0-1.0.txt`) |
| Dentate and interposed nuclei | Diedrichsen J, Balsters JH, Flavell J, Cussans E, Ramnani N (2009), NeuroImage 46: 39-46, doi:10.1016/j.neuroimage.2009.01.045; nuclei from Diedrichsen J, Maderwald S, Küper M et al. (2011), NeuroImage 54: 1786-1794, doi:10.1016/j.neuroimage.2010.10.035 | CC BY (notice in `atlas_src/LICENSES/CC-BY-Diedrichsen.txt`) |
| Cochlear nuclei, superior olivary complex, inferior colliculus | Sitek KR, Gulban OF et al. (2019), eLife 8: e48932, doi:10.7554/eLife.48932 | BSD 3-Clause (text in `atlas_src/LICENSES/BSD-3-Clause-Sitek.txt`) |
| Ten brainstem nuclei (local builds only) | Brainstem Navigator v1.0, Bianciardi lab, doi:10.25790/bml0cm.96 (downloaded by hand) | Non-commercial, no sharing outside the organisation; used only in local builds until the authors allow sharing |
| MRI template for slices | Colin 27 Average Brain (1998): Holmes CJ, Hoge R, Collins L, Woods R, Toga AW, Evans AC (1998), J Comput Assist Tomogr 22(2): 324-333, doi:10.1097/00004728-199803000-00032 | Permissive notice (text in `atlas_src/LICENSES/Colin27.txt`) |
| Descriptions | Written for this project; every claim cites a reference | CC BY 4.0 |
| Code | This repository | GNU General Public License v3.0 or later (`LICENSE`) |

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
- `pathways.toml`: the routes, one step per station, crossing or relay, with the side of each
  station relative to the start (`same`, `opposite` or `midline`).
- `knowledge/en/pathway-<key>.md`: one description per route with an Overview and one
  `Step N` section per step, each with one `Role:` and one `Lesion:` line; `{same}` and
  `{opposite}` become "left" or "right". Behaviour routes (`sides = "both"`,
  `texts = "behaviour"`) use one `Role:`, one `Disorders:` and at most one `Drugs:` line.
- `timelines/<route>.toml`: a schematic hormone timeline for a route: curves of relative level
  over time and marks that tie moments to steps.

The build refuses to package a source without a redistribution licence, a description that
cites a missing reference, a reference without a DOI, URL or ISBN, a changed or reused id,
a labelled structure without voxels, or a pathway with an unknown structure, a station with
no shape on a side, or a description that does not match its route.

A source whose authors have not yet allowed sharing can be marked `local_only = true` in
`recipe.toml`. A normal build leaves it out, so the result can be shared; `--local` includes it,
and the app then shows "local build, not for sharing" in its title and About box. Such a
package must never be published or bundled into an installer.

Some sources cannot be downloaded by a script and are marked `manual = true`. The build then
stops and names the page to download each file from and the folder to put it in
(`~/.cache/cns-atlas/sources/<checksum>/`); `--manual-dir <folder>` takes them from a folder
instead. Every build needs the Harvard Ascending Arousal Network Atlas (CC0, from Dryad); only
`--local` needs the Brainstem Navigator (from NITRC, after accepting its licence).

## Performance

| Measure | Result |
|---|---|
| Desktop, 166 structures, integrated GPU | display refresh rate (144 Hz) |
| Terminal viewer, simulated drag at 200x60 | about 28 to 30 frames per second |

The 3D view draws every structure with one composite object and picks with the GPU, so it
scales to thousands of structures; it switches to a lighter level of detail when the scene
exceeds 3 million triangles. Budgets enforced by `pytest -m perf`: opening a 5,000-structure
atlas under 200 ms, search under 10 ms per keystroke, a slice under 5 ms. With the real atlas
built, `pytest -m slow` checks start to first frame under 2 s, the app's own memory under
400 MB (shared libraries such as Qt and VTK not counted, since how much of them is resident
depends on what the system has cached), selection under 7 ms, a generated 3,500-structure scene at 60 fps or more, and quiz timing: a
quiz starts under 100 ms, moves to the next question under 50 ms and checks a typed answer
under 1 ms. Tracts are built the first time they are shown (under 500 ms), then show or hide
in under 50 ms; a slice with every tract outlined redraws in under 10 ms. Entering a pathway
or switching its side takes under 100 ms, a step under 30 ms, and a playing timeline updates
in under 5 ms per tick.

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
