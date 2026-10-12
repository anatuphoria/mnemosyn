# Finishing Pass: Activity Controls and Open Items

Date: 2026-10-12
Status: approved in discussion, awaiting review of this document
Builds on: B4 pathways, C4 glands and D1 behaviour circuits (all merged), and the deferred items
of every review so far

## 1. Context

The owner asked to move the playback controls into the Activity panel, where the change is
shown, and to finish every open issue and deferred item. Each item below was checked against the
code on 2026-10-12; items already fixed (template volume lookup, Name it re-select order, shade
wording) are not repeated.

## 2. Playback controls in the Activity panel

- While a pathway is open, the Activity panel shows a control bar above the chart: Back,
  Play / Pause and Next buttons; a speed choice (½×, 1×, 2×, default 1×); a step readout
  ("Step 3 of 6: Adrenal cortex"); and, for routes with a timeline, a time readout
  ("30 / 120 min").
- The bar is hidden when no pathway is open.
- The Pathways panel keeps its step list, texts, Back and Next; its Play button is removed.
- `Space` toggles play in both panels.
- Speed scales playback: a step every 3 s / speed without a timeline; a whole timeline in
  `play_seconds` / speed with one. Changing speed does not pause.
- Entering a pathway shows the Activity dock if it was hidden; leaving restores its previous
  visibility.

## 3. Behaviour circuits

1. The status bar names no side for both-sides routes.
2. Timeline marks must have strictly increasing times (equal times are a build error).
3. A timeline `route` that is not text is a build error, not a crash.
4. Only left clicks inside the chart's plot area seek; legend, title and axes do not.
5. Tests cover the "needs at least one curve" and "marks must be within 0 and the duration"
   errors.
6. The stress route starts at the amygdala: amygdala 1400, paraventricular nucleus 2510,
   pituitary gland 2700, adrenal cortex (text), hippocampus 1350, medial prefrontal and
   subgenual cingulate 1090, 1300. Its texts keep their content in the new order and its
   timeline marks each step: 0, 2, 8, 25, 50, 70 min.

## 4. Pathways

7. After meshing, the build checks again that every station lights a meshed shape (not only a
   labelled one); a failure is a build error.
8. Unknown top-level keys in `pathways.toml` (for example `[[pathway]]`) are a build error.
9. Enter on the pathway list opens the pathway.
10. Leaving a pathway draws the 3D view once.
11. The step budget is checked on the 90th percentile of steps, not the median.
12. A station can be marked `crossing = true`; its label shows ✕ like a crossing step. The
    middle and superior cerebellar peduncles (cerebellar steps 4 and 7) are marked.
13. Selecting a structure whose shapes overlap a step's lit shapes (for example a station's
    parent concept) goes to that step and keeps the selection.
14. Going to a step shows its lit shapes even if they were hidden from the tree during pathway
    mode (leaving still restores the saved visibility).
15. Entering a route: find and remove avoidable work so entering stays under 100 ms with
    margin on the real local atlas; if no saving is found, record the measurements.

## 5. Local-only sources

16. A normal build's report does not list drop entries of left-out sources.
17. Leaving out a structure also leaves out all its descendants (closure, repeated until
    stable).
18. The glands spec says priority -1, matching the code.
19. `local_only` on a `[[tracts]]` or `[[templates]]` table is a build error ("only label sources
    can be local-only").
20. The loader refuses a `local_only` metadata value that is not a list of texts.
21. The About box lists a local-only source id even when its citation is missing.
22. A test checks that a normal build of a tree with a local-only source equals a build of the
    same tree without it, apart from `build-report.md` and `knowledge/`.

## 6. Older items

23. Zero-length vertex normals (830 in the current atlas) are repaired in the build: a vertex
    whose normal is near zero gets the direction from the mesh centre to the vertex. The build
    report counts repaired normals.
24. Opening a malformed package gives an `AtlasError` naming the problem, not an internal
    error: metadata that is not an object, `format_version` that is not exactly the integer 1,
    duplicate structure ids, structures not in depth-first order, and unreadable mesh files.
25. Terminal viewer: descriptions show numbered citations, a reference list and a Draft line
    for drafts; an atlas that fails to open prints its message and exits with status 1; an
    `--atlas` path given explicitly that does not exist is an error (the built-in shapes are
    used only when no path is given and the default atlas is missing).
26. Build report: adds the package size in MB and a warnings section (repaired normals,
    3D-shape-only structures, or "none"); counts use the right singular or plural.
28. The downloader's nested `with` becomes one statement.

## 7. Testing

Each item gets a test that fails before its change, except 15 (measured) and 18 and 28 (text
and style). The real atlas is rebuilt locally and the slow suite run at the end.

## 8. Scope

In scope: sections 2 to 7. Out of scope: new content, physiology simulation, packaging.
