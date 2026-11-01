# Lesion mode

Date: 2026-11-01
Status: approved by the owner in conversation on 2026-11-01 (layout A of the mockups)
Builds on: the pathways and their texts (decisions 19 to 21, `atlas_src/pathways.toml`,
`atlas_src/knowledge/en/pathway-*.md`), the workspaces (decision 65), the design system (decisions
67 to 71), the roadmap's first idea

## 1. Why

Neuroanatomy is examined through one skill above all: localization. A patient shows these signs,
so where is the lesion, and why does it cause them? Mnemosyn shows the parts and plays the routes,
but does not let anyone reason with them. The owner chose lesion mode as a main feature: the
features that must exist before the work turns to enhancements and fixes and the handbook is
written (roadmap, "Handbook").

## 2. Goals, non goals, what would make it fail

Goals:

1. Place a lesion and see which structures it hits, how much of each, and which deficits follow,
   each deficit explained from the route it breaks, with sources.
2. Cases: the app describes a patient's signs, the user places a lesion, and the app compares,
   sign by sign.
3. Deficits come only from cited route texts, never from a hidden table. What the atlas cannot
   support is said plainly.
4. Every route gained later adds deficits without new code.

Non goals: diagnosis or anything presented as clinical advice (the app's learning notice applies);
medullary syndromes that need cranial nerve nuclei the atlas does not have (Wallenberg and the
like), until such data exist; saving lesions to files; scheduling cases with spaced repetition;
changes to the Lab, the quizzes or the routes themselves.

It fails if a deficit is ever shown without the route step and source behind it, if a case's signs
contradict what its own lesion causes, if the lesion or its results draw over other regions, or if
a public build shows something that needs a local only source.

## 3. Data

1. **Lesion.** A set of voxels per labelled volume: the brain labels volume (MNI152, 1 mm) and, in
   local builds, the spine volume (PAM50). Tracts are matched through their voxels in the brain
   grid (`cns_atlas/tracts.py`).
2. **Arterial territories.** Liu and colleagues, "Digital 3D Brain MRI Arterial Territories
   Atlas", Scientific Data 2023 (doi 10.1038/s41597-022-01923-0), MNI152 version from NITRC
   (`nitrc.org/projects/arterialatlas`). A new source in `atlas_src/recipe.toml`, pinned by checksum,
   resampled to the brain grid, with territories as a new structure group "Arterial territories"
   (left and right of each level 1 territory under its level 2 artery: ACA, MCA, PCA,
   vertebrobasilar). Its page lists an attribution licence without a version; the label file in
   the download states CC BY-SA 4.0, so the source is shared (decision 77). NITRC needs a login,
   so it stays a manual, optional source that a build skips when the file is missing.
3. **Deficit texts.** Each step of a route already has a cited `Lesion:` line with `{same}` and
   `{opposite}` side words. These are the deficit explanations. A new optional `Sign:` line per step
   gives the same deficit in a patient's terms without naming any structure, side words filled the
   same way, cited like the Lesion line ("Weakness of the {opposite} arm and leg"). Cases use only
   steps that have a Sign line. The eight sensory and motor routes get Sign lines as drafts,
   checked by `step_problems` with `Sign` as an optional label.

## 4. The engine (no UI)

A module under `cns_atlas` (it needs no Qt) computes, for a lesion:

1. **Hits.** For every structure with voxels, the share of its voxels inside the lesion, in the
   volume it lives in.
2. **Broken steps.** For every pathway whose texts have Lesion lines, for each start side (left,
   right), the stations of each step resolved with the existing `resolve(atlas, step, side)`. A
   step is broken when any of its structures has a share of at least 5 percent; "partly" when the
   largest share is under 25 percent (builder's call to name these two constants).
3. **Deficits.** One per broken step: the route, the start side, the step, its filled Lesion line,
   its filled Sign line if any, its references, and the structures and shares that broke it.
   Deficits from the same route and start side are grouped, earliest step first.
4. **Spared.** The routes the atlas can follow that no deficit touches.

The engine is a pure function of the atlas and the lesion so it is tested without a window.

## 5. The Lesion workspace (layout A)

A fifth workspace, "Lesion", beside Explore, Slices, Pathways and Lab, with its own panels (decision
71). Entering saves visibility, selection and slice, leaving restores them, as Pathways does.

1. **Left, "Place" and "Cases" tabs.** Place: a tree of territories by artery (shown only when the
   territories are in the build), "Brush on the slice", "Whole structure", a side switch (left,
   right) for territories and structures, and a brush size from 2 to 20 mm.
2. **Centre.** The 3D view and a slice side by side. The lesion is drawn in gold on both: a
   translucent body in 3D and a filled overlay on the slice. Structures it hits keep their colour;
   the rest fade as in a route.
3. **Right, "Deficits" and "Hit" tabs.** Deficits: grouped by route, each with its filled Lesion
   line, "partly" when so, the structures that broke it on hover, and its numbered sources; then
   "Spared"; then the learning notice. Hit: every structure hit with its share, largest first;
   clicking one selects it.
4. **Placing.** Click a territory to set the lesion to it on the chosen side. With the brush, click
   on the slice to add a sphere of the brush size at that point and drag to paint; Ctrl with click
   or drag erases. Whole structure: pick in the tree or the 3D view. Each action is one undo step
   (Ctrl+Z, Ctrl+Shift+Z); "Clear" empties the lesion.
5. **Cases tab.** "New case" picks a target: a territory, or a structure that breaks at least one
   step with a Sign line, on a random side, from what the build has. Its signs (the filled Sign
   lines of its deficits) are listed as the patient's signs. The user places a lesion with the same
   tools and presses "Check": each sign is marked matched, missed or extra (a sign the user's lesion
   causes that the case does not), then the real lesion is shown in a second colour and the case's
   deficits are explained. A case attempt is kept in the progress record (date, target, matched,
   missed, extra).
6. **Cord.** When the spine volume is in the build, the slice can show it and the brush works there;
   cord routes work like any other. Public builds have no cord, and the Place tab says so in one
   line instead of offering it.

## 6. Speed

Computing hits and deficits after a click or a brush stroke stays within the existing selection
budget (decisions 9 and 31): under 50 ms for a territory on the reference machine, measured by a slow test
with a baseline. Painting updates the overlay while dragging and computes deficits on release.

## 7. Left to the builder

The territory tree's labels from the atlas label file, the exact gold and fade values from the
tokens, how the lesion body is meshed for 3D, how the workspace registers with `workspaces.py`
(generalizing `register_lab` is fine), the progress table's shape, and the case picking weights.

## 8. Tests

The engine gets unit tests on a toy atlas: hits and shares, a broken step on each side through a
crossing, partly, spared, a lesion in two volumes, no deficit without a Lesion line. Sign lines are
checked by the knowledge checks. The workspace gets tests for each placing tool, undo, the deficit
list, the Hit tab, a full case (new, check, reveal), enter and leave restoring the window, a public
build without territories or cord, and that nothing draws over another region. A slow test holds
the speed of section 6.

## 9. Decisions to log

1. Lesion mode is a workspace that computes deficits from the cited route texts, with cases
   generated from the same engine.
2. The arterial territories of Liu and colleagues (2023) are a source, local only until the
   authors confirm the terms.
