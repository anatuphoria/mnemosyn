# Performance

| Measure | Result |
|---|---|
| Desktop, local build with 395 shapes, integrated GPU (Radeon 680M) | 2.7 ms per frame while turning, so the display refresh rate (144 Hz) is the limit |

The 3D view draws the grey matter as a few composite objects of neighbouring structures, so showing
or hiding shapes rebuilds only the pieces that changed, and picks with the GPU; the 3D view and the
slice redraw once per action, after every change in it has been made; it switches to a lighter level
of detail when the scene exceeds 3 million triangles. Right after the first frame the app loads the
slice volumes, their label centres and the outlines in small idle steps, so nothing is loaded the
first time it is used. Budgets enforced by `pytest -m perf`: opening a 5,000-structure atlas under
200 ms, search under 10 ms per keystroke, the label layer of a slice under 5 ms. With the real atlas
built, `pytest -m slow` checks, each in a fresh process on the median of repeated runs: first frame
under 2 s; the app's own memory under 400 MB, also once everything is loaded (shared libraries such
as Qt and VTK not counted, since how much of them is resident depends on what the system has
cached); selecting a structure under 7 ms and under 16 ms with its redraw; the CNS, Brain or Spinal
cord under 20 ms with its redraw, the first time too; the Tracts group under 40 ms; hiding, showing
or isolating any group under 30 ms; one step of the slice slider, of a slice zoom or of a slice pan
under 16 ms; a generated 3,500-structure scene at 60 fps or more; a quiz starting under 100 ms,
moving on under 50 ms and checking a typed answer under 1 ms; tracts built the first time they are
shown under 500 ms, then shown or hidden in under 50 ms, a slice with every tract outlined redrawn
in under 10 ms; entering a pathway or switching its side under 100 ms, every step of every pathway
under 30 ms, and a playing timeline updated in under 5 ms per tick. The build report records the
build time and peak memory. Each timed action is also compared with its own record in
`.timing-baseline.json` (written on the first run, kept out of git): one at least 25% and 1 ms
slower than its record fails even under its limit. After a slowdown you accept, run the tests with
`--reset-timing-baseline` to record the new times.

