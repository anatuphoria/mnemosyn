# Smooth Surfaces and the Brainstem Body (audit fix, project 2 of 6)

Date: 2026-10-18
Status: described in discussion; builder check done; awaiting the owner's review
Branch: `spinal-cord` (C2 stays unmerged until every audit item is fixed)
Audit: `.superpowers/audit-2026-10-13.md` items 1, 2, 6 and 9

## 1. Why

Every shape looks like stacked 1 mm cubes: terraces on the cortex, hippocampus and nuclei
(audit item 1). The brainstem has no body: AAL3 has no midbrain, pons or medulla, so the brainstem
is a cloud of floating nuclei and the spinal cord hangs below it with a gap (item 2). Sources on
different grids also look unevenly smooth (item 6), and 910 zero normals are repaired at each build
(item 9).

The goal is surfaces that read as real organ surfaces, and a solid brainstem the nuclei sit inside,
continuous with the cord.

## 2. Smooth surfaces (all builds)

The usual practice in anatomy atlases (owner accepted it as the standard choice):

- Each structure's binary mask is smoothed before its surface is extracted (a Gaussian of 2 mm, see
  section 6, on a float copy of the mask, contoured at 0.5), then the surface is lightly evened with the
  existing Taubin pass. The 1 mm staircase disappears; gyri and sulci stay.
- Accuracy beats smoothness for small structures: a small nucleus is blurred less, so its enclosed
  volume stays within 10% of its voxel volume and its centre moves less than 1 mm. Structures that
  would vanish or split are never blurred into nothing.
- Every structure is smoothed on its own; neighbours never merge, and touching parts keep their own
  edges.
- The same rule applies on every source grid (1 mm, 0.5 mm, 0.1 mm), with the blur expressed in
  millimetres so smoothness looks the same across sources.
- Zero normals at pinch points should mostly disappear; the build report keeps counting any left.
- Level-of-detail settings (`lod0_max_faces`, `lod_fractions`, `min_faces`) are the builder's call
  if smoothing changes how decimation looks; the face budget of the scene must not grow by more than
  10%.

## 3. Brainstem body (local builds only)

### 3.1 Source (owner's decision)

- Iglesias JE et al. (2015), Bayesian segmentation of brainstem structures in MRI, NeuroImage 113:
  184-195, doi:10.1016/j.neuroimage.2015.02.065; the MNI ICBM 2009c (symmetric) version from the
  FreeSurfer wiki page "Subfield atlases in MNI-ICBM 152 space", file `Brainstem.zip`
  (sha256 `f6ad672136102669955ee803f27c188a5e172a326a61fb9818d12fb4707fe5c2`), member
  `BrainstemProbs.MNIsymSpace.nii.gz` with `BrainstemProbs.MNIsymSpace.names.txt`.
- Grid 53 x 67 x 85 voxels of 1 mm, RAS, 4D probabilities: channel 0 background, 1 medulla
  (FreeSurfer 175), 2 pons (174), 3 superior cerebellar peduncle (178), 4 midbrain (173).
- No licence stated: `local_only`, like the glands, the Brainstem Navigator and PAM50. A permission
  email to the authors goes into `review/emails/` for the owner to send.
- A voxel belongs to the brainstem when the brainstem as a whole (every non-background channel
  summed) is at least 0.5; it then goes to the most likely of the three kept parts. This leaves no
  cracks along the seams and fills the place of the dropped superior cerebellar peduncle channel
  (the atlas already has that peduncle as a tract from HCP-1065). Parts never overlap.

### 3.2 Structures

- Three midline regions, one inside each existing group (my wording, easy to change): Midbrain
  body (in group 31 Midbrain), Pons body (in 32 Pons), Medulla body (in 34 Medulla). The groups and
  their nuclei stay as they are; the shareable build leaves the three bodies out and keeps every
  nucleus.
- They rank below every existing label in the brain volume, so they never overwrite a nucleus in
  the slices, and are meshed on their own grid so their 3D shape stays whole.
- No descriptions yet.

### 3.3 See-through bodies (owner's decision)

- The three bodies are see-through by default, like glass, so the nuclei inside stay visible. They
  use a new structure kind, `shell`, for context shapes drawn see-through; the bodies are the only
  shells for now.
- A click on the brainstem selects the nucleus under the mouse when there is one, and the body only
  where no nucleus is behind it. The same holds for Find quizzes ("click it in the 3D view").
- Everything else treats a shell like any structure: the tree, hide, isolate, F to frame, the x-ray
  outline when it is selected, slices, quizzes and routes.
- How see-through (opacity) is the builder's call, checked on rendered images: the body's shape must
  read clearly and the nuclei inside must stay easy to see. Shells must not slow rotation or
  selection beyond the project 1 budgets.

### 3.4 Where the bodies meet other shapes

- The two atlases do not line up exactly: the bodies reach into the cerebellum (about 430 voxels of
  medulla into lobule IX, 400 of pons into lobules III, IV-V and X, 150 of midbrain into vermis
  III). The cerebellum wins: the bodies are trimmed against every non-brainstem label, so no two
  surfaces cross or flicker.
- The medulla (to z -78) overlaps the top of the PAM50 cord (from about z -67): in a local build with
  both, the medulla is trimmed where the cord begins, so they meet without a gap or overlap.

## 4. Out of scope

The bamboo look of the cord segments and the colours (project 3), speed (project 4), slices
(project 5), build-check gaps and the booklet (project 6), descriptions of the new parts.

## 5. Testing

- Smoothing on a toy volume: a staircase surface becomes smooth (a curvature or normal-angle
  measure drops), a sphere's enclosed volume stays within 10% of its voxel volume, a small blob
  keeps volume within 10% and centre within 1 mm, two touching blobs stay two separate shapes.
- Real build: every existing structure still has a shape; scene faces within 10% of before; zero
  normals reported; the slice labels unchanged (smoothing only changes surfaces).
- See-through: shells are drawn see-through; a click over a nucleus inside a body selects the
  nucleus, a click on the body away from any nucleus selects the body; a Find quiz accepts a 3D
  click on a brainstem nucleus.
- Brainstem: a local build adds the three bodies with centres near (0, -23, -13) midbrain,
  (0, -28, -33) pons and (0, -41, -55) medulla; the normal build leaves them out and keeps every
  nucleus; no body overwrites a nucleus label in slices; at the junction no medulla vertex lies
  more than 1 mm inside the cord's top segment.
- A visual check of rendered close-ups (cortex, deep nuclei, brainstem junction) before handing
  over.
- Budgets: first frame under 2 s, own memory under 400 MB, selection budgets from project 1.

## 6. Calls made by the builder of this document (not the owner)

- 2 mm of blur (one voxel left the hand-drawn AAL3 ridges on the cortex; checked on renders; owner accepted it, 2026-10-18), less for
  small structures, volume within 10%, centre (of the enclosed volume) within 1 mm.
- Names Midbrain body, Pons body, Medulla body.
- Highest-probability assignment at 0.5 and dropping the peduncle channel.
- Whole-brainstem assignment (no cracks), trimming against the cerebellum and at the cord.
