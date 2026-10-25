# Hippocampus cells (sub-project E, part 1: E1)

Date: 2026-10-25
Status: approved
Builds on: `docs/specs/2026-10-12-pathways-design.md` (B4: route data, knowledge texts, the
Pathways panel), `docs/specs/2026-10-12-behaviour-circuits-design.md` (D1: Play, speed, Space)
and `docs/specs/2026-10-19-slices-looks-design.md` (zoom and pan in a 2D view)

## 1. Why

Sub-project E takes Mnemosyn from structures down to neurons. Today the smallest thing in the
app is a structure such as the hippocampus; E lets the person open a structure and see the cells
it is made of and how the signal travels between them.

The owner asked for the hippocampus first, with Ramón y Cajal's 1911 drawing of it as the model.
What they want from that drawing is the cell shapes and the arrows that show which way the
signal flows. In the view they want to watch the signal play through and click cells to learn
them. The hippocampus is the first of several structures that will get a cell view, so the
format must let the next one (cerebellum, cortex, retina) come in as data, not new code.

## 2. Decisions made in discussion

1. The look is a flat slice through the hippocampus in the app's dark colours, the layers as
   named coloured bands, arrows for the pathways (option B of three; the owner chose it over a
   Cajal ink style and over cells in 3D). The clickable mockup is kept at
   `.superpowers/brainstorm/46497-1792941408/content/cells-prototype-v2.html` (outside git).
2. Cell shapes come from real traced neurons, flattened onto the slice, not drawn by hand.
3. Play sends a pulse along the circuit one step at a time, like Play on a route.
4. Clicking a cell type shows what it is.
5. While the Cells panel is open, the 3D view draws a thin plane through the hippocampus where
   the slice is cut.
6. Two levels of detail: Basic (the classic four step loop) and Full (the rest of the real
   circuit, including the main interneurons).
7. The Cajal ink style and 3D cells are later work, not part of E1.

## 3. What the person sees and does

1. With the hippocampus selected, the Info panel shows a "Show cells" link and the View
   toolbar's "Cells" action is enabled. Either opens the Cells dock, titled
   "Cells: Hippocampus", on the right next to the other docks.
2. The dock holds the slice drawing, a Basic / Full switch at the top, play controls under the
   drawing and a text area at the bottom, laid out as in the mockup.
3. The drawing is one fixed drawing of the hippocampus as seen from the front, with medial and
   lateral on the sides the 3D view shows from the front: drawn for the left hippocampus and
   mirrored as a whole (text kept readable) when the right is the side shown.
4. The 3D view shows a translucent plane through the hippocampus on the side last selected
   (left if none), perpendicular to the hippocampus's long axis, through the middle of its body.
   The plane disappears when the dock closes.
5. Play (or Space) runs the steps of the current level. In each step a glowing pulse travels the
   step's arrows, the arrows brighten, the cells that receive the signal light up and the
   caption for the step shows beside the controls. Pause stops mid step; the start button goes
   back to the beginning; Left and Right move one step; the speed menu offers the same speeds as
   route playback. After the last step playback stops and the caption says it is done.
6. Clicking a cell type lights every cell of that type, fades the rest and shows its text: name,
   layer, what it receives, what it sends, the species and source of the traced cell, and
   references. Clicking a layer band shows the layer's text. Clicking an input or output box
   (entorhinal cortex, subiculum) shows its text. Clicking empty space clears the selection.
   Clicking anything stops playback.
7. The drawing zooms with the wheel, pans with right drag and F fits it to the dock, as in the
   slice view.
8. Switching between Basic and Full stops playback, keeps any selected cell type if it exists in
   the new level and redraws.

## 4. The hippocampus content

All texts, captions and the choice of steps are drafts for the owner's doctor review, like every
other text in the app, with references from `atlas_src/knowledge/references.toml`.

### 4.1 Layers drawn

1. Cornu ammonis as one curved band from the subiculum end through CA1 and CA2 to CA3, its tip
   entering the hilus. Sublayers: stratum oriens, stratum pyramidale, stratum lucidum (CA3 only,
   where mossy fibres run), stratum radiatum, stratum lacunosum moleculare.
2. Dentate gyrus as a C shaped band around the CA3 tip: molecular layer, granule layer, hilus.
3. CA1, CA2, CA3 and DG named on the drawing. CA2 is a narrow named zone with no cell type of
   its own in E1.
4. The hippocampal fissure between the DG molecular layer and CA1 lacunosum moleculare.
5. Two boxes outside the slice: Entorhinal cortex (input, with layer II and layer III as the two
   origins of its arrows) and Subiculum (output).

### 4.2 Cell types

Basic level:

1. Dentate granule cell (granule layer).
2. CA3 pyramidal cell (stratum pyramidale of CA3).
3. CA1 pyramidal cell (stratum pyramidale of CA1).

Full level adds:

1. Parvalbumin basket cell: perisomatic inhibition. One cell type with two placements, in
   CA stratum pyramidale (CA3 and CA1) and at the border of the granule layer and hilus in the
   DG; clicking it lights both, and it has one text.
2. Oriens lacunosum moleculare (O-LM) cell (stratum oriens of CA1): its axon inhibits the
   distal dendrites in lacunosum moleculare.
3. Hilar mossy cell (hilus): excitatory, feeds back onto granule cells. Amended while building:
   NeuroMorpho holds no traced mossy cells, so the HIPP cell (hilar perforant path associated
   cell, inhibitory, its axon in the outer molecular layer) takes its place (decision 65).

### 4.3 Steps

Basic:

1. Entorhinal cortex layer II to granule cells, along the perforant path.
2. Granule cells to CA3 pyramidal cells, along the mossy fibres.
3. CA3 pyramidal cells to CA1 pyramidal cells, along the Schaffer collaterals.
4. CA1 pyramidal cells to the subiculum and back to the entorhinal cortex deep layers.

Full:

1. Entorhinal cortex layer II to granule cells, and on to CA3, along the perforant path.
2. Granule cells to CA3 pyramidal cells (mossy fibres), and to mossy cells and basket cells in
   the hilus.
3. Mossy cells back onto granule cells; basket cells inhibit the granule cells. As built: basket
   cells inhibit the granule cell bodies and HIPP cells their outer dendrites.
4. CA3 pyramidal cells excite each other through recurrent collaterals.
5. CA3 pyramidal cells to CA1 pyramidal cells (Schaffer collaterals); basket cells inhibit CA1
   around the cell bodies.
6. Entorhinal cortex layer III directly to the distal dendrites of CA1 (temporoammonic path).
7. CA1 pyramidal cells excite O-LM cells, which inhibit the distal dendrites of CA1.
8. CA1 pyramidal cells to the subiculum and back to the entorhinal cortex deep layers.

Excitatory arrows are warm (the amber of the mockup) with an arrowhead; inhibitory arrows are a
cool colour with a flat bar end, so the two read apart at a glance.

## 5. Neuron shapes

### 5.1 Source

NeuroMorpho.Org (RRID:SCR_002145), licensed CC BY 4.0 according to its terms of use page
(https://neuromorpho.org/useterm.jsp, checked 2026-10-25). Its terms ask for three citations:
the original paper of each reconstruction, "NeuroMorpho.Org (RRID:SCR_002145)" and Tecuatl C,
Ljungquist B, Ascoli GA (2024) Accelerating the continuous community sharing of digital
neuromorphology data, FASEB Bioadvances 6(7):207 to 221, doi 10.1096/fba.2024-00048. All three
appear in the cell text and in the sources list. This data is shareable, so it goes into the
normal build and the public downloads; `atlas_src/LICENSES/CC-BY-4.0.txt` already exists.

### 5.2 Which cells

For each cell type, one to three reconstructions, chosen by these rules in order:

1. Adult, soma present, NeuroMorpho's `experiment_condition` includes "Control" (as the
   archive labels it, which counts tissue from surgery that the archive calls control), and
   NeuroMorpho's physical integrity field says the dendrites are complete or moderately
   complete.
2. Human when NeuroMorpho has a cell meeting rule 1; otherwise rat; otherwise mouse. A query on
   2026-10-25 found human CA1 pyramidal cells (archive DeFelipe, Benavides-Piccione et al. 2020,
   Cerebral Cortex, doi 10.1093/cercor/bhz122, dendrites only) and human dentate granule cells
   (archive Allen Cell Types), and no human CA3 pyramidal cells or hippocampal interneurons, so
   those come from rat (or mouse) archives.
3. Prefer a cell whose dendrites lie mostly in the slicing plane, so it flattens well.

The cell text states the species, archive, NeuroMorpho id and paper. Axons are not drawn from
the reconstructions: the arrows stand for the axons, so reconstructions without an axon are fine.

### 5.3 Flattening

At build time each reconstruction (the standardised SWC file NeuroMorpho serves) is:

1. downloaded by its NeuroMorpho id and checked against a pinned sha256, cached like every other
   source;
2. reduced to soma and dendrites;
3. projected onto the plane of its two largest principal axes, then rotated so its main axis
   (soma to the centre of the apical or main dendritic tree) points up;
4. simplified (Douglas Peucker) to a tolerance that keeps the shape at the largest zoom of the
   panel while keeping the whole package addition small (budget in section 9);
5. written as polylines with a width per segment taken from the traced diameter.

Cells are drawn scaled to fit their layer, not at true size, and the cell text says so (human
CA1 cells are much larger than rat CA3 cells, so true scale would mislead in a mixed species
drawing). In the drawing each cell is placed on its layer with its main axis along the local
layer normal, apical side towards the layer it reaches.

## 6. Source format

Built for any structure; nothing in it names the hippocampus.

### 6.1 `atlas_src/cells/<key>.toml`

One file per cell view. The hippocampus file is `atlas_src/cells/hippocampus.toml`. It holds:

1. `key`, `name`, and `structures` (the atlas ids whose selection offers this view; for the
   hippocampus, 1350).
2. `plane`: how to place the slice plane in 3D. For E1 one rule, `"mid-body"`: perpendicular to
   the first principal axis of the structure's mesh on the chosen side, through the centre of
   the middle third along that axis.
3. `layers`: each with a key, name, colour group and a curve (points in a fixed drawing frame,
   for example 1000 by 700 units) and a width; sublayers as offsets across the band.
4. `boxes`: key, name, position, and named ports where arrows start or end.
5. `cells`: key, name, level (`basic` or `full`), one or more placements (each a layer, the
   span of the layer the cells occupy and a number of copies), and a list of reconstructions
   (NeuroMorpho id, NeuroMorpho name, sha256 of the SWC, species, archive, paper doi and a short
   citation).
   Copies reuse the reconstructions in turn, with mirroring and a small rotation so the row does
   not look stamped.
6. `flows`: key, kind (`excitatory` or `inhibitory`), from (cell or box port), to (cell, layer
   or box port), label, and the curve the arrow follows.
7. `levels.basic.steps` and `levels.full.steps`: each step lists its flows and the cells that
   light up at the end of the step. Full may reuse Basic's flows.

### 6.2 `atlas_src/knowledge/en/cells-<key>.md`

Knowledge format (front matter with `key = "cells-hippocampus"` and `status = "draft"`), with
sections `## Overview`, `## Cell <key>`, `## Layer <key>`, `## Box <key>`,
`## Basic step <n>` and `## Full step <n>` (each step section is the caption). Every cell,
layer, box and step in the TOML has exactly one section, and no section names an unknown key.

### 6.3 Sources

`atlas_src/cells/<key>.toml` is the single authority for its reconstructions, including their
sha256; `recipe.toml` is not changed (its sources are label volumes). The build writes one
source record "NeuroMorpho.Org" into `sources.json` with `provides = "Neuron shapes"`, licence
CC BY 4.0, the RRID, the Tecuatl 2024 citation and the list of original papers used, so it shows
in the build report. The README data licence table and the website get one NeuroMorpho row that
names the papers. The structure Info panel is not changed (its source lines are geometry
sources); the per cell citations show in the Cells panel's text for that cell.

### 6.4 Build errors

Each names the file and the item: unknown layer, cell, box, port or flow key; a step naming a
flow or cell missing from its level; a Full only cell lit in a Basic step; a cell view naming an
unknown structure id or a structure without shapes on either side; a reconstruction whose
download fails its sha256; a reconstruction with no soma or no dendrites after reduction; a text
section missing or extra; a curve with fewer than two points.

## 7. Package and loader

1. The build writes `cells.json` (the views, flattened cell shapes inline) into the atlas
   package. Missing file means no cell views; `format_version` stays 1, so older readers
   (including the separate terminal app's copy of `cns_atlas`) ignore it.
2. `cns_atlas` gains a `cells` module with frozen dataclasses for the view, layers, boxes,
   cells, flows and steps, `Atlas.cell_views()`, `Atlas.cell_view_for(structure_id)` and
   `Atlas.cell_text(key)`. The file is read on first use, not at startup.

## 8. Desktop

1. New `cns_desktop/views/cell_panel.py`: a `QGraphicsView` drawing the layers, boxes, cells and
   arrows as vector items, with hit testing by item. It talks only to `AppState`, like every
   other panel.
2. `AppState` gains the open cell view key, the level, the selected cell item and the play
   state, with signals, so the 3D view can show and hide the plane.
3. The 3D view adds the slice plane as one actor, created when the dock opens.
4. Keys: while the Cells dock is visible, Space, Left and Right act on it; opening it pauses a
   playing route. When the dock closes they return to route playback as today. The Cells action
   gets a keyboard shortcut not already used (C is Centre slice).
5. The dock stays open, on the hippocampus, when the person selects another structure; it closes
   with its close button or the Cells action.

## 9. Budgets and tests

1. Startup unchanged: nothing about cells loads before the first frame, and the timing baseline
   must not move.
2. Opening the dock: first time at most 300 ms, later times at most 50 ms (owner's machine,
   median of the usual timing runs).
3. Playback: every animation frame at most 16 ms.
4. Package growth from `cells.json`: at most 2 MB.
5. Tests, alongside the existing suites: format errors of 6.4 each raised; loader round trip;
   every hippocampus item has its text; the panel shows a cell's text on click; Play walks the
   captions of both levels in order; level switch keeps a shared selection; the plane appears
   on open and goes on close; Space goes to the Cells dock only while it is visible; the timing
   checks above in the timing suite.

## 10. Documentation

1. `docs/decisions.md`: the decisions of section 2 and the calls of section 11 the owner accepts,
   in the same commit as the work they describe.
2. README data licence table and the website's sources and Building the atlas pages gain the
   NeuroMorpho row. The website's feature list mentions the Cells view.
3. The specialist booklet is not changed in E1; the new texts join it in a later edition.

## 11. Calls made by the designer, for the owner to check

1. Species rule: human where NeuroMorpho has a usable adult cell, else rat, else mouse, stated
   on each cell's text.
2. Cells drawn scaled to their layer, not at true size.
3. Axons are the arrows, not traced axons.
4. Full level's extra cells are basket, O-LM and mossy cells; other interneuron types wait.
5. The slice plane sits through the middle of the hippocampal body, perpendicular to its long
   axis, on the side last selected.
6. No quiz on cells in E1.
7. The dock stays open when another structure is selected.
8. Rendering with Qt's 2D graphics view rather than VTK.
9. The basket cell is one cell type placed in two regions.
10. "Control" and "complete" read from NeuroMorpho's own condition and integrity fields.
11. NeuroMorpho recorded as one source with its papers listed; per cell citations in the Cells
    panel, not in the structure Info panel.
12. The drawing mirrors for the right hippocampus.

## 12. Left to the builder

The exact drawing of the layer curves (they should read like a coronal section through the body
of the human hippocampus, as in Cajal and in standard atlases); how many copies of each cell;
the exact colours within the app's palette; the pulse look; the shortcut key; the text wording
(drafts in any case); the choice of individual reconstructions within the rules of 5.2.

## 13. Out of scope and anti goals

Out of scope: other structures' cell views, the Cajal ink style, 3D cells, quizzes on cells,
membrane or spike simulation, connecting cell views to route stations.

Anti goals (failures even if everything technically works): cartoon cells; a tangle of
dendrites in which the signal cannot be followed; an arrow or text that states more than the
references support; neuron data shipped without a licence that allows it; any slowdown of
startup or of the existing views.
