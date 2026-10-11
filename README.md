# 3D TUI Brain Model 🧠

Rotate, slice, isolate and study 100+ brain regions **in the terminal** - GUI parity, no GUI needed.

## Quickstart

```bash
pip install -e .
brain-tui
# or without install:
python -m brain_tui.app
```

Force a graphics mode:

```bash
PAR_TERM_GRAPHICS=halfblock brain-tui   # pure Unicode, works everywhere
PAR_TERM_GRAPHICS=kitty brain-tui       # hi-fi shaded PNG (Kitty/WezTerm/Ghostty)
```

## Controls

Letters are lowercase unless written with `Shift+`.

| Action | Keys |
|---|---|
| Rotate (inertial - eases to stop) | arrows / `hjkl` or mouse-drag |
| Zoom / Pan | `+`/`-`, `wasd` or wheel / shift+drag |
| Spin showcase (default OFF) | `r` |
| Select | click, `Tab` / `Shift+Tab` cycle, `/` search-bar (hidden until `/`; `Enter` commits, `Esc` cancels) |
| Move selected | `m` move-mode: arrows or `wasd` move, `PgUp`/`PgDn` depth, `Esc` exits |
| Isolate / Hide / Unhide | `i` / `Shift+H` / `u` |
| Explode | `x` / `Shift+X` |
| Slice axial/coronal/sagittal | `1` / `2` / `3`, `,`/`.` move plane |
| Labels | `Shift+L` |
| Bookmark save/restore | `b` / `Shift+B` (views.json; restore eases to the newest view) |
| HiFi stills / Quiz | `o` / `z` (`z` again reveals the answer) |
| Help | `?` |

## Performance

The UI thread only handles input and shows finished frames. Rendering runs on a
background thread (`pipeline.py`): at most one frame is in flight, and input
that arrives meanwhile is folded into the next one, so stale frames are never
drawn. Frames become terminal lines directly (`present.py`): runs of equal cells
are merged and only rows that changed are repainted.

Measured headless at 200×60 cells, all 116 regions, during a continuous drag:

| | before | now |
|---|---|---|
| frames shown per second | ~6 | ~28-30 |
| input stall, median / p95 | ~56 / ~170 ms | ~2 / ~11 ms |
| worst input stall | ~185 ms | ~15-25 ms |

The idle app renders nothing. While dragging it uses a lighter point budget,
then snaps crisp 300ms after you stop. The splat kernel is numba-compiled with a
pure-numpy fallback. After the first frame the app freezes long-lived objects
and tunes the garbage collector; without that, Textual's per-frame line objects
cause ~70ms hitches (details in `BrainApp.on_frame_ready`).

## Desktop app (prototype)

A GPU desktop viewer for the same atlas: PySide6 (Qt) + VTK/PyVista + pyqtgraph.
It is the start of the full-CNS atlas; the terminal app above stays as a
lightweight companion.

```bash
pip install -e ".[desktop]"
cns-desktop                 # or: python -m cns_desktop
cns-desktop --bench         # full-screen spin; prints fps
prime-run cns-desktop       # use the NVIDIA GPU on hybrid laptops
```

Drag rotates, right-drag/wheel zooms, middle- or shift-drag pans, click selects.
`H` hide, `I` isolate, `U` show all, `R` reset view, `Ctrl+F` filter.

Every panel talks only to the shared `AppState` (`cns_desktop/state.py`), never
to each other. New panels (simulations, neuron scenes) plug in by connecting
to its signals. The Activity chart shows **placeholder data**: no model exists yet.

Measured on a Radeon 680M (integrated): the 116-region scene renders at the
144 Hz display cap (~1.4 ms GPU time per frame). Stress test at ~3,500
structures / 10M triangles: separate actors per structure drop to ~11 fps, the
VTK composite mapper (one actor, a block per structure) holds ~48 fps, so the
composite mapper is the path for the full CNS. A PyInstaller build works:
~960 MB installed (VTK is 554 MB of it), ~217 MB compressed.

## Full 116-region atlas

Ships with real **AAL116 anatomy** by default (`data/manifest_aal.json`, ~3MB of
decimated meshes in `assets/meshes/` - no download needed at runtime).
Rebuild/refresh it with:

```bash
python tools/fetch_atlas.py --atlas AAL116 --out data/manifest_aal.json
# needs: nilearn nibabel scikit-image trimesh (all in default deps)
```

Falls back to a 36-region procedural brain if the atlas files are missing
(`data/manifest.json`, built via `--atlas procedural`).

Rendering: FAST point-splat (default, smooth-shaded) and `o` HiFi supersampled
stills. `PAR_TERM_GRAPHICS=halfblock` forces the `suckless-st`-compatible
Unicode path.

## Layout

```
brain_tui/  app.py (Textual UI)        pipeline.py (render thread, Frame)
            renderer.py (point splat)  present.py (frame -> terminal lines)
            scene.py (camera/regions)  atlas.py (procedural + AAL116 names)
            knowledge.py (study DB)    widgets/
cns_desktop/  app.py (entry, --bench)  main_window.py  state.py (shared AppState)
              atlas_data.py (meshes -> GPU)  views/ (3D, tree, info, chart)
tools/fetch_atlas.py   data/manifest.json + knowledge.json
tests/
```

## Disclaimer

Educational visualization only - decimated meshes + summaries. **Not for diagnosis.**
Atlas ontology: Allen Brain Atlas / AAL (Tzourio-Mazoyer 2002).
