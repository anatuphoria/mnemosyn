# Navigation, Selection and About Box (audit fix, project 1 of 6)

Date: 2026-10-18
Status: described in discussion; builder check done; awaiting the owner's review of this document
Branch: `spinal-cord` (C2 stays unmerged until every audit item is fixed)
Audit: the 2026-10-13 audit, items 10 to 16 (selection, camera, highlight, speed) plus
two owner requests (moving the scene, the About box)

## 1. Why

Using the 3D view feels inconsistent. You cannot slide the scene, only rotate and zoom. Picking
Brain, Tracts or Spinal cord behaves three different ways: the camera moves for some parts and not
others, tracts appear for some groups and then stay on, and a large selection just turns pale. Big
selections are slow (46 to 153 ms against a 7 ms budget). The About box lists every source's full
citation and grows taller than the screen.

The goal is that the same action always does the same thing, the scene can be moved freely, and
selection is instant.

Later projects, not part of this one: smooth surfaces and the brainstem body (2), the cord and
colours (3), speed of routes and first frame (4), slices (5), build checks and the booklet (6). The
terminal viewer is left alone: the owner is moving it to its own repository.

## 2. Moving around (owner's decision)

- Mouse wheel: zoom toward the point under the mouse pointer, not the screen centre. Over empty
  background, zoom toward the screen centre.
- Left drag: rotate (as today).
- Right drag: pan (slide the scene).
- R: back to the start view (as today).
- Clicking still selects; a click is a press and release without dragging, as today.

## 3. The camera never moves on its own (owner's decision)

- Selecting anything, from the tree, a 3D click, a slice click, a route step, a quiz or search, never
  moves the camera.
- F ("Frame selection", new shortcut and menu entry) moves the camera to show the current selection
  whole: one nucleus, a group, the whole cord or the whole brain. It keeps the viewing direction and
  only changes the target and the distance.
- With nothing selected, F frames the brain, like R but keeping the viewing direction. (Clicking the
  background keeps the selection, as today, so this case is rare.)
- The C2 rule that framed selections outside the brain box (`_frame_selection`, `framing_outside`)
  is removed.
- The start view (and R) frames the brain, as built in C2.

## 4. One selection behaviour for every part

### 4.1 Where tracts live (owner's decision)

- The top-level group 70 "Tracts" moves inside Brain (parent 2), as spinal tracts (group 80) already
  sit inside Spinal cord. Its subgroups, including Cranial nerves, move with it. Ids do not change.
- So Brain contains its tracts and Spinal cord contains its tracts; Central nervous system contains
  both.

### 4.2 When tracts are shown

- Tracts stay hidden unless asked for: T toggles them all; selecting a tract or a group whose shapes
  are all tracts shows those tracts.
- Tracts shown by a selection are hidden again as soon as the selection moves to anything that does
  not contain them (another tract included), unless T had turned tracts on. Tracts turned on with T
  stay on until T again. So browsing tract after tract shows one tract at a time.
- Selecting a mixed group (Brain, Spinal cord, Central nervous system) does not show its tracts; the
  highlight covers the visible shapes only.

### 4.3 Highlight

- One look for every selection, whatever its size: one bright outline around the outer edge of the
  whole selection (a group gets one outline, not one per member), and the selected shapes keep their
  own colour at full strength.
- The outline shows through everything in front of it, like an x-ray (owner's decision): a
  selection buried inside the cortex, the cord or behind the cerebellum is always outlined where it
  is, so picking it from the tree, a quiz or a route step always changes the picture.
- Builder's choice of technique (for example a mask pass plus a screen-space edge). It may draw the
  selected shapes again from the existing mappers and data for a mask or stencil pass; it must not
  build duplicate actors or meshes, and must not slow rotation noticeably for a whole-brain
  selection. The outline must stay visible against both the black background and neighbouring
  shapes.
- Emphasis inside routes (the lit station) uses the same look.
- The current "lighten every selected shape" overlay is removed.

### 4.4 Speed

- Selecting anything, including Central nervous system, Brain and Tracts, takes under 7 ms
  including the redraw it causes, measured on the owner's local build.
- The first time tracts are shown may build the tract layer once; that build is measured separately
  (budget 500 ms, as today).
- The selection performance test times the selection plus its redraw, for single structures and for
  groups 1, 2, 3, 70 and 80. `render()` returns before the frame is drawn, so the test calls
  `processEvents()` and then the render window's `WaitForCompletion()`.

## 5. About box (owner's request)

- A proper window of fixed size that fits on a 1366 x 768 screen and never grows with content.
- Two tabs:
  - About: app name and version, atlas package name and version, the disclaimer, and in a local
    build a one-line note that it contains data not yet allowed to be shared.
  - Data sources: a scrolling list, one row per source (13 in the owner's local build, templates
    included): what it gives the atlas (for example "Spinal cord"), a short author and year, the
    licence, and a "local only" tag where it applies. Selecting a row shows the full citation and
    the link below the list.
- "What it gives the atlas" is a new short `provides` text on every source and template in
  `recipe.toml`, carried into `sources.json`; packages without it show the source title instead.
- F1 opens it, as today.

## 6. Out of scope

Smooth surfaces, the brainstem body, cord and colour fixes, route entry and first-frame speed,
slice zoom, build-check gaps, the booklet, the terminal viewer.

## 7. Testing

- Navigation: wheel over a structure moves the focal point toward that point; right drag changes
  the camera position and focal point by the same offset (pan) without changing the view direction;
  left drag still rotates; a click still selects.
- Camera: selecting from the tree, a 3D click, a slice click, a route step and a quiz answer leaves
  the camera unchanged; F frames a single structure, a group, the cord and the whole brain; F with
  nothing selected frames the visible scene.
- Tree: group 70 is a child of Brain; Brain's subtree contains every brain tract; Central nervous
  system has Brain and Spinal cord as children.
- Tracts: selecting a tract shows it and selecting a non-tract afterwards hides it again; tracts
  turned on with T stay on through selections; selecting Brain or Spinal cord shows no tract.
- Highlight: no duplicate actors or meshes are added on selection; a buried structure (a thalamic
  nucleus inside the cortex) changes the rendered image when selected; a group gets one outline.
- Speed: selection plus redraw under 7 ms (median) for single structures and groups 1, 2, 3, 70, 80
  on the local build.
- About: the window fits 1366 x 768 with 12 sources; both tabs present; selecting a source shows its
  citation.

## 8. Calls made by the builder of this document (not the owner)

- F as the shortcut for framing; F with nothing selected frames the brain.
- One outer outline per selection; a second mask pass over the existing mappers is allowed.
- Zoom toward the screen centre over empty background.
- Tracts shown by a selection hide when the selection moves to anything that does not contain them.
- A hand-written `provides` text per source for the About list.
