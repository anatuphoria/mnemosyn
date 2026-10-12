# Pathway View Design (sub-project B, part 4: B4)

Date: 2026-10-12
Status: approved
Builds on: `docs/specs/2026-10-11-atlas-foundation-design.md` (A, which reserved
`pathways.json` and `knowledge/<lang>/pathway-<key>.md`), the B1 + B2, B3 and C1 specs

## 1. Context

B4 adds pathways: ordered routes through the nervous system that the person follows station by
station, with what each station does and what a lesion there causes.

Decisions made in discussion:

- First version teaches the route and lesions; pathway quiz questions come later.
- Display: the whole route stays visible and the current station is lit brightly; Back and
  Next move along it and the slice follows; clicking a step jumps to it.
- Sides: one side at a time with a Left / Right switch; lesion texts name the side of the
  deficit; crossings are steps of their own.
- Storage: a route file in `atlas_src/` plus one description file per pathway in the
  knowledge format, so texts carry references and a draft or reviewed status.
- All texts are drafts with references for the owner's doctor review.
- The spinal cord parts follow with C2; relays the atlas lacks are text-only steps.

## 2. The first eight pathways

Sides are relative to the pathway's start: `same`, `opposite` or `midline`. Crossing steps
(marked x) and relay steps (marked r) have no geometry.

| Key | Name | Start | Steps |
|---|---|---|---|
| `visual` | Visual pathway | eye | optic nerve 3370; x optic chiasm; LGN 1890; optic radiation 3350; calcarine cortex 1500 |
| `auditory` | Auditory pathway | ear | vestibulocochlear nerve 3440; r cochlear nuclei; x trapezoid body; lateral lemniscus 3250 (opposite); r inferior colliculus (opposite); MGN 1900 (opposite); acoustic radiation 3360 (opposite); Heschl gyrus 1610 (opposite) |
| `papez` | Papez circuit | hippocampus | hippocampus 1350; fornix 3340; mammillary body 2630; mammillothalamic tract 3400; anteroventral thalamus 1800; cingulum 3160; cingulate cortex 1330 and 1340; parahippocampal gyrus 1360; hippocampus 1350 |
| `motor` | Voluntary movement (corticospinal) | motor cortex | precentral gyrus 1000; corticospinal tract 3000; x pyramidal decussation; r lateral corticospinal tract in the spinal cord (opposite) |
| `touch` | Touch and position (dorsal column, medial lemniscus) | side of the body | r dorsal columns and gracile and cuneate nuclei; x internal arcuate fibres; medial lemniscus 3240 (opposite); VPL thalamus 1840 (opposite); postcentral gyrus 1700 (opposite) |
| `pain` | Pain and temperature (spinothalamic) | side of the body | r dorsal horn; x anterior white commissure; spinothalamic tract 3260 (opposite); VPL thalamus 1840 (opposite); postcentral gyrus 1700 (opposite) |
| `basal-ganglia` | Basal ganglia motor loop | motor cortex | supplementary motor area 1070; corticostriatal pathway 3050; putamen 1420; substantia nigra pars compacta 2010; globus pallidus 1430; VA and VL thalamus 1820 and 1830; corticothalamic pathway 3060; precentral gyrus 1000 |
| `cerebellar` | Cerebellar motor loop | motor cortex | precentral gyrus 1000; frontopontine tract 3010; r pontine nuclei; x middle cerebellar peduncle 3320 (midline); cerebellar hemisphere 41 (opposite); r dentate nucleus (opposite); x superior cerebellar peduncle 3330 (midline); red nucleus 2030; VL thalamus 1830; precentral gyrus 1000 |

All station ids exist in the current atlas with shapes on both sides (3320 and 3330 are
midline). A station may name several structures (cingulate cortex, VA and VL thalamus) and may
name a group (41): it lights every shape under it on the resolved side.

## 3. Source format

### 3.1 `atlas_src/pathways.toml`

```toml
[[pathways]]
key = "visual"
name = "Visual pathway"
start = "eye"
steps = [
  { structures = [3370] },
  { cross = "Optic chiasm" },
  { structures = [1890] },
  { structures = [3350] },
  { structures = [1500] },
]
```

- A step is exactly one of: `structures = [ids]` with optional `side = "same" | "opposite" |
  "midline"` (default `same`), `cross = "<name>"`, or `relay = "<name>"` with optional `side`.
- `key` is lowercase letters, digits and hyphens, unique.

### 3.2 `atlas_src/knowledge/en/pathway-<key>.md`

```text
+++
key = "pathway-visual"
status = "draft"
+++
## Overview
...
## Step 1
Role: ...
Lesion: a lesion of the {same} optic nerve causes blindness in the {same} eye [purves2018].
## Step 2
...
```

- Sections: `Overview`, then `Step 1` to `Step N` matching the route's N steps exactly.
- Every step section has one `Role:` line and one `Lesion:` line; citations as in A.
- `{same}` and `{opposite}` are replaced with "left" or "right" for the chosen side.

## 4. Build and package

- The build reads `pathways.toml` and writes `pathways.json`:
  `[{"key", "name", "start", "steps": [{"structures": [...], "side": ...} | {"cross": name} |
  {"relay": name, "side": ...}]}]`. No package ever contained pathways, so the record layout
  changes freely; `format_version` stays 1.
- The knowledge loader accepts `Overview` and `Step N` sections for `pathway-` keys only.
- Build errors, each naming the pathway and step: unknown structure id; a structure or group
  with no shape on either side for a sided step; unknown side; a step that is not exactly one
  kind; a duplicate key; a description file whose steps do not match the route; a step
  section without one Role and one Lesion line; a citation of an unknown reference; a missing
  description file.

## 5. Loader

- `cns_atlas.Pathway(key, name, start, steps)` with step kinds `Station(structures, side)`,
  `Crossing(name)`, `Relay(name, side)`.
- `Atlas.pathways` (tuple, may be empty) and `Atlas.pathway_text(key, side) -> PathwayText |
  None` with `overview` and per-step `role`, `lesion`, references, status, side words filled
  in for `side` in (`left`, `right`).
- `resolve(atlas, step, start_side) -> tuple[int, ...]`: the shape ids a station lights for
  the chosen start side (same, opposite or midline leaves under the listed ids).

## 6. Desktop

### 6.1 Panel

- A Pathways dock tabbed with the Structures dock lists the pathways (empty note when the atlas
  has none).
- Choosing a pathway enters pathway mode. The panel shows the name, a Left / Right switch, a
  Draft label while the description is a draft, the numbered steps (stations, crossings marked
  with a cross, relays greyed), the current step's Role, Lesion and references, and Back and
  Next buttons; the Left and Right arrow keys step while the panel has focus; clicking a step
  jumps to it. Esc or "Leave pathway" leaves.

### 6.2 Views

- 3D: every structure that is not a station on the chosen side is drawn faint (block opacity
  0.08) and is not pickable; route stations keep full colour; route tracts are shown and all
  other tracts hidden; the current station gets the selection highlight, so the info panel shows
  its description. The camera does not move on its own.
- Slices: only route structures are coloured; the slice moves through the current station
  (Centre on selection). Crossings and relays light nothing and leave the slice where it is.
- Entering saves visibility, opacity, selection and slice; leaving restores them exactly.
  Starting a quiz leaves pathway mode first; quiz and pathway mode never run together.

### 6.3 Budgets

| Measure | Budget |
|---|---|
| Enter a pathway or switch side | under 100 ms |
| Move one step | under 30 ms |
| First frame and memory | unchanged (under 2 s, under 600 MB) |

## 7. Testing

- Build on the toy atlas with two small pathways: parsing, side resolution, crossings and
  relays, description matching, each build error of section 4.
- Loader: pathways and steps, side words for left and right, `resolve` for same, opposite,
  midline and groups.
- Desktop: entering dims the rest and lights the route on the chosen side; stepping
  highlights and moves the slice; the side switch updates lights and texts; crossings and
  relays light nothing; leaving restores; a quiz leaves pathway mode first.
- Real atlas (slow): the eight pathways load and every station lights shapes on both sides;
  the budgets of section 6.3.

## 8. Scope

In scope: sections 2 to 7, and draft descriptions with references for the eight pathways.

Out of scope: pathway quiz questions, spinal cord segments (C2), animated flow along a
route, pathways in the terminal app.
