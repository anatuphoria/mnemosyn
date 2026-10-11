# Scalable Viewer and Slice View Design (sub-project B, part 1: B1 + B2)

Date: 2026-10-11
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-11-atlas-foundation-design.md` (sub-project A)

## 1. Context

Sub-project B turns the atlas foundation into the study tool. It splits into four parts:

| Part | Scope | When |
|---|---|---|
| B1 Rendering core | Composite renderer, picking, batched visibility, automatic detail level, sibling shades, in-app budgets | This round |
| B2 Slice view | Atlas-plate cross-sections over an MRI template, linked to 3D, tree and info | This round |
| B3 Self-testing | Quizzes and flashcards with progress | Next round |
| B4 Pathway view | End-to-end systems | After sub-project C (needs tract data) |

Decisions made in discussion:

- Slice view first after the rendering core; it is also what future model importers need to
  review imports.
- Slices show coloured labels over a grey MRI template, like an MRI viewer.
- Layout: the 3D view and one slice panel side by side; buttons switch the axis.
- 3D: VTK composite mapper. Slices: numpy composition shown with pyqtgraph.
- Surface smoothing is dropped: a Gaussian blur before surface extraction was tested and
  changed little; the visible steps are mostly AAL parcel boundaries.
- The labelled volume stays the single source of truth for where structures are. Future
  importers rely on this rule.

## 2. Measured facts this design relies on

- Composite mapper on the integrated GPU (Radeon 680M), 1400x850, pixels read back every
  frame: about 97 fps at 1,160 structures (3.3M triangles), about 48 fps at 3,480 structures
  (9.9M triangles). One actor per structure: 27 fps and 11 fps.
- Building the composite for the 166 real structures and rendering the first frame: 0.47 s.
- `vtkHardwarePicker` returns the flat block index and respects block visibility.
  `vtkCellPicker` does not (it picks hidden blocks), so it is not used.
- Colin27 (MNI single subject, 1998, NIfTI) has exactly the AAL3 grid: shape 181x217x181,
  1 mm voxels, origin (-90, -126, -72). Labels follow its gyri; 99.1 percent of labelled
  voxels fall inside its brain mask.

## 3. B1: rendering core

### 3.1 Composite renderer

- All structures with geometry are blocks of one `vtkMultiBlockDataSet` drawn by one
  composite mapper and one actor. Block order is the atlas depth-first order of structures
  with geometry; the view keeps `block index -> structure id` and the reverse.
- Colour, visibility, opacity and highlight are per-block display attributes. Changing them
  never rebuilds geometry.
- Vertex normals come from the package; smooth (Gouraud) interpolation.

### 3.2 Picking

- `vtkHardwarePicker` at the click position; the flat block index maps to the structure id.
- A click on a hidden structure reaches whatever is drawn behind it, or the background.
- Click versus drag keeps the existing 3 pixel tolerance.

### 3.3 Batched visibility

- `AppState.set_hidden` already emits one signal per call. The tree's checkbox handling is
  changed so a group toggle results in one `set_hidden` call for all affected structures,
  and the view renders once per signal.

### 3.4 Automatic detail level

- A pure function `choose_lod(face_counts_per_level, budget=3_000_000) -> int` returns the
  finest level whose total face count over all structures with geometry is within budget,
  falling back to the coarsest level.
- With the current 166 structures (1.29M faces at lod0) it chooses lod0.

### 3.5 Sibling shades

- In the build, a concept that inherits its colour from an ancestor gets a shade of it:
  siblings under the same coloured group are ordered by id; with n siblings, sibling k
  (0-based) gets factor f = -0.15 + 0.30 * k / (n - 1) (f = 0 when n = 1). A positive f mixes
  the colour toward white by f, a negative f toward black by -f. Deterministic.
- Left and right children always share their concept's shade.
- A concept with an explicit `color` keeps it unchanged.
- Colours stay atlas data (`rgb_triplet`), so both apps show them.

### 3.6 In-app performance budgets

Budgets from spec A, now measured where the user feels them:

| Measure | Budget | How |
|---|---|---|
| Start to first frame, real atlas | under 2 s | `cns_desktop --first-frame` subprocess, second run |
| App memory, real atlas, first frame | under 500 MB | `VmHWM` of that subprocess |
| Selection to all panels updated, real atlas | under 7 ms median | in-process, offscreen |
| Generated 3,500-structure scene | at least 60 fps | offscreen, pixels read back each frame |
| On-screen frame rate | display refresh (144 Hz) | manual, `cns_desktop --bench` |

## 4. B2: slice view

### 4.1 Template data

- A new recipe section `[[templates]]` declares template sources with the same fields as
  label sources (download, sha256, member, licence, licence_file, redistribution) plus the
  label volume they belong to.
- First template: Colin27 1998 NIfTI
  (`http://packages.bic.mni.mcgill.ca/mni-models/colin27/mni_colin27_1998_nifti.zip`,
  sha256 `9dd49943ec20fb72407d85591219f6f701fa60e3a8234e73d8f41a754bdbf87d`, member
  `colin27_t1_tal_lin.nii`). The archive has no licence file, so
  `atlas_src/LICENSES/Colin27.txt` carries the notice from the McGill page (year range
  written with a plain hyphen). Licence: permissive notice, "Permission to use, copy, modify,
  and distribute ... provided that the above copyright notice appear in all copies".
- The build resamples a template onto its label grid when the grids differ (linear
  interpolation), rescales intensities so the 0.5th and 99.5th percentiles map to 0 and 255,
  and writes `volumes/<label volume>-template.nii.gz` as uint8. The full head is kept.
- `metadata.json` volume records gain an optional `role`: `"labels"` (default) or
  `"template"`, and templates name their label volume in `labels`. Format version stays 1;
  packages without `role` open as before.
- Loader: `Atlas.template -> TemplateVolume | None` with `data` (uint8 array) and the same
  world mapping as the label volume.
- Build validation adds: a template source needs a licence and `redistribution = true`, like
  any source.

### 4.2 Slice composition (pure functions, no Qt, no GPU)

Module `cns_desktop/slices.py`:

- `AXES = ("axial", "coronal", "sagittal")`.
- `slice_count(shape, axis) -> int`, `index_for_mm(affine, axis, mm) -> int`,
  `mm_for_index(affine, axis, index) -> float`.
- `extract(volume, axis, index) -> np.ndarray` returns a 2D array oriented for display in
  neurological convention: patient left on screen left, anterior up in axial, superior up
  in coronal and sagittal; sagittal shows anterior on the left.
- `compose(labels_2d, template_2d | None, colors, hidden, selected, opacity) -> RGBA uint8`:
  template in grey (black when absent); each visible structure blended in its colour at
  `opacity` (default 0.45); hidden structures not coloured; selected structures drawn at
  full colour with a one pixel outline.
- `colors` is a lookup array indexed by structure id, built once per atlas.
- Budget: `compose` for a 217x181 slice under 5 ms.

### 4.3 Slice panel

- Widget with buttons Axial, Coronal, Sagittal; a position slider with a millimetre readout
  (for example "z = +12 mm"); a label opacity slider; a "Centre on selection" button (key
  `C`); orientation letters (L/R, A/P, S/I) on the panel edges.
- Hover shows the structure name under the cursor in the status bar.
- Click selects the structure under the cursor (via `Atlas.label_at`); a click on unlabelled
  tissue or background changes nothing.
- "Centre on selection" moves the slice through the centre of the selected structure's
  voxels (for a group, of all its structures' voxels). The slice does not move by itself on
  selection.
- Without a template the panel draws labels on black and shows "No template in this atlas".

### 4.4 Shared state and linking

- `AppState` gains `slice_axis`, `slice_mm`, `set_slice(axis, mm)` and the signal
  `slice_changed`.
- The 3D view draws the current plane as a translucent rectangle spanning the volume and
  moves it on `slice_changed`.
- Selection and visibility changes repaint the slice; selecting a group outlines all of its
  structures, as the 3D view highlights them.
- Layout: the slice panel is a dock to the right of the 3D view by default; the activity
  chart dock stays at the bottom.

## 5. Errors

- Atlas without a template: labels on black, note in the panel.
- Template grid not covering the label grid after resampling: the build fails with a message
  naming the template.
- Hover or click outside the volume or on unlabelled voxels: no name, no selection change.

## 6. Testing

- Build: template fetch, checksum, resampling, intensity scaling and the `role` records,
  using a synthetic template in the toy atlas; shades deterministic, left and right equal,
  explicit colours untouched; licence rules apply to templates.
- Loader: `Atlas.template` present and absent; volumes without `role` treated as labels.
- Slice functions: orientation with a deliberately asymmetric test volume (left appears on
  the left, anterior up in axial); millimetre and index conversion both ways; composition of
  colour, opacity, hidden and selected outline; the 5 ms budget on a full-size slice.
- Desktop app on the toy atlas: one block per structure with geometry; picking returns the
  right id and cannot reach a hidden structure; a group toggle renders once; `choose_lod`;
  axis buttons, slider moving the 3D plane, hover name, click selecting, "Centre on
  selection".
- Budgets in section 3.6, with the real-atlas ones marked slow.

## 7. Scope

In scope: sections 3 and 4, the Colin27 template source and its licence notice.

Out of scope: self-testing (B3), pathways (B4, after C), surface smoothing, tilted slices,
the editor and model importers, terminal app changes.

## 8. Amendments made during planning (2026-10-11)

1. The selection highlight is a separate overlay composite of the selected, visible
   structures (lightened own colours, polygon offset, not pickable). Measured: changing any
   block attribute of the main composite makes the next render take about 22 ms, while
   swapping the overlay input costs about 0.5 ms. Block attributes of the main composite are
   set for colours at startup and for visibility only.
2. Colin27 is a zip archive; the fetcher extracts members from zip as well as tar.
3. VTK 9.7 names the mapper `vtkCompositePolyDataMapper` (module `vtkRenderingCore`).
4. The structure tree computes its own tri-state check marks, so one click results in one
   visibility change.
