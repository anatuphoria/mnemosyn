# Tracts and Hypothalamus Design (sub-project C, part 1: C1)

Date: 2026-10-11
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-11-atlas-foundation-design.md` (A),
`docs/specs/2026-10-11-viewer-slices-design.md` (B1 + B2),
`docs/specs/2026-10-11-self-testing-design.md` (B3)

## 1. Context

Sub-project C makes the atlas cover the whole central nervous system. It is split in parts:

| Part | Scope | When |
|---|---|---|
| C1 | White-matter tracts and the hypothalamic region | This round |
| C2 | Spinal cord (PAM50: tracts, horns, spinal levels) | After the PAM50 authors allow redistribution |
| C3 | Brainstem and cerebellar nuclei | When a redistributable source is found |

Decisions made in discussion:

- C1 first because both sources have clear licences and lie in the MNI space the atlas
  already uses.
- Tracts are hidden when the app opens; one key (T) shows them; selecting a tract shows it.
- Tracts get their own quiz level with its own schedules.
- Overlapping tracts are stored as a sparse tract layer (per-tract voxel lists), not in the
  label volume.
- The hypothalamic region goes into the existing label volume; its 3D shapes are built from
  its native 0.5 mm voxels ("the volume decides where, the surface decides the look").
- Descriptions of the new structures are not part of C1; they follow the owner's doctor review
  of the existing drafts.

Research findings (2026-10-11):

| Region | Source | Licence | Usable |
|---|---|---|---|
| Tracts | HCP-1065 tractography atlas (Yeh 2018), Zenodo record 3627772 | CC BY-SA 4.0 | yes |
| Hypothalamic region | Neudorfer 2020, Zenodo record 3942115 (v4) | CC BY 4.0 | yes |
| Spinal cord | PAM50 (Spinal Cord Toolbox) | none stated | only with permission |
| Brainstem nuclei | Brainstem Navigator | non-commercial, no redistribution | no |
| Subcortical nuclei | CIT168 (Pauli 2018) | not stated | unclear |

## 2. Sources

### 2.1 HCP-1065 tracts (`hcp1065`)

- Yeh FC, Panesar S, Fernandes D, et al. (2018). Population-averaged atlas of the macroscale
  human structural connectome and its network topology. NeuroImage 178: 57-68,
  doi:10.1016/j.neuroimage.2018.05.027. Licence CC BY-SA 4.0.
- Download: the Zenodo zip of the whole record,
  `https://zenodo.org/api/records/3627772/files-archive`, pinned by sha256.
- Content: 80 binary masks (`<Name>.nii.gz`, uint8, values 0 and 1), 1 mm, RAS, shape
  157 x 189 x 136, origin (-78, -112, -50). The grid is an integer offset of the label grid
  (origin (-90, -126, -72)), so masks are placed exactly.
- Measured: 77 masks used, 1,311,614 voxels in total; 354,279 voxels lie in more than one
  tract; large tracts overlap AAL3 grey matter labels by up to about 50 percent.
- Dropped (listed in the recipe): `Cerebellum_L`, `Cerebellum_R`, `Vermis` (AAL3 labels the
  cerebellum).

### 2.2 Hypothalamic region (`neudorfer2020`)

- Neudorfer C, Germann J, Elias GJB, Gramer R, Boutet A, Lozano AM (2020). A high-resolution in
  vivo magnetic resonance imaging atlas of the human hypothalamic region. Scientific Data 7:
  305, doi:10.1038/s41597-020-00644-6. Licence CC BY 4.0.
- Download: two plain files from Zenodo record 3942115, each pinned by sha256:
  `MNI152b_atlas_labels_0.5mm.nii.gz` (labels aligned to MNI152 2009b, 0.5 mm, RAS, shape
  394 x 466 x 378, origin (-98, -134, -72)) and `Volumes_names-labels.csv` (label, name,
  hemisphere, abbreviation).
- 50 labels (25 structures, left and right). Measured at 1 mm: most structures do not overlap
  AAL3 labels at all; the smallest nuclei cover 4 to 15 voxels.
- Dropped labels (listed in the recipe): substantia nigra 15, 16 and red nucleus 17, 18 (AAL3
  keeps its own), fornix 5, 6 and anterior commissure 1, 2 (the tract atlas traces them in
  full).

### 2.3 Space

AAL3 (MNI), HCP-1065 (ICBM 2009a based) and Neudorfer (MNI152 2009b) are all MNI ICBM 152
variants. They are combined without further registration; differences between these
templates are a few millimetres at most. The about box and the build report state the
sources' spaces.

## 3. Hierarchy additions (`atlas_src/structures.toml`)

New groups (ids chosen from free ranges; `ids.lock` records them):

- `19` Basal forebrain, under Telencephalon (11).
- `22` Hypothalamus and `23` Subthalamus, under Diencephalon (20).
- `70` Tracts, under the CNS (1), with subgroups: `71` Projection, `72` Association,
  `73` Commissural, `74` Brainstem tracts, `75` Cerebellar peduncles, `76` Limbic and
  diencephalic tracts, `77` Radiations, `78` Cranial nerves. Each subgroup has its own colour;
  tracts in it get sibling shades.

New structures (concept ids in 2500-2699 for the hypothalamic region and 3000-3499 for tracts;
left and right children as for all concepts):

- Hypothalamus (22): medial preoptic nucleus, paraventricular nucleus, dorsal periventricular
  nucleus, periventricular nucleus, lateral hypothalamus, ventromedial nucleus, dorsomedial
  nucleus, arcuate nucleus, supraoptic nucleus, suprachiasmatic nucleus, tuberomammillary
  nucleus, posterior hypothalamic nucleus, anterior hypothalamic area, mammillary bodies.
- Subthalamus (23): subthalamic nucleus, zona incerta.
- Basal forebrain (19): nucleus basalis of Meynert, diagonal band of Broca, bed nucleus of the
  stria terminalis.
- Limbic and diencephalic tracts (76): mammillothalamic tract and inferior thalamic peduncle
  (from `neudorfer2020`), fornix (from `hcp1065`).
- From `hcp1065` (41 tracts including the fornix above; 36 left and right pairs and 5
  midline):
  - Projection (71): corticospinal, frontopontine, parietopontine, occipitopontine,
    temporopontine, corticostriatal, corticothalamic.
  - Association (72): arcuate fasciculus, superior, middle and inferior longitudinal
    fasciculus, inferior fronto-occipital fasciculus, uncinate fasciculus, cingulum, extreme
    capsule, frontal aslant tract, vertical occipital fasciculus, U-fibres.
  - Commissural (73): corpus callosum, anterior commissure, posterior commissure (midline).
  - Brainstem tracts (74): medial lemniscus, lateral lemniscus, spinothalamic tract, central
    tegmental tract, medial longitudinal fasciculus, dorsal longitudinal fasciculus,
    rubrospinal tract.
  - Cerebellar peduncles (75): inferior (pair), middle and superior (midline).
  - Radiations (77): optic radiation, acoustic radiation.
  - Cranial nerves (78): II, III, IV, V, VII, VIII, X.
- All tracts have `kind = "tract"`; the hypothalamic region nuclei `kind = "nucleus"`,
  areas `kind = "region"`.
- Totals: 62 new concepts, 12 new groups, 119 new 3D shapes; the atlas grows from 266 to
  about 450 entries.

Label references: for `hcp1065` a concept's `left`, `right` or `midline` is the mask name (a
string, for example `"Cortico_Spinal_Tract_L"`); for `neudorfer2020` it is the label number.
`LabelRef.value` becomes `int | str`.

## 4. Package format

Format version stays 1. Additions, ignored by older loaders:

- `tracts/ids.npy` (uint16, structure ids in atlas order), `tracts/offsets.npy` (int64,
  length ids + 1), `tracts/voxels.npy` (uint32, flat C-order indices into the label grid,
  sorted within each tract). About 5 MB.
- `metadata.json` volume record `{"file": "tracts", "role": "tracts", "labels": "brain"}`.
- Hypothalamic structures are labels in `volumes/brain.nii.gz`.
- Meshes of all new structures are in the existing `meshes/lod0..2` packs.
- `LICENSES/` gains the CC BY-SA 4.0 and CC BY 4.0 notices; `sources.json` lists both sources.

## 5. Build

- Recipe: `neudorfer2020` is a `[[sources]]` entry with `download` of a plain file (no
  archive), `label_names` in CSV form (`label_names_format = "csv"`, columns label, name,
  hemisphere, abbreviation), `drop = [1, 2, 5, 6, 15, 16, 17, 18]`, `priority = 2` (AAL3 wins
  where both label a voxel), and `mesh_grid = "native"`.
- New `[[tracts]]` section for `hcp1065`: the same source fields (download, sha256, licence,
  licence_file, redistribution) plus `labels = "brain"` and `drop = ["Cerebellum_L",
  "Cerebellum_R", "Vermis"]`. Members are found as `*.nii.gz` inside the archive.
- Fetching supports plain files (the download is the member) as well as tar and zip archives.
- Labels of a source on another grid are resampled to the label grid by nearest neighbour.
- `mesh_grid = "native"`: the source's 3D shapes are built from its own voxels (binary mask per
  label at 0.5 mm) with the same smoothing and detail levels; its 1 mm labels still decide
  slices and picking. Other sources and the tracts mesh on the 1 mm grid.
- Validation, in addition to A's rules:
  - every value or mask in a source is mapped to a structure or listed in `drop`;
  - a `drop` entry that does not exist in the source is an error;
  - every tract concept references masks of a `[[tracts]]` source, every other concept labels;
  - every structure with references gets voxels in the label volume or the tract layer;
  - a structure whose 1 mm labels vanish after merging keeps its native mesh and is listed in
    the build report (not an error).
- The build report lists counts per source and the dropped entries with their reason.

## 6. Loader

- `Atlas.tracts -> TractLayer | None` (only when the record's `labels` volume exists and the
  grid matches).
- `TractLayer`: `ids: tuple[int, ...]`, `voxels(structure_id) -> np.ndarray` (flat indices),
  `tracts_at(point) -> tuple[int, ...]` (ids of tracts containing the voxel at a world point,
  smallest tract first), memory-mapped arrays.
- `Atlas.label_at` is unchanged (grey matter labels only).

## 7. Desktop

### 7.1 3D view

- Structures of kind `tract` are not in the main composite. A second composite of tract
  blocks is built the first time any tract becomes visible, with its own detail level chosen
  by the same rule (`choose_lod` over tract faces only). Startup work is unchanged.
- Picking uses the hardware picker over both composites; the front-most drawn structure wins.
- The selection overlay covers tract blocks as well.

### 7.2 Visibility

- `AppState` starts with every tract hidden.
- Action "Tracts" (key T, toolbar) shows all tracts when any tract is hidden, otherwise hides
  all tracts.
- Selecting a tract (tree, search, quiz) makes it visible.

### 7.3 Slices

- Visible tracts are drawn as one-pixel outlines in their colour over the composed labels;
  selected tracts are filled at the label opacity.
- Hover and click: if visible tracts contain the voxel under the cursor, the smallest of them
  is named or selected; otherwise the grey matter label, as before.
- Tract voxels for the current slice are taken from the tract layer per redraw.

### 7.4 Quizzes

- `cns_study.items`: level `"tracts"` with items for concepts of kind `tract` (both sides as
  one, as for structures). `LEVELS = ("structures", "groups", "tracts")`. Structures level and
  Groups level exclude tracts and the Tracts groups.
- Name it on the tracts level: the asked tract is shown and all other tracts hidden; Find it:
  all tracts shown. Structures and Groups quizzes hide all tracts. Leaving the quiz restores
  visibility as before.
- The setup dialog lists the Tracts level; the progress window gains its rows.
- The hypothalamic region structures become Structures items; Hypothalamus, Subthalamus and
  Basal forebrain become Groups items when they have at least two items.

### 7.5 Budgets

| Measure | Budget |
|---|---|
| Start to first frame, real atlas | under 2 s (unchanged) |
| App memory at first frame, real atlas | under 600 MB (unchanged) |
| First time tracts are shown | under 500 ms |
| Showing or hiding tracts after that | under 50 ms |
| Slice redraw with all tracts visible | under 10 ms |
| Hover or click lookup with tracts visible | under 1 ms |

## 8. Errors

- A tract source without its label volume, or with a grid that is not an integer offset of
  it: build error naming the source.
- A package with a `tracts` record whose files are missing or inconsistent (offsets not
  increasing, indices outside the grid): `AtlasError` naming the file.
- An atlas without a tract layer: no Tracts action effect, no tract outlines, no tracts level
  items (the setup dialog says nothing to ask).

## 9. Testing

- Toy atlas gains a 0.5 mm `toyhyp` source (two small nuclei, one dropped label) and a tract
  zip (two overlapping masks on an offset grid and one dropped mask).
- Build: plain-file fetch; CSV names; drop lists (missing and unknown entries are errors);
  priority (the older source wins); nearest-neighbour resampling; native meshing (a nucleus
  with no 1 mm voxels keeps its mesh and is reported); tract layer contents and determinism;
  licences and sources listed.
- Loader: tract layer present and absent; `voxels`; `tracts_at` with overlaps (smallest
  first); malformed files raise `AtlasError`.
- Desktop: tracts hidden at start; T shows and hides; selecting a tract shows it; the tract
  composite is built once; slice outlines and filled selection; click picks the smallest
  visible tract, else the label; quiz tracts level (Name it shows only the asked tract, Find
  it shows all) and tracts hidden in other levels.
- Real atlas (slow): 41 tract concepts with 77 shapes, 21 hypothalamic-region concepts, the
  budgets of section 7.5, memory.

## 10. Scope

In scope: sections 2 to 8.

Out of scope: spinal cord (C2), brainstem and cerebellar nuclei (C3), descriptions of the new
structures, the pathway view (B4), registration between MNI template variants, terminal app
changes.

## 11. Amendments made during planning (2026-10-11)

1. Zenodo record 3627772 has no whole-record zip (the files-archive URL returns 404), so
   `[[tracts]]` pins every file: `download` is a URL template containing `{name}`, and
   `[tracts.files]` maps each mask name to its sha256.
2. The Neudorfer name table is not downloaded: names live in `structures.toml`; the label
   numbers were mapped from that table during planning.
3. In the existing merge a higher `priority` wins, so `neudorfer2020` has `priority = 0` and
   AAL3 keeps `priority = 1`.
4. Label references are typed: a string is a mask name and must belong to a `[[tracts]]`
   source; a number is a label and must belong to a `[[sources]]` entry. The
   mammillothalamic tract and inferior thalamic peduncle are `kind = "tract"` but stored as
   labels.
5. The build report lists dropped entries; the reasons are recorded in section 2, not in the
   recipe.
6. Source spaces are stated in this spec only, not in the About box.
7. Selecting a structure shows hidden tracts only when every 3D shape under it is a tract, so
   selecting the CNS root does not show all tracts.
8. The slice panel uses the tract layer only when its grid equals the panel's label volume.
9. Tests use a second toy atlas with tracts and a 2 mm source; the existing toy atlas is
   unchanged.
10. Tract mask voxels outside the label grid are a build error.
11. Tract timing budgets are measured in a subprocess, like the quiz timing.
12. Groups whose members are all structure items are left out of the Groups quiz level (with
    tracts outside the Brain group, "Brain" would otherwise become a quiz item).
