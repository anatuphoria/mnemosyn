# Slices and looks (audit fix, project 5 of 6)

Date: 2026-10-19
Status: approved by the owner on 2026-10-19
Branch: `spinal-cord` (C2 stays unmerged until every audit item is fixed)
Audit: the 2026-10-18 audit, sections 3 and 4 (old audit item 24)

## 1. Why

The app works, but several things look wrong or get in the way of reading it:

- Cord slices are tiny: the cord is about a fifth of the slice panel's width in axial view and a
  sliver in coronal and sagittal, and there is no way to zoom in.
- The stress-axis timeline is squashed flat: its note and two references sit under the chart and
  take its height, so the hormone curves are almost invisible in a 950-pixel window.
- The Activity panel shows a random sine wave titled "PLACEHOLDER data (no model yet)" for every
  structure and every route without a timeline, taking a fifth of the window.
- In the Name it quiz a small buried structure (a hypothalamic nucleus) shows in 3D only as a tiny
  ring on the cortex; only the slice makes the question answerable.
- The status bar gives the wrong mouse hint ("right-drag/wheel zoom, middle/shift-drag pan"; right
  drag pans since project 1) and shows developer read-outs: last frame time, GPU name, visible
  count. The README repeats the wrong hint and its key table lacks F.
- Tree names are cut off at the default panel width ("Hippo...", "Anterior ci..."), the info panel
  names the drawing kind ("cover, midline", "shell, midline"), and long route step names are cut
  off with a sideways scroll bar.

The app is for students and researchers, so what it shows must be true to the data and easy to
read. Nothing here changes the atlas data.

## 2. Slices: zoom and pan

The owner wants the same moves as the 3D view.

- The mouse wheel zooms in and out around the pointer.
- Right-drag pans.
- Left-click still selects the structure under the pointer; hovering still names it.
- The zoom and pan stay while the slider moves and while selections change, so a person can step
  through the cord at one zoom.
- Switching between Brain and Spinal cord, or between axial, coronal and sagittal, fits the slice
  back to the whole volume (each shows a differently shaped picture).
- F (frame selection) with the pointer over the slice panel fits the slice back to the whole
  volume; with the pointer anywhere else it frames the selection in 3D as today.
- The slice opens fitted to the whole volume, as today. Nothing zooms on its own (the owner turned
  down zooming to the cord automatically).
- Centre on selection (C) keeps working; when zoomed it also brings the selection into view in the
  slice. (Builder's call how: pan so its centre sits in the middle is enough.)

Builder's calls: the zoom step per wheel notch (match the 3D view's feel), the zoom limits (at
least close enough that a 0.5 mm cord voxel is about 20 screen pixels; never out further than the
whole volume), and how the slice panel tells F apart (pointer position or focus).

## 3. Slices: what zoomed-in pixels look like

Decided by the owner on the builder's advice, for both students and researchers:

- Colour labels are drawn as sharp squares, one per voxel, at every zoom. Each square is a real
  decision in the atlas data; smoothing the edges would draw boundaries nobody measured. Research
  viewers (FSLeyes, ITK-SNAP, 3D Slicer) show labels this way.
- The grey MRI template under the labels is drawn smooth (interpolated between voxels), as research
  viewers do for intensity images; this makes the cord's shape easy to read.
- Outlines (selection and tracts) stay sharp too.
- This applies to both volumes, the brain (Colin27, 1 mm) and the cord (PAM50, 0.5 mm).
- The Labels opacity slider keeps working on the label layer only.

This needs the template and the labels drawn as separate layers (today `compose` blends them into
one image); the builder decides how, within the slider limit below.

## 4. Activity panel and the timeline

- The Activity panel is hidden unless a route with a timeline is open (today: stress, body clock,
  hunger). Opening such a route shows it; leaving the route, or switching to a route without a
  timeline, hides it. The owner chose this on 2026-10-18.
- The placeholder sine wave and its title go away completely.
- While hidden, the panel's entry in the panels menu is disabled (builder's call: disabled or
  removed, as long as it cannot show an empty panel).
- When it appears it is tall enough to read the curves: about a third of the window height
  (builder's call on the exact size; the curves must be clearly readable at a 950-pixel window).
- Layout B, chosen by the owner from mockups: the note and its references sit in a narrow column to
  the right of the chart inside the Activity panel, scrolling if long; the chart takes the full
  height of the panel. The time read-out ("0 / 120 min") stays with the chart.

## 4a. Route play controls move to the Pathways panel

Today Back, Play, Next and the speed picker sit in the Activity panel and every route uses them, not
only routes with a timeline. The owner chose on 2026-10-19 to move them into the Pathways panel,
just above the step list, for every route, drawn as the familiar media control symbols instead of
words:

- Back, play or pause, next: the standard media icons from the system theme (skip back, play,
  pause, skip forward), each with a tooltip naming it and its key, for example "Play (Space)".
- Speed: a compact picker showing "½×", "1×", "2×", as video players show it.
- The step read-out ("Step 1 of 6: Amygdala") sits with the controls.
- Space plays and pauses during any route, wherever the keyboard focus is, except while typing in
  a text field; Back and Next stay disabled at the first and last step, as today.

## 5. Name it quiz fades the rest

- While a Name it question is shown (typed or choose from 4), the asked structure stays solid and
  everything else fades, the same way a route step fades all but its stations. The owner chose this
  on 2026-10-18.
- Builder's call, for the owner to check: Flashcards fade the same way, since they also show one
  structure and ask its name. Find it does not fade: fading would point at the
  answer.
- The tract quiz keeps its current look (grey matter dimmed, the asked tract shown).
- The asked structure is always drawn during its question, even if the person had hidden it
  before the quiz (the hidden state comes back when the quiz ends, as other state does today).
- Leaving the quiz, or revealing the answer, restores the normal look (builder's call whether the
  fade stays while the answer is shown; restoring at the next question or at the end is fine).

## 6. Status bar and README

The owner chose this on 2026-10-18.

- Normally: the selected structure's name and the correct mouse hint: left-drag rotates, right-drag
  pans, the wheel zooms, F frames the selection, click selects.
- During a quiz or a route it says so, as today ("quiz in progress, Esc ends the quiz"; "pathway:
  name, step n of m, Esc leaves the pathway").
- Removed: last frame time, GPU name, visible count. `--bench` still prints frame times and the GPU
  for the builder.
- The README gets the same hint and adds F (frame selection) to its key table.

## 7. Small fixes

Builder's calls, accepted by the owner:

- Tree names: the Structures panel opens wide enough for the common names, and every tree item
  shows its full name in a tooltip.
- Info panel: drop the drawing kind ("cover", "shell", "nucleus" and so on); keep only the side
  ("left", "right") when there is one, and nothing for midline structures.
- Route steps: long step names wrap onto a second line; no sideways scroll bar in the step list.

## 8. Limits and tests

- Speed limits from decision 43 stay; in particular one slice slider step stays under 16 ms with
  the new layers, and zooming or panning a slice also stays under 16 ms per step. Every new timing
  goes through the timing record (decision 44).
- Each behaviour above gets a test on the toy atlases; the slow suite runs five times in a row
  without a false failure before hand-over.
- Every owner choice above goes in the decision log in the same commit that builds it.

## 9. Out of scope

Build checks, lint, leftovers from projects 2 and 3, README beyond the hint and key table, and the
review booklet (project 6). New descriptions for brainstem and spinal structures (doctor review).
