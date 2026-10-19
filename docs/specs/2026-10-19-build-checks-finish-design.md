# Build checks and finish (audit fix, project 6 of 6)

Date: 2026-10-19
Status: written from the audits at the owner's request; approved by the owner on 2026-10-19; built on `spinal-cord`
Branch: `spinal-cord` (C2 merges only after this project and the owner's yes)
Audit: the 2026-10-18 audit, sections 5 and 6 (old audit items 28 to 31, 33 and 35), plus the
minors deferred from projects 2, 3 and 5

## 1. Why

Projects 1 to 5 fixed what a person sees and feels. What is left is what goes wrong quietly: the
atlas build accepts recipe settings it then ignores, some bad inputs crash with a raw Python error
instead of a build message, nothing guards that a rebuild leaves existing shapes untouched, the lint
run reports 138 findings nobody reads, a list of small defects was deferred from earlier projects,
and the review booklet that specialists are reading says things that stopped being true.

The goal: after this project the branch can be merged with nothing known to be wrong, and anything
that does go wrong in a build says so in plain words.

## 2. Build checks

The recipe (`atlas_src/recipe.toml`) and the build (`tools/build_atlas`) must never accept a setting
and silently do something else. Every case below becomes a `BuildError` with a message that names
the source, the setting and what to do, or is made to work; the builder decides which per case,
preferring "make it work" where the meaning is obvious.

1. Multi-file sources (`members`) silently ignore `drop`, `crop`, `mask` and `label_names`, and turn
   non-string paths into strings (old 28). Either apply them to every member or reject them for
   multi-file sources with a clear message.
2. A non-numeric `threshold` raises a raw `ValueError`; a negative `margin` shrinks the crop;
   `margin` without `crop` is ignored; a tracts setting on a skipped volume would raise `KeyError`
   (old 29). All become build errors (or, for margin without crop, a build error saying margin
   needs crop).
3. A 4D image member with more than one frame raises `ValueError` instead of a build error (old 30).
4. A station only partly left out of a shareable build loses its `crossing` and `fallback` (old 31):
   keep them.
5. Leftovers from projects 2 and 3: `load_parts` raises `IndexError` for an out-of-range channel
   (build error instead); an empty cord piece is written without an error (build error, naming the
   segment); a zero-voxel tract is missing from the report's "small shapes" (list it); member
   loading is duplicated in `labels.py` (one helper).

Each case gets a test with a tiny recipe on the toy sources; the message text is part of the test.

## 3. A rebuild leaves existing shapes alone

Old 33: there is no permanent check that an atlas rebuild keeps every existing structure id, name,
label and shape the same; it was checked by hand for C3.

- The build report gains a comparison with the previous build in the same output folder (if there
  is one): structures added, removed, renamed, and shapes whose voxel count or centre moved more
  than a small tolerance (builder's call; a few percent and about 1 mm).
- Removed or renamed structures, or ids that changed meaning, fail the build unless the recipe says
  the change is intended (builder's call how, for example a list of accepted changes in the
  recipe); moved shapes are reported, not failed, since smoothing changes are legitimate.
- A test builds the toy atlas twice and checks that nothing is reported, then changes one toy label
  and checks that it is.

## 4. Lint at zero

138 lint findings, mostly import order: the code puts the project's own packages and the test
helper modules in one alphabetical block, and the lint settings call the helpers third-party.

- Change the lint settings to match the code's existing style (the test helper modules counted as
  first-party, wrapped imports allowed), not the code to match the settings.
- Fix the real findings by hand: unused imports and variables, the cast-to-int ones in
  `slice_panel.py`, anything else that is a genuine defect.
- A fast test runs the linter on the repository and fails on any finding, so the count stays at
  zero (skipped if the linter is not installed).

## 5. Deferred minors

From project 2 and 3 hand-overs:
- The medulla body shows in slices below where its 3D shape is trimmed; trim the slice label the same
  way (or clip it to the same range).
- Zooming over a see-through body costs two picks per wheel step; one is enough.
- The cord stays faded on the Find summary screen; restore it when the summary shows.

From project 5's final review:
- The slice can be panned completely out of view; keep part of the slice in view.
- A fitted slice keeps a small margin although the code asks for none; make the code and the
  result agree (no margin, the builder's call).
- A sideways trackpad swipe zooms the slice; ignore horizontal wheel movement.
- With Labels opacity at 0, a filled tract over an empty voxel divides by zero and prints a warning;
  guard it.
- F over the slice on an atlas without slices does nothing; frame the 3D view instead.
- The fast timing test still times `compose`, which the app no longer draws with; time the label
  layer (`overlay` with tracts) instead and keep `compose` only as the reference in the equivalence
  tests.
- The Space branch left in the Pathways panel's key handling never runs; remove it.
- The smooth-and-sharp slice test only checks class attributes; check pixels on a zoomed grab
  (label edges hard, template values in between).
- A midline structure's info line is a bare colour square; show the swatch beside the name instead
  and drop the empty line (builder's call how).

Builder's call, found while checking project 5: the route tooltips say "Back (Left)" and
"Next (Right)", but the arrow keys only work while the Pathways panel has the keyboard focus. Make
Left and Right window keys during a route, like Space, except while typing in a text field.

## 6. Documentation and the review booklet

- README: one read-through against the app as it now is (keys, panels, quizzes, routes, slices,
  build commands, test commands, performance limits), fixing anything stale. The website is built
  from it.
- Review booklet (`review/`, never committed; old 35): the booklet specialists already have says the
  cerebellar, acetylcholine, fear, hunger, motor, touch and pain spinal stations are words only;
  they now have shapes. Correct every statement that is no longer true, and add a short "changed
  since the first edition" page. Keep the 50 question numbers and wording exactly as they are, since
  the live Google Form and its answers are keyed to them. Rebuild the PDF with `review/tools`.
  Whether to send the new edition is the owner's call; the builder writes a short cover email to
  `review/emails/` for the owner to send, nothing is sent.
- The terminal viewer (`mnemosyn-tui`, its own repository): copy the current `cns_atlas` reader
  into it so it understands the "cover" kind, run its tests, and commit locally there; pushing it
  is the owner's call.

## 7. Before the merge

- A final whole-app audit by the 2026-10-18 method (timings on the owner's build, screenshots in
  every mode, a scripted run of every selection, hide, isolate, route step, quiz mode and slice
  view, lint, and every earlier audit item rechecked), written next to the earlier audits (outside
  git).
- The fast suite green, the slow suite five times in a row green.
- Merging `spinal-cord` into `main` and pushing are the owner's decisions; the builder stops at a
  hand-over report that lists anything still open.

## 8. Out of scope

- Build time (about 6 minutes local), peak memory (2.4 GB) and package size (97 MB): packaging,
  sub-project F.
- Descriptions for the brainstem and spinal structures, and every draft text: the doctor review.
- The AAN PTg_L data artefact: the owner's report to the AAN authors.
- The 154 zero normals repaired at build: they are repaired; no visible effect.
- Speeding up the quiz fade (accepted by the owner, decision 49).

## 9. Decisions to log

Every owner choice made while building goes in `docs/decisions.md` in the same commit; this design
itself adds none until the owner approves it, and then one entry for the build-check rule ("the
build never ignores a setting") and one for the lint-at-zero rule.
