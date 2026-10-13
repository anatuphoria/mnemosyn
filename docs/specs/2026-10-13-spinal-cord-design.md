# Spinal Cord from PAM50 (sub-project C, part 2: C2)

Date: 2026-10-13
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-12-endocrine-glands-design.md` (C4: local-only sources) and
`docs/specs/2026-10-13-brainstem-nuclei-design.md` (C3: members, crop, station fallback)

## 1. Context

The atlas stops at the medulla. The motor, touch and pain routes describe their spinal stations in
words only. PAM50 (De Leener et al. 2018) is a template and atlas of the spinal cord that shares
the ICBM152 coordinate system with the brain atlases. Its files carry no licence; a permission
email to its authors is already drafted (`review/emails/01-pam50-spinal-cord.md`).

Decisions made in discussion:

- PAM50 is local-only until its authors allow sharing, exactly like the glands and the Brainstem
  Navigator. The shareable build does not change.
- Content: the 30 spinal segments, the six grey matter regions and the 30 white matter tracts.
- The cord appears in 3D and in slices. The start view still frames the brain.
- Three words-only route stations become shapes in local builds; their texts do not change.
- New structures get names only; descriptions are a later review round.

## 2. Source

| Id | Data | Licence | Fetch |
|---|---|---|---|
| `pam50`, `pam50-atlas`, template `pam50-t2` | PAM50 release r20250730 (github.com/spinalcordtoolbox/PAM50), `PAM50-r20250730.zip`, sha256 `8347c7a240a54e7c44ecd9cc43ef7c3c650784757bf9ed8c8bb2f8587dfc8846`; members under `spinalcordtoolbox-PAM50-3144364/` | none stated: local only until the authors allow sharing | automatic, one download shared by the three entries |

- Citation: De Leener B, Fonov VS, Collins DL, Callot V, Stikov N, Cohen-Adad J (2018). PAM50:
  Unbiased multimodal template of the brainstem and spinal cord aligned with the ICBM152 space.
  NeuroImage 165: 170-179, doi:10.1016/j.neuroimage.2017.10.041.
- Grid: 141 x 141 x 991 voxels of 0.5 mm, LAS orientation, MNI coordinates; the cord runs from
  z -67 to -542 mm, centred near x 0, y -45.
- `pam50`: `template/PAM50_spinal_levels.nii.gz`, labels 1 to 30 = C1 to C8, T1 to T12, L1 to L5,
  S1 to S5. Grid source of the spine volume.
- `pam50-atlas`: `atlas/PAM50_atlas_00` to `_35.nii.gz` as members (tracts 00 to 29, grey matter
  30 to 35); probabilistic maps, kept where the value is at least 0.3 (the lateral reticulospinal
  map never reaches 0.5). Each map's 3D shape comes from its own mask (`separate = true`), so left
  and right stay symmetric where their maps overlap at the midline; in the slice volume overlaps go
  to the map listed first, and the members are listed smallest pair first so small tracts keep
  their voxels. `_36` (CSF contour) is not used. Ranks above `pam50` in the spine volume, so
  segments fill only the remaining cord voxels.
- `pam50-t2`: `template/PAM50_t2.nii.gz`, the slice template of the spine volume.
- All three are `local_only`, meshed on their own grid (`mesh_grid = "native"`).

## 3. Structures

New groups (ids free in `ids.lock`):

| Id | Parent | Acronym | Name |
|---|---|---|---|
| 3 | 1 Central nervous system | SpC | Spinal cord |
| 4 | 3 | SpSeg | Spinal segments |
| 5 | 4 | Cerv | Cervical segments |
| 6 | 4 | Thor | Thoracic segments |
| 7 | 4 | Lumb | Lumbar segments |
| 8 | 4 | Sacr | Sacral segments |
| 9 | 3 | SpGM | Spinal grey matter |
| 80 | 3 | SpTr | Spinal tracts |

Segments: 30 midline regions, id `5000 + 10 * level` (C1 = 5010 to S5 = 5300), acronym `C1` to
`S5`, name `Segment C1` to `Segment S5`, parent the matching group, `pam50` label = level.

Grey matter (left and right, `kind = "nucleus"`, parent 9, `pam50-atlas`):

| Id | Acronym | Name | Members (left, right) |
|---|---|---|---|
| 5400 | VH | Ventral horn | 30, 31 |
| 5410 | IZ | Intermediate zone | 32, 33 |
| 5420 | DH | Dorsal horn | 34, 35 |

Tracts (left and right, `kind = "tract"`, parent 80, `pam50-atlas`):

| Id | Acronym | Name | Members |
|---|---|---|---|
| 5500 | FG | Fasciculus gracilis | 00, 01 |
| 5510 | FC | Fasciculus cuneatus | 02, 03 |
| 5520 | LCST | Lateral corticospinal tract | 04, 05 |
| 5530 | VSCT | Ventral spinocerebellar tract | 06, 07 |
| 5540 | RuST | Rubrospinal tract | 08, 09 |
| 5550 | LReST | Lateral reticulospinal tract | 10, 11 |
| 5560 | sSTT | Spinothalamic tract (spinal lemniscus) | 12, 13 |
| 5570 | SOT | Spino-olivary tract | 14, 15 |
| 5580 | VLReST | Ventrolateral reticulospinal tract | 16, 17 |
| 5590 | LVST | Lateral vestibulospinal tract | 18, 19 |
| 5600 | VReST | Ventral reticulospinal tract | 20, 21 |
| 5610 | VCST | Ventral corticospinal tract | 22, 23 |
| 5620 | TST | Tectospinal tract | 24, 25 |
| 5630 | MReST | Medial reticulospinal tract | 26, 27 |
| 5640 | sMLF | Medial longitudinal fasciculus (spinal part) | 28, 29 |

- Member names `A00` to `A35` refer to `PAM50_atlas_00` to `_35`; even numbers are left, odd
  right, as in PAM50's `info_label.txt`. A test checks every left child lies at x < 0.
- 66 shapes in local builds (30 + 6 + 30). Spinal tracts are hidden by default with the other
  tracts (T).
- In the shareable build all of them are left out with their ids kept in `ids.lock`.

## 4. Build changes

### 4.1 Threshold and separate shapes

A source may set `threshold` (a number). Members, and a single-file source with `mask = true`,
then keep a voxel when its value is at least the threshold instead of when it is nonzero. Overlaps
between members still go to the member listed first and are counted in the build report. With
`separate = true` (members and a native grid only) each member's 3D shape is meshed from its own
mask; the overlap rule then applies only to the label volume.

### 4.2 Crop margin

A source with `crop = true` may set `margin` in millimetres; the read box grows by that much on
every side, clamped to the image. `pam50` uses `margin = 10`.

### 4.3 The spine volume

- `recipe.toml` gains `[[volumes]] name = "spine", space = "PAM50", grid_source = "pam50"`.
- A volume's grid is stored in RAS orientation: when its grid source is not RAS, the build turns
  the grid to the closest RAS orientation before merging labels and resampling the template.
- With the 10 mm margin the spine grid is about 64 x 60 x 952 voxels of 0.5 mm.

### 4.4 Local-only volumes and templates

- Templates may be `local_only`, with the same rules as label sources.
- A volume whose grid source is local-only is allowed when every source and template of that
  volume is local-only. A normal build leaves out the whole volume and its template; the package
  is unchanged.
- A volume with a local-only grid source and any shareable source or template is a build error
  naming the volume.

## 5. App

### 5.1 Loader

- `Atlas.templates` maps a label volume's name to its template; `Atlas.template` stays the
  template of the first volume.
- Packages with one volume behave as today.

### 5.2 Slice panel

- When the atlas has more than one label volume, the panel shows one button per volume, named
  `Brain` (brain) and `Spinal cord` (spine); otherwise nothing changes.
- The chosen volume gives the slices, slider range, template, hover names and clicks; switching
  keeps the axis and moves to the middle of the new volume.
- `Centre on selection (C)` switches to the volume that holds the selection's voxels.
- The axial view is the useful cord view; coronal and sagittal show the full cord as a narrow
  strip. Slice zoom is out of scope.

### 5.3 State and 3D view

- `AppState.slice_volume` (the chosen volume's name) with `set_slice_volume(name)`; the 3D slice
  plane uses that volume's bounds.
- The start view and Reset frame the brain volume, never the whole cord.
- Selecting a structure inside Spinal cord (group 3) frames the selection, keeping the view
  direction; selecting a structure outside it while the camera frames the cord frames the brain
  again.

### 5.4 Quizzes

Segments, grey matter and the new groups join the structure quizzes automatically; spinal tracts
join the Tracts level. No quiz code changes.

## 6. Routes

| Route | Words-only station | Becomes (local builds) | Fallback (shareable build) |
|---|---|---|---|
| motor | Lateral corticospinal tract in the spinal cord | 5520, opposite side | same name |
| touch | Dorsal column and gracile and cuneate nuclei | 5500 and 5510, same side | same name |
| pain | Dorsal horn | 5420, same side | same name |

Station texts in `atlas_src/knowledge/en/pathway-*.md` do not change by a single byte.

## 7. Testing

Toy atlas (fast):
- `threshold` on members and on a mask source.
- `margin` grows the crop box and clamps at the image edge.
- A non-RAS grid source gives a RAS volume whose voxels sit at the same world positions.
- A local-only second volume with a local-only template: left out of a normal build (package
  identical to one without it), included in a local build; a local-only grid source with a
  shareable source on the same volume is a build error.
- Loader: `templates` per volume; a one-volume package as before.
- Slice panel: volume buttons only with two volumes; switching changes slices, slider and hover;
  Centre switches to the selection's volume.
- 3D view: Reset frames the brain volume; selecting a structure under the spinal group frames it;
  selecting a brain structure afterwards frames the brain.

Real atlas (slow):
- Normal build: 306 shapes, unchanged; no spine volume.
- `--local` build: 392 shapes (326 + 66); a RAS spine volume about 64 x 60 x 952 with its
  template; segment C1 near the top (centre z near -73) and S5 at the bottom (near -540); every
  left horn and tract centred at x < 0.
- Routes: the three stations are shapes in the local build and keep their names in the
  shareable build; texts byte-identical.

Budgets measured on the local build: first frame under 2 s, the app's own memory under 400 MB,
selection under 7 ms. Entering a route rises from 100 to 130 ms (owner's decision, 2026-10-13), and
switching its side, the same single redraw, with it: the spinal segments and horns add about 13%
more faded geometry to that redraw.

## 8. Scope

In scope: sections 2 to 7.

Out of scope: descriptions of the new structures, the cord's natural curvature (PAM50 is
straightened), vertebrae, nerve roots and spinal nerves, the CSF contour, slice zoom.
