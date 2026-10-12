# Pituitary and Pineal Glands with Local-Only Sources (sub-project C, part 4: C4)

Date: 2026-10-12
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-11-tracts-hypothalamus-design.md` (C1: native mesh grids, drop
lists, source checks) and the A foundation spec (recipe, ids, knowledge)

## 1. Context

Physiology (sub-project D) needs the hormone glands of the head. The atlas has the hypothalamic
nuclei that drive them (C1) but neither the pituitary nor the pineal gland.

No openly licensed 3D source exists for either. Two published shapes can be downloaded but carry
no licence for the files. The owner chose to use them in local builds only, ask their authors
for permission, and ship them once permission arrives.

Decisions made in discussion:

- Scope: pituitary gland (whole, one structure) and pineal gland. Separate pituitary lobes and
  the circumventricular organs are out of scope.
- Shapes come from the two published sources below, marked local-only until their authors allow
  redistribution.
- A normal build stays shareable and unchanged; a local build adds the local-only sources and is
  marked as not for sharing.

## 2. Sources

| Id | Data | Grid | Licence |
|---|---|---|---|
| `tang2024` | Pituitary mask on the MNI ICBM152 2009a nonlinear asymmetric template, annotated by an expert; repository `github.com/kvttt/Pituitary_Segmentation` (Kaibo Tang, Athinoula A. Martinos Center), file `pituitary_mask_2009a.nii.gz` | 197 x 233 x 189, 1 mm, RAS, values 0 and 1; 1272 voxels centred at (0, 2.7, -32.2) mm | none stated |
| `razavi2021` | Probabilistic pineal gland atlas, MNI version thresholded at 0.25: Razavi et al. (2021), Frontiers in Neuroinformatics 15: 554229, doi:10.3389/fninf.2021.554229; files at `brainee.ir/pineal-gland-atlas/`, archive `Pineal_MNI_Atlas_th0.25.zip`, member `3. Pineal_MNI_Atlas_th0.25.nii` | 182 x 218 x 182, 1 mm, LAS, probability values; 152 nonzero voxels centred at (0.5, -30.2, 3.8) mm | article CC BY; files none stated |

- Both are pinned by sha256 like every source, `redistribution = false`, `local_only = true`.
- Both are meshed on their native grid (`mesh_grid = "native"`) and merged into the label volume
  at priority -1, below every other source, so they never overwrite an AAL3 or hypothalamus
  label.
- The pineal file stores probabilities. A new source option `mask = true` turns every nonzero
  voxel into label 1 before mapping.
- Permission requests go to Kaibo Tang and to the pineal atlas team; the owner sends them.

## 3. Hierarchy and descriptions

| Id | Parent | Acronym | Name | Kind | Shape |
|---|---|---|---|---|---|
| 24 | 20 Diencephalon | EPI | Epithalamus | group | - |
| 2700 | 20 Diencephalon | PIT | Pituitary gland | region | `tang2024` label 1, midline |
| 2710 | 24 Epithalamus | PIN | Pineal gland | region | `razavi2021` label 1, midline |

- Both placements are judgment calls for the owner's doctor review: only the posterior lobe of
  the pituitary is neural tissue.
- Draft descriptions `knowledge/en/2700.md` and `knowledge/en/2710.md` (Function, Connections,
  Clinical), with references, `status = "draft"`.

## 4. Local-only builds

### 4.1 Recipe

- `[[sources]]` gains two optional keys: `local_only` (default false) and `mask` (default false).
- Build errors: `local_only = true` together with `redistribution = true` ("a shareable source
  must not be local-only"); `redistribution = false` without `local_only` (as today).
- Only label sources may be local-only; tracts and templates keep today's rules.

### 4.2 Two builds

- `python -m tools.build_atlas` (normal): local-only sources are neither fetched nor built;
  structures whose labels all come from skipped sources are left out of the package, with their
  descendants, and groups left empty are kept. The package is shareable and identical in content
  to a build without these sources.
- `python -m tools.build_atlas --local`: local-only sources are fetched and built like any other.
- `ids.lock` records every id in the source tree in both builds, so the new ids are published as
  soon as they are committed.
- Knowledge files of left-out structures are still copied; the loader ignores entries for ids it
  does not have.

### 4.3 What a local package records

- `metadata.json` gains `"local_only": [source ids]`, present only when the list is not empty.
  `format_version` stays 1; older packages without the key open as before.
- `sources.json` lists the local-only sources with their citation, so the About box credits them.
- The build report adds one line: `- local-only sources included: ...` or
  `- local-only sources left out: ...`.

### 4.4 Loader and packaging rule

- `Atlas.local_only: tuple[str, ...]` (empty when the key is absent).
- Rule for the future packaging step (sub-project F): an installer must refuse a package whose
  `local_only` is not empty.

## 5. Desktop

- A local package shows "(local build, not for sharing)" after the atlas name in the window
  title, and the About box adds: "This atlas includes data that may not be shared yet:" followed
  by the citations of the local-only sources.
- The glands behave like any structure: tree, 3D picking, slices, Centre slice, quizzes, info
  panel. No new panel or shortcut.

## 6. When permission arrives

For a source whose authors agree: set `redistribution = true`, add `licence` and a licence
notice file, remove `local_only`, rebuild. The gland then ships in normal builds.

## 7. Testing

- Toy atlas gains a local-only mask source (one small probability blob) mapped to one structure.
- Build: a normal build skips the local-only source without fetching it, leaves its structure
  out, writes no `local_only` key and reports it as left out; a `--local` build includes it,
  writes the key and the report line and gives the structure a shape; `mask = true` maps a
  probability file to one label; both recipe errors of 4.1.
- Loader: `local_only` from the key; packages without it give an empty tuple.
- Desktop: title and About text in a local package, absent otherwise.
- Real atlas (slow): the normal build keeps 285 shapes; a `--local` build adds 2700 and 2710 with
  centres near (0, 3, -32) and (0, -30, 4) mm, both visible in slices; source tests check the two
  new recipe entries and structures.
- Budgets unchanged: first frame under 2 s, own memory under 400 MB, selection under 7 ms.

## 8. Scope

In scope: sections 2 to 7, the two draft descriptions, and the permission email texts (shown to
the owner, sent by the owner).

Out of scope: separate pituitary lobes, circumventricular organs, the packaging step itself,
physiology.
