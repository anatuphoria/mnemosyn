# Atlas Foundation Design (sub-project A)

Date: 2026-10-11
Status: approved in discussion, awaiting review of this document

## 1. Context

The project is a free desktop 3D atlas of the whole central nervous system. It is first a
personal study tool, and is also published for students and anyone else to use.

Stated goals:

- Study modes: explore in 3D and read, slices like atlas plates, pathways and circuits,
  self-testing.
- Performance must be excellent, not merely acceptable, and is enforced by benchmarks.
- Research-grade traceability: real coordinates in mm and a recorded source, version and
  licence for every structure and every claim.
- English first, with every text ready for translation (Arabic expected later).
- Descriptions are drafted in working sessions from open, cited sources, then reviewed by
  the project owner. Every claim carries a reference.
- A visible disclaimer: not built by a specialist, made for studying, feedback welcome.
  GitHub Discussions for feedback come later, not in this sub-project.

Technology (already decided): PySide6 + VTK/PyVista + pyqtgraph for the desktop app, Python
for data building and future simulations. The Textual terminal app stays as a companion
and gets no new features.

## 2. Roadmap

| Id | Sub-project | Delivers |
|---|---|---|
| A | Atlas foundation (this document) | Data format, build tool, loader, current 116 regions migrated |
| B | Scalable viewer | Composite renderer, hierarchy tree, slice view, pathway view, quizzes |
| C | Whole-CNS content | Brainstem, cerebellum, spinal cord and tract sources; full descriptions |
| D | Physiology layer | Values on structures, one end-to-end simulation, linked charts |
| E | Neuron scale | Neuron morphologies, action potential simulation and animation |
| F | Packaging (parallel) | Installer, dedicated environment, size reduction |

Each sub-project gets its own design, plan and implementation cycle.

## 3. Decisions

- Own package format with a BrainGlobe-compatible core. BrainGlobe field names and meanings
  are kept for the core files so BrainGlobe users and tools can read them. Extensions live in
  extra fields and extra files.
  Rejected: BrainGlobe format as-is (format in transition to OME-Zarr, one citation per
  atlas, no mesh levels of detail); glTF + JSON (no labelled volume, not readable by
  research tools).
- BrainGlobe currently publishes one human atlas (`allen_human_500um`) and no human spinal
  cord atlas, so it can serve as a source, not as the whole solution.

## 4. Structure model

Every structure is one record in `structures.json`:

```json
{
  "id": 1201,
  "acronym": "HIP-L",
  "name": "Left hippocampus",
  "structure_id_path": [1, 2, 10, 120, 1200, 1201],
  "rgb_triplet": [235, 150, 150],
  "kind": "region",
  "side": "left",
  "concept": 1200,
  "synonyms": ["Hippocampus L", "left hippocampal formation"],
  "xrefs": {"uberon": "UBERON:0001954", "aal": "Hippocampus_L"},
  "sources": ["aal-spm12"]
}
```

Core fields (BrainGlobe): `id`, `acronym`, `name`, `structure_id_path`, `rgb_triplet`.

Extension fields:

- `kind`: one of `group`, `region`, `nucleus`, `tract`, `ventricle`, `nerve-root`. The viewer
  styles kinds differently (tracts as tubes, ventricles translucent).
- `side`: `left`, `right`, `midline`, or `none` for grouping nodes.
- `concept`: id of the side-independent concept node. Left and right structures share one
  concept, which owns the description. Absent on structures that are their own concept.
- `synonyms`: alternative names and abbreviations, used by search and self-testing.
- `xrefs`: identifiers in standard ontologies (UBERON, NeuroNames) and the original label
  name in each source atlas.
- `sources`: ids from `sources.json` that the geometry comes from. Group nodes have none.

Rules:

- `id` is a positive integer below 65536 (the volume stores labels as uint16). An id never
  changes and is never reused after a structure is removed.
- Exactly one root (id 1, "Central nervous system"). Every other structure has exactly one
  parent; the hierarchy follows standard neuroanatomy (CNS > brain / spinal cord > ...).
- Structures are stored in depth-first order, so every subtree is a contiguous index range.
- Cross-cutting systems (limbic system, basal ganglia) are collections, not tree parents.
- Pathways are ordered chains of structure ids, stored separately.

`collections.json`:

```json
[{"key": "limbic-system", "name": "Limbic system", "members": [1200, 1300, 1400]}]
```

`pathways.json`:

```json
[{"key": "spinothalamic", "name": "Anterolateral (spinothalamic) pathway",
  "steps": [5101, 3310, 1510]}]
```

Collections and pathways may reference concept ids or sided ids. Their descriptions use the
knowledge format with the key as file name (`knowledge/en/pathway-spinothalamic.md`).

## 5. Package layout

```
atlases/cns/
  metadata.json
  structures.json
  sources.json
  collections.json
  pathways.json
  volumes/
    brain.nii.gz
  meshes/
    lod0/  vertices.npy  normals.npy  faces.npy  index.npy
    lod1/  (same files)
    lod2/  (same files)
  knowledge/
    references.toml
    en/<id>.md
```

`metadata.json` holds the BrainGlobe keys with BrainGlobe meanings (`name`, `citation`,
`atlas_link`, `species`, `symmetric`, `resolution` in micrometres, `orientation`, `shape`,
`version`, `additional_references`) plus extension keys: `format_version`,
`coordinate_units` ("mm"), `licence` (licence of the descriptions and curated data,
"CC BY 4.0"), and `volumes`, a list of `{file, space, affine_to_world}` records.

`sources.json`:

Examples in this document use placeholder sources and references.

```json
[{"id": "example-atlas", "title": "Example labelled atlas",
  "authors": "Author A, et al.", "year": 2020, "version": "1.0",
  "doi": "10.0000/example", "url": "https://example.org/atlas", "licence": "CC BY 4.0",
  "redistribution": true}]
```

Volumes: `volumes/` holds one or more labelled NIfTI files. Each voxel stores a structure
id. Each volume records its coordinate space and an affine into the shared world frame
(mm). The brain volume is in MNI152 space; the spinal cord volume (sub-project C) will use a
cord template space with its own affine.

Meshes, per level of detail, are packed arrays loaded with memory mapping:

- `vertices.npy`: float32 (N, 3), world coordinates in mm.
- `normals.npy`: float16 (N, 3), unit vertex normals.
- `faces.npy`: uint32 (M, 3), indices relative to the owning structure's first vertex.
- `index.npy`: structured array, one row per structure with geometry:
  `id`, `vertex_start`, `vertex_count`, `face_start`, `face_count`.

Detail levels: `lod0` is the smoothed surface capped at 20,000 faces per structure, `lod1`
is 25 percent of `lod0`, `lod2` is 5 percent of `lod0`, never below 64 faces.

Knowledge files, one per concept, collection or pathway:

```
+++
id = 1200
status = "draft"
+++
## Function
Forms new declarative memories and supports spatial navigation [textbook2018].

## Connections
Main input from the entorhinal cortex; main output through the fornix [review2013].

## Clinical
Early atrophy in Alzheimer disease [review2013].
```

- The header is TOML (`tomllib`, standard library). It holds `id` for structures and `key`
  for collections and pathways. `status` is `draft` or `reviewed`;
  the app shows a "Draft" badge on unreviewed entries.
- Sections are `Function`, `Connections`, `Clinical`. A section may be omitted.
- Citations are reference keys in square brackets. Every key must exist in
  `references.toml`; the app renders them as numbered references under the entry.
- Translations live in `knowledge/<lang>/`; a missing file falls back to English.

`references.toml`:

```toml
[textbook2018]
authors = "Author A, Author B"
title = "Example Neuroscience Textbook"
edition = "6th"
year = 2018
publisher = "Example Press"
isbn = "9780000000000"
```

Every reference has at least one of `doi`, `url`, `isbn`.

## 6. Build pipeline

Source inputs, committed to git under `atlas_src/`:

- `recipe.toml`: sources with download URL, sha256 checksum, licence, `redistribution`
  flag and merge priority; output settings (resolution, levels of detail).
- `structures.toml`: the curated hierarchy. Each structure lists its id, names, synonyms,
  xrefs, kind, side, parent, and `labels`: which value in which source maps to it.
- `ids.lock`: every id ever published and the list of retired ids.
- `knowledge/`: the authored descriptions and `references.toml`.

The tool lives in `tools/build_atlas/` (replacing `tools/fetch_atlas.py`) and runs:

1. Fetch: download each source to a local cache and verify its checksum. A mismatch fails
   the build.
2. Register: resample each source volume into its target space. For AAL (already MNI152)
   this is the identity: the first build uses the AAL native 2 mm grid as the output grid.
3. Merge labels: write one labelled volume per space. Where sources overlap, the higher
   priority source wins.
4. Meshes: for each structure, marching cubes on its label mask in mm, Taubin smoothing,
   decimation to the three levels using an explicit face count, vertex normals, packing.
5. Validate. The build fails if any of these hold:
   - a label value in a volume has no structure, or a structure with `labels` has no voxels;
   - the hierarchy has more than one root, a cycle, or a missing parent;
   - an id is above 65535, duplicated, retired, or present in `ids.lock` but missing
     without being retired;
   - a structure with geometry lists no source;
   - a source has no licence or `redistribution` is not true;
   - a knowledge file cites a missing reference, has an unknown id, or a malformed header;
   - a reference has none of `doi`, `url`, `isbn`.
6. Write the package and `build-report.md` (counts, sizes, warnings).

Output is deterministic: the same inputs produce byte-identical files (sorted keys, fixed
seeds, no timestamps).

Dependencies: nilearn, scikit-image and trimesh move to a new `atlas-build` optional
dependency group. The runtime needs numpy and nibabel only.

The built package `atlases/cns/` is committed to git while it stays under 20 MB. Above that
it is published as a GitHub release asset instead.

## 7. Runtime loader

New package `cns_atlas/`, free of Qt and rendering code, used by both apps.

```python
atlas = Atlas.open("atlases/cns")
atlas.structures            # tuple of Structure, depth-first order
atlas.get(1201)             # Structure
atlas.children(1200)        # tuple of ids
atlas.ancestors(1201)       # ids from root to parent
atlas.subtree(1200)         # slice over the depth-first order
atlas.search("hippo")       # ids ranked: exact, prefix, substring
atlas.knowledge(1201, "en") # Entry (sections, references, status) via concept, English fallback
atlas.mesh(1201, lod=1)     # vertices, normals, faces views
atlas.label_at((x, y, z))   # structure id at a world point in mm, or None
atlas.collections, atlas.pathways, atlas.sources
```

- Opening reads the JSON files and memory-maps mesh arrays. Volumes load on first use.
- `cns_desktop` replaces `atlas_data.py` with this loader; its tree shows the real hierarchy
  and its info panel shows sections, status badge and numbered references.
- `brain_tui` gets an adapter that builds its `Region` objects from the package (converting
  mm to its unit scale). `data/manifest*.json`, `assets/meshes/` and the old manifest code
  are deleted.

Error handling:

- Missing or invalid package: a clear error naming the file and the problem.
- Structure without a knowledge entry: "No description yet".
- Missing level of detail: nearest available level.
- Missing translation: English.

## 8. Performance budgets

Checked by benchmarks that fail when a budget is exceeded:

| Measure | Budget |
|---|---|
| `Atlas.open` with 5,000 structures | under 200 ms |
| Desktop app start to first frame | under 2 s |
| `search` per keystroke, 5,000 structures | under 10 ms |
| Selection to all panels updated | under 7 ms |
| Resident memory with the full CNS loaded | under 500 MB |

The frame-rate target for the whole CNS (display refresh, 144 Hz, on the integrated GPU)
belongs to sub-project B; this sub-project provides the levels of detail it needs.

## 9. Disclaimer

Shown on first launch, in an About dialog, under every description, and in the README:

> This atlas is a personal study project. It was not built or reviewed by a neuroanatomy
> specialist and may contain errors. It is not for diagnosis or treatment. Corrections and
> feedback are welcome.

## 10. Testing

- Loader tests on a small synthetic package (a few ellipsoid structures) generated inside
  the tests; no downloads.
- Build tests on small synthetic NIfTI sources through the full pipeline.
- One test per validation rule in section 6, each proving the failure is caught.
- Determinism test: two builds, byte-identical output.
- Real-data test with the AAL source, marked slow, run on demand.
- Benchmarks on a generated 5,000-structure package, enforcing section 8.
- Content test: every knowledge entry cites at least one reference.
- Desktop and terminal app tests updated to the new package, plus tests for the hierarchy
  tree and for references in the info panel.

## 11. Scope of sub-project A

In scope:

1. Verify the redistribution licence of the first source (AAL SPM12). If it does not allow
   redistribution, select a replacement with a verified open licence before building.
2. Package format, build tool, `cns_atlas` loader.
3. The 116 regions rebuilt through the pipeline; both apps reading the new package; old
   manifest code and files removed.
4. Knowledge format with references, demonstrated on about five complete, referenced
   entries. The existing 24 unreferenced built-in descriptions are removed.
5. The disclaimer in all four places.
6. Build-only dependencies moved to the `atlas-build` group.

Out of scope: composite renderer, slice view, pathway view, quizzes (B); new sources and
the full description set (C); simulations (D); neurons (E); installer work (F).

## 12. Open item

The AAL licence has not been verified yet. It is the first implementation task, and its
outcome decides the first source. The design does not change either way.

## 13. Amendments made during planning (2026-10-11)

1. First source: AAL3 (GIN "AAL 3v2", AAL3v1 1 mm volume), verified GNU General Public License
   (no version stated; the package ships the GPL-3.0 text). Output grid: AAL3 native 1 mm.
   166 labelled structures.
2. Meshes are built with VTK through PyVista. Build dependencies: vtk, pyvista, scipy.
   nilearn, scikit-image and trimesh are no longer used.
3. The built package measures about 35 MB, above the 20 MB limit in section 6, so it is not
   committed. `atlases/` is ignored and built locally with `python -m tools.build_atlas`.
4. A source may set `verify_tls = false` (GIN's certificate chain is incomplete). Its sha256
   is pinned and always verified.
5. The desktop view renders with the stored vertex normals (startup budget, see the plan ledger).
