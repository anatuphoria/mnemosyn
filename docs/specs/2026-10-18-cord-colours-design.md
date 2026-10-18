# The Spinal Cord's Look and Colours (audit fix, project 3 of 6)

Date: 2026-10-18
Status: approved by the owner on 2026-10-18; built on `spinal-cord`
Branch: `spinal-cord` (C2 stays unmerged until every audit item is fixed)
Audit: `.superpowers/audit-2026-10-13.md` items 3, 4, 5, 7 and 8, plus the ridged spinal tracts seen
on the project 2 renders

## 1. Why

The cord looks like stacked bamboo: each of the 30 segments is a closed slab, so a ring shows at
every boundary, and all 30 are one beige. Grey matter tips poke out above C1. With T on, the 30 spinal
tracts are one tan column with vertical ridges, because their probability maps overlap (24% of tract
voxels sit in two or three maps). The brainstem nuclei, and other crowded groups, are nearly one
colour each, so neighbours cannot be told apart in 3D, slices or quizzes.

The goal is the usual practice of teaching atlases: one continuous cord with its segments marked as
colour bands, tracts that fit together like tiles in textbook colours, and neighbours that always
differ in colour.

## 2. One continuous cord (owner's decision)

- The cord's outer surface comes from PAM50's whole-cord mask (`template/PAM50_cord.nii.gz`, member of
  the `PAM50-r20250730.zip` already pinned for `pam50`), smoothed like every surface (2 mm blur).
  It is a new local-only source entry sharing that download, like `pam50-atlas`.
- It is cut into 30 open pieces, one per segment, along the segment boundaries of
  `PAM50_spinal_levels`. Each piece is that segment's 3D shape: no end caps, so neighbouring pieces
  meet edge to edge and no ring shows. The seams follow the boundaries cleanly.
- The surface starts at the top of C1 and ends at the bottom of S5; the 3 mm of cord mask above C1
  is dropped (the medulla body already meets C1 there).
- Segments stay ordinary structures: tree, quizzes, slices, routes and F to frame work as today.
  Clicking the cord selects the segment at that height; selecting a segment gives its band the x-ray
  outline.
- Slices are unchanged: segments still fill the spine volume from `PAM50_spinal_levels`.

## 3. Solid by default, see-through to look inside (owner's decision)

- The cord is drawn solid with its colour bands.
- It turns see-through (like the brainstem bodies, project 2) while anything inside it is in view:
  when the selection is spinal grey matter or a spinal tract (or a group of them), or while tracts are
  shown with T. It turns solid again when that ends.
- A Find quiz whose target is spinal grey matter or a spinal tract also makes it see-through, so
  the target can be clicked.
- How see-through is the builder's call, checked on renders, as for the brainstem bodies.
- While it is see-through, a click goes to the grey matter or tract behind it when there is one, as
  with the brainstem bodies; otherwise it selects the segment.

## 4. Grey matter stops at C1

The spinal grey matter (ventral horn, intermediate zone, dorsal horn) is trimmed to the segments'
extent, so nothing pokes out above C1 or below S5.

## 5. Spinal tracts fit together

- Same rule as the brainstem bodies: a white matter voxel belongs to the tracts when the summed
  probability of all 30 tract maps is at least 0.5; it then goes to the single most likely tract.
  Tracts never overlap, in 3D or in slices.
- Ties are split by side, so left and right stay mirror images: a voxel on the left never goes to a
  right tract because of list order, and the reverse.
- Each tract's shape is meshed from its own share, so the column of ridges becomes tiles that fit
  together and nothing flickers with T on.
- A tract that ends up with almost no voxels is listed in the build report.

## 6. Colours neighbours can tell apart

- Spinal segments: one hue per region (cervical, thoracic, lumbar, sacral), with neighbouring segments
  alternating light and dark, so every boundary is visible and the region reads at a glance.
- Spinal tracts: textbook convention, ascending (sensory) tracts in blues, descending (motor) tracts
  in reds and oranges, each tract a clearly different shade within its family. Ascending: fasciculus
  gracilis, fasciculus cuneatus, ventral spinocerebellar, spinothalamic, spino-olivary. Descending:
  lateral and ventral corticospinal, rubrospinal, the four reticulospinal, lateral vestibulospinal,
  tectospinal, medial longitudinal fasciculus.
- Crowded nucleus groups (brainstem, thalamus, hypothalamus, deep cerebellar nuclei): every member
  gets a clearly different colour instead of the plus or minus 15% shade, chosen so that structures
  next to each other differ most.
- Left and right of a structure keep one colour. Colours stay atlas data (`rgb_triplet`), so slices,
  quizzes and the website show the same ones. Groups not named here keep today's colours.

## 7. Out of scope

Nerve roots and rootlets (PAM50 has them; a later project), the cord's natural curve, speed (project
4), slice zoom and other slice work (project 5), build checks and the booklet (project 6),
descriptions of the cord structures.

## 8. Testing

- Toy atlas: a cord mask cut by a levels map gives one open piece per level with no end caps, whose
  edges meet the next piece's edges; together they enclose the cord mask's volume (within 10%).
- Clicking a segment piece selects that segment; the cord turns see-through when a horn is selected
  and solid again when a segment is selected; T makes it see-through; a click through the see-through
  cord selects the tract or horn behind it.
- Grey matter above the top level or below the bottom level is removed.
- Tracts: overlapping toy maps give tiles that never share a voxel; a left and right pair with equal
  probabilities on the midline split by side, so the pair stays symmetric; the 0.5 summed rule.
- Colours: neighbouring segments differ; ascending tracts are blue and descending ones red or orange;
  in a crowded group, every pair of touching members differs clearly (a colour distance threshold).
- Real local build (slow): 30 segment pieces from C1 (top near z -70) to S5; no grey matter vertex
  above C1's top; tract voxels never shared; every tract keeps a shape; left and right tract volumes
  within 5% of each other; the normal build unchanged apart from colours.
- Renders of the cord, the C1 junction, the tracts with T and the brainstem nuclei, checked before
  handing over.
- Budgets from project 1 (decision 31): selection, first frame and memory.

## 9. Calls made by the builder of this document (not the owner)

- Cutting the cord mask surface into open per-segment pieces, so picking, outlines and quizzes need
  no new code paths.
- The see-through trigger: a spinal grey matter or tract selection, a Find quiz on one, or T.
- The cord mask as its own local-only source entry.
- The summed 0.5 rule and splitting ties by side (the same rule as the brainstem bodies).
- Which tracts count as ascending or descending, as listed in section 6.
- The distinct-colour rule also covering the thalamus and hypothalamus, which have the same problem
  as the brainstem.
