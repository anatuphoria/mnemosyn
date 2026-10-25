# Building the atlas

The atlas package (`atlases/cns/`, built locally, not committed) contains `metadata.json`,
`structures.json`, `sources.json`, `collections.json`, `pathways.json`, the labelled volumes and
their MRI templates in `volumes/`, packed meshes at three levels of detail in `meshes/`, and
descriptions in `knowledge/`. The format is described in
`docs/specs/2026-10-11-atlas-foundation-design.md`.

To change the atlas, edit `atlas_src/` and rebuild:

- `structures.toml`: the hierarchy, ids, names, synonyms and source labels. Ids never change
  and are never reused; `ids.lock` records every published id.
- `knowledge/en/<id>.md`: one description per concept, with `status = "draft"` or
  `"reviewed"`, citing keys from `knowledge/references.toml`.
- `recipe.toml`: sources with pinned checksums and licences.
- `pathways.toml`: the routes, one step per station, crossing or relay, with the side of each
  station relative to the start (`same`, `opposite` or `midline`).
- `knowledge/en/pathway-<key>.md`: one description per route with an Overview and one
  `Step N` section per step, each with one `Role:` and one `Lesion:` line; `{same}` and
  `{opposite}` become "left" or "right". Behaviour routes (`sides = "both"`,
  `texts = "behaviour"`) use one `Role:`, one `Disorders:` and at most one `Drugs:` line.
- `timelines/<route>.toml`: a schematic hormone timeline for a route: curves of relative level
  over time and marks that tie moments to steps.
- `cells/<key>.toml`: a cell view: the structures it belongs to, its layers as curves on a flat
  drawing, the cell types with where they sit and which traced neurons to draw them from
  (NeuroMorpho id, paper, download address and checksum), the arrows, and the steps of its Basic
  and Full levels. `knowledge/en/cells-<key>.md` holds one section per cell, layer, box and step.

The build refuses to package a source without a redistribution licence, a description that
cites a missing reference, a reference without a DOI, URL or ISBN, a changed or reused id,
a labelled structure without voxels, or a pathway with an unknown structure, a station with
no shape on a side, or a description that does not match its route. It never accepts a recipe
setting it would ignore; mistakes of the same kind are listed together, each with what to do.

A source whose authors have not yet allowed sharing can be marked `local_only = true` in
`recipe.toml`. A normal build leaves it out, so the result can be shared; `--local` includes it,
and the app then shows "local build, not for sharing" in its title and About box. Such a package
may be packaged for your own machines but must never be shared or published.

Some sources cannot be downloaded by a script and are marked `manual = true`. The build then
stops and names the page to download each file from and the folder to put it in
(`~/.cache/cns-atlas/sources/<checksum>/`); `--manual-dir <folder>` takes them from a folder
instead. Every build needs the Harvard Ascending Arousal Network Atlas (CC0, from Dryad); only
`--local` needs the Brainstem Navigator (from NITRC, after accepting its licence).

Traced neurons for cell views come from NeuroMorpho.Org under CC BY 4.0. The build downloads each
file, checks its checksum, keeps only the cell body and dendrites, lays the cell flat on its two
widest axes with its main dendrite pointing up, and simplifies the lines; the result goes into
`cells.json`. A view naming an unknown layer, cell, arrow or structure, a step that uses a cell
of the other level, or a text missing a section stops the build with the file and item named.
