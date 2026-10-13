# Brainstem and Deep Cerebellar Nuclei (sub-project C, part 3: C3)

Date: 2026-10-13
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-11-tracts-hypothalamus-design.md` (C1: native mesh grids, per-file
tract sources) and `docs/specs/2026-10-12-endocrine-glands-design.md` (C4: local-only sources,
`mask`, left-out structures as text-only stations)

## 1. Context

The atlas draws the large brainstem landmarks from AAL3 (substantia nigra, red nucleus, VTA, locus
coeruleus, dorsal and median raphe) but none of the small nuclei that sensory, motor and behaviour
routes pass through. Six route stations are described in words only for that reason.

Decisions made in discussion:

- Use three openly licensed sources, shipped to everyone, plus the Brainstem Navigator in local
  builds only for nuclei no open source draws. A permission email to its authors is drafted for the
  owner to send.
- Existing shapes and labels do not change. Each new structure comes from exactly one source, open
  sources before the Navigator.
- Words-only route stations whose nucleus now exists become real stations. Their texts stay word for
  word; no stations are added.
- New structures get names only. Descriptions are new draft text for a later review round.

## 2. Sources

| Id | Data | Licence | Shipped | Fetch | Grid |
|---|---|---|---|---|---|
| `edlow2023` | Harvard Ascending Arousal Network Atlas v2.0 (Edlow BL, Kinney HC 2023), Dryad doi:10.5061/dryad.zw3r228d2, one binary mask per nucleus | CC0 1.0 (stated in the dataset README and the Dryad record) | yes | manual: Dryad zip `doi_10_5061_dryad_zw3r228d2__v20230718.zip`, sha256 `a6918e370241f5128ce06c2b26820c85d731295056c901540ad547bd652efbfb` | 1 mm MNI152 |
| `diedrichsen2009` | Probabilistic atlas of the human cerebellum, nuclei labels 29 to 32 (Diedrichsen et al. 2009; nuclei: Diedrichsen et al. 2011), `Diedrichsen_2009/atl-Anatom_space-MNI_dseg.nii` at commit `6857dfa732de6dd60c94da2f84d0b15ccf316618` of github.com/DiedrichsenLab/cerebellar_atlases, sha256 `434471d89ff329e6e14cdecb66998018fe0dcadbbe47781429148d0017598b72` | CC BY (repository README) | yes | automatic | 1 mm MNI |
| `sitek2019` | Subcortical auditory atlas from BigBrain histology (Sitek et al. 2019, eLife 8:e48932), `atlases/sub-bigbrain_MNI_conjunction_rois.nii.gz` at commit `2b73fb3e1f0afef8c3c487bf86c9bf61f6b04d51` of github.com/sitek/subcortical-auditory-atlas, sha256 `4327588dc0d2beae92a4f47d48af674235bfcd8742ca71a2592a91aa46994e91` | BSD-3-Clause (repository LICENSE.md) | yes | automatic | 0.1 mm MNI, 720 x 600 x 840 |
| `bianciardi2024` | Brainstem Navigator v1.0 (Bianciardi lab, MGH), `labels_thresholded_binary_0.35` masks in MNI space; zip `BrainstemNavigatorv1.0.zip`, sha256 `0ac9af5ab6e7fe1237f8f84be237cf6077111fb7ebd31899bee9b97bbfc88fc4` | non-commercial research only, no distribution outside the organisation (Copyright.txt) | local only | manual (NITRC login) | 1 mm MNI |

- Sitek labels: 1, 2 cochlear nucleus (left, right); 3, 4 superior olivary complex; 5, 6 inferior
  colliculus; 7, 8 medial geniculate body (dropped, already drawn by AAL3).
- Diedrichsen labels 29 to 34: dentate, interposed, fastigial (left, right). Labels 1 to 28
  (lobules, already drawn by AAL3) and 33, 34 are dropped: the fastigial label has 3 and 4 voxels
  and its probability never exceeds 0.23.
- Every new source ranks below all existing sources (priority -2; the Navigator -3) and is meshed on
  its own grid (`mesh_grid = "native"`), so it never overwrites an existing label in the slice view
  and still keeps its full shape in 3D.
- Licence notices for CC0, CC BY and BSD-3 are added to `atlas_src/LICENSES/`. The Navigator's
  `Copyright.txt` is reproduced in local builds only.

## 3. Structures

New groups: 34 Medulla (parent 30 Brainstem), 43 Deep cerebellar nuclei (parent 40 Cerebellum).
All nuclei are `kind = "nucleus"`; bilateral ones get left and right children (id + 1, id + 2).

| Id | Parent | Acronym | Name | Sides | Source and label |
|---|---|---|---|---|---|
| 2040 | 31 Midbrain | PAG | Periaqueductal grey | midline | edlow2023 `AAN_PAG` |
| 2050 | 31 Midbrain | IC | Inferior colliculus | both | sitek2019 5, 6 |
| 2060 | 31 Midbrain | mRt | Midbrain reticular formation | both | edlow2023 `AAN_mRt_L`, `_R` |
| 2070 | 31 Midbrain | PPN | Pedunculopontine nucleus | both | edlow2023 `AAN_PTg_L`, `_R` |
| 2080 | 31 Midbrain | SC | Superior colliculus | both | bianciardi2024 `SC_l`, `SC_r` |
| 2090 | 31 Midbrain | CnF | Cuneiform nucleus | both | bianciardi2024 `CnF` |
| 2110 | 32 Pons | LDT | Laterodorsal tegmental nucleus | both | edlow2023 `AAN_LDTg` |
| 2120 | 32 Pons | PB | Parabrachial complex | both | edlow2023 `AAN_PBC` |
| 2130 | 32 Pons | PnO | Pontine reticular nucleus, oral part | both | edlow2023 `AAN_PnO` |
| 2140 | 32 Pons | SOC | Superior olivary complex | both | sitek2019 3, 4 |
| 2150 | 32 Pons | SubC | Subcoeruleus | both | bianciardi2024 `SubC` |
| 2230 | 33 Raphe nuclei | ROb | Raphe obscurus | midline | bianciardi2024 `ROb` |
| 2240 | 33 Raphe nuclei | RPa | Raphe pallidus | midline | bianciardi2024 `RPa` |
| 2800 | 34 Medulla | CN | Cochlear nuclei | both | sitek2019 1, 2 |
| 2810 | 34 Medulla | ION | Inferior olive | both | bianciardi2024 `ION` |
| 2820 | 34 Medulla | Ve | Vestibular nuclei | both | bianciardi2024 `Ve` |
| 2830 | 34 Medulla | VSM | Viscero-sensory-motor nuclei (solitary tract and dorsal vagal nuclei) | both | bianciardi2024 `VSM` |
| 2840 | 34 Medulla | sMRt | Superior medullary reticular formation | both | bianciardi2024 `sMRt` |
| 2850 | 34 Medulla | iMRt | Inferior medullary reticular formation | both | bianciardi2024 `iMRt` |
| 2900 | 43 Deep cerebellar nuclei | Dn | Dentate nucleus | both | diedrichsen2009 29, 30 |
| 2910 | 43 Deep cerebellar nuclei | Int | Interposed nucleus | both | diedrichsen2009 31, 32 |

- A bilateral member written as `X` means `X_L` and `X_R` for edlow2023 and `X_l` and `X_r` for
  bianciardi2024 (file names end in `_MNI152_1mm_v2p0.nii` and `.nii.gz`).
- Shareable: 11 structures, 21 shapes. Local only: 10 structures, 18 shapes.
- Placing the cochlear nuclei under Medulla is a judgment call for the owner's doctor review: they
  lie at the junction of the pons and medulla.
- Left out: fastigial nucleus (too faint), raphe magnus (11 voxels in the Navigator), pontine nuclei
  and gracile and cuneate nuclei (no source draws them).
- In the shareable build the Navigator structures are left out with their ids kept in `ids.lock`,
  exactly as the glands are (C4 section 4.2).

## 4. Build changes

### 4.1 Masks from several files

A label source may list `members`: binary mask files inside its archive, each becoming one label of
that source. Structures refer to such a label by the member's short name (for example
`left = "AAN_PTg_L"`), as tract structures refer to tract files.

- A member is a voxel set: every nonzero, non-NaN voxel belongs to it.
- Members must share one grid; a member on another grid is a build error naming it.
- Where two members of one source overlap, the voxel goes to the member listed first in the recipe.
  The build report states how many voxels each source lost this way.
- Members not referred to by any structure are not listed and not read.
- A `members` source has no `member` and no `label_names`; giving both is a build error.

### 4.2 Manual downloads

A source may set `manual = true` with `url` naming the page to download from and `download` naming
the expected file name.

- The build looks for the file in its download cache folder for that checksum
  (`~/.cache/cns-atlas/sources/<sha256>/<file name>`), and also accepts it from a folder given with
  `--manual-dir`.
- Missing file: the build stops before any work with one line per missing source, naming the page
  and the folder to put the file in.
- Wrong checksum: refused, as for automatic downloads.
- A normal build needs `edlow2023`; only `--local` needs `bianciardi2024`.
- The two zips the owner downloaded into the project folder are moved into the cache during
  implementation; they are already excluded from git locally.

### 4.3 Fine grids

A source may set `crop = true`. The build then scans the image slab by slab to find the box around
its kept labels and reads only that box (plus one voxel), with the affine shifted to match. The
Sitek image is never held whole in memory. The cropped image is meshed on its own grid and resampled
to the 1 mm label volume for slices, as other native sources are.

## 5. Routes

| Route | Words-only station | Becomes |
|---|---|---|
| auditory | Cochlear nuclei | 2800, same side |
| auditory | Inferior colliculus | 2050, opposite side |
| cerebellar | Dentate nucleus | 2900, opposite side |
| acetylcholine | Pedunculopontine and laterodorsal tegmental nuclei | 2070 and 2110 |
| fear | Periaqueductal grey | 2040 |
| hunger | Nucleus of the solitary tract | 2830 (local builds); words only in the shareable build |

- Station texts in `atlas_src/knowledge/en/pathway-*.md` do not change by a single byte.
- The hunger station relies on the existing rule that a station whose structures are all left out
  is shown as a words-only station.

## 6. Credits and permission

- Each new source has its citation, licence and link in `sources.json` and the About box.
- A permission email to the Bianciardi lab asking to ship the Navigator nuclei goes into
  `review/emails/04-brainstem-navigator.md`, shown to the owner for approval and sent by the owner.
- When permission arrives, the Navigator source follows C4 section 6 (set redistribution, add the
  licence notice, remove local only, rebuild).

## 7. Testing

Toy atlas (fast):
- A `members` source maps each mask to its structure; overlapping masks give the voxel to the first
  member and report the count; a member on another grid and a source with both `member` and
  `members` are build errors.
- A missing manual source stops the build with the page and folder named; a wrong checksum is
  refused; a present one is used; `--manual-dir` is honoured; a normal build does not ask for a
  local-only manual source.
- A `crop = true` source is read only around its labels (a test checks the box and that values
  outside it are never read) and gives the same shapes as an uncropped read.
- A priority -1 native source never changes an existing label in the label volume.

Real atlas (slow):
- Normal build: 306 shapes (285 + 21); every existing shape and the existing label volume are
  identical to before; no Navigator file is opened.
- `--local` build: adds the 18 Navigator shapes to the glands.
- Centres near known MNI positions (within 6 mm): inferior colliculus (plus or minus 5, -35, -10),
  cochlear nuclei (plus or minus 13, -41, -44), dentate (plus or minus 14, -60, -34), periaqueductal
  grey (0, -30, -8), inferior olive (plus or minus 5, -37, -52); each new structure appears in the
  slice view.
- Routes: the six stations are shapes; their texts are byte-identical; in the shareable build the
  hunger station is words only.
- Build memory: reading the Sitek image stays under 1 GB of the build process.

Budgets unchanged: first frame under 2 s, the app's own memory under 400 MB, selection under 7 ms.

## 8. Scope

In scope: sections 2 to 7.

Out of scope: descriptions for the new nuclei, new route stations, replacing existing shapes with
better sources, the fastigial nucleus, raphe magnus, the pontine nuclei, the gracile and cuneate
nuclei, the spinal cord (C2).
