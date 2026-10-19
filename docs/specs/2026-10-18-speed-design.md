# Speed (audit fix, project 4 of 6)

Date: 2026-10-18
Status: approved by the owner on 2026-10-18; built on `spinal-cord`
Branch: `spinal-cord` (C2 stays unmerged until every audit item is fixed)
Audit: the 2026-10-18 audit, section 2 (old audit items 17, 21 and 23)

## 1. Why

The owner cannot measure the app, so the builder measured it on the owner's local build. Most
actions are well inside their limits, but some are not, and a few have no limit at all:

| Action | Now | Limit |
|---|---|---|
| First step into the spinal cord in a route (motor) | 89 to 95 ms | 30 ms |
| First selection of a very large group (CNS) | 47 to 127 ms | 20 ms |
| Selecting the Tracts group (after the first build) | 35 to 51 ms | 50 ms |
| Hiding or showing the whole brain | 46 to 58 ms | none |
| One step of the slice slider, with the 3D plane | 15 to 26 ms | none |
| Timing tests inside the long slow run | fail now and then, pass alone | - |

Where the time goes (profiled):

- The first step into the cord loads the cord's three slice volumes from compressed files
  (about 45 ms) and builds its label centre table (about 12 ms). Later visits take 19 to 27 ms.
- The first very large selection pays a one-time setup of the x-ray outline on the graphics card.
- Hiding or showing many shapes changes the visibility of each block in turn; the drawing library
  rebuilds its lists for every change.
- The slider redraws the slice and the 3D view at every step.

The goal: everything a person does feels instant, every action has a limit a test enforces, and the
tests fail only when the app really became slower.

## 2. Limits (new or changed, all measured on the owner's local build)

| Action | Limit |
|---|---|
| Any route step, including the first step into the cord, every route and side (90th percentile) | 30 ms (unchanged, now covering every route) |
| First selection of the CNS, Brain or Spinal cord after start | 20 ms (the existing group limit, now also the first time) |
| Selecting the Tracts group after the first build | 40 ms (was 50) |
| Hiding, showing or isolating any group, including the whole brain | 30 ms (new) |
| One step of the slice slider, slice and 3D plane together | 16 ms (new; 60 steps a second) |
| First frame, own memory, every other limit | unchanged |

The first-use limits apply once the idle work of section 3 has finished, about a second after the
first frame; a person who acts sooner gets today's speed, never worse.

## 3. What changes

- Work that happens on first use and does not depend on the person's choice moves to idle time
  right after the first frame: loading every slice volume and template, the label centre tables, and
  the one-time outline setup. It runs in small pieces between events, so the app stays responsive
  and the first frame is not delayed. If a person needs something before it is ready, it is done
  then, as today. The app's own memory stays under its 400 MB limit with everything loaded.
- Showing and hiding many shapes is done as one batch, so the 3D view rebuilds once, not once per
  shape.
- Selecting the Tracts group and moving the slice slider are made cheaper: how is the builder's
  call (for example drawing fewer outlines or reusing the plane), checked against the limits above.
- Nothing changes in how things look or behave; only how long they take.

## 4. Trustworthy timing tests

- The route step test covers every route on both sides, not only the cerebellar route.
- New tests for the first large selection, hiding and showing, and the slider.
- Every timing test measures in a fresh process, repeats each action enough times, and judges the
  median (or the stated percentile), so a busy moment does not fail it. A real slowdown of a
  quarter or more still fails it.
- The slow suite runs five times in a row without a false failure before this project is handed
  over.

## 5. The build

- Local build peak memory (2.4 GB) and time (150 s) are recorded in the build report; the builder
  may lower them where it is cheap, but they get no limit (packaging, sub-project F, decides sizes).
- Package size is out of scope.

## 6. Out of scope

Cord slice zoom and pan, the timeline layout, the Activity panel, quiz fading, the status bar
(project 5); build checks, lint, README and booklet (project 6).

## 7. Testing

- Unit tests where the code allows it (the batch of visibility changes rebuilds once; idle loading
  finishes and leaves the same state as loading on demand).
- Real-build timing tests for every limit in section 2, in fresh processes, judged on medians.
- The first frame stays under 2 s with idle loading on (measured after the frame, not delayed by it).
- Five consecutive slow runs pass.

## 8. Calls made by the builder of this document (not the owner)

- The new limits: 30 ms for hiding and showing, 16 ms per slider step, 40 ms for the Tracts group,
  and the 20 ms group limit applying to the first selection too.
- Idle-time loading after the first frame rather than loading during start-up.
- No limit on build memory, build time or package size.
