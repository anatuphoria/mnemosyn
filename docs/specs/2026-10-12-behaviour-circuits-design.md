# Behaviour Circuits, Play and Hormone Timelines (sub-project D, part 1: D1)

Date: 2026-10-12
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-12-pathways-design.md` (B4: routes, pathway texts, the Pathways
panel) and `docs/specs/2026-10-12-endocrine-glands-design.md` (C4: pituitary and pineal,
local-only sources)

## 1. Context

Sub-project D teaches the brain basis of behaviour (psychology). D1 adds behaviour circuits as
routes in the Pathways panel, automatic playback of any route, and schematic hormone timelines
for the three circuits where time matters.

Decisions made in discussion:

- Behaviour comes in as circuits in the existing Pathways panel, under a Behaviour heading.
- Ten circuits: dopamine, serotonin, noradrenaline, acetylcholine, fear, stress axis, body clock,
  hunger, memory, decision and self-control.
- Behaviour circuits work on both sides at once; texts per step are Role, Disorders and
  optionally Drugs.
- Play and Pause step any route automatically; stress axis, body clock and hunger also show
  schematic hormone curves in the Activity chart with a moving time cursor that drives the steps.
- A real simulation with adjustable feedback is out of scope (a later sub-project).
- All texts and curves are drafts with references for the owner's doctor review.

## 2. Route format changes (`atlas_src/pathways.toml`)

- `group` (required): the heading the route is listed under, `"Sensory and motor"` or
  `"Behaviour"`. The panel shows groups in order of first appearance.
- `sides` (optional): `"one"` (default) or `"both"`. In a both-sides route every station lights
  its shapes on the left, right and midline, no step may set `side`, the Left / Right switch is
  hidden and step labels show no side word.
- `texts` (optional): `"lesion"` (default: each step has one `Role:` and one `Lesion:` line) or
  `"behaviour"` (each step has one `Role:` line, one `Disorders:` line and at most one
  `Drugs:` line).
- `{same}` and `{opposite}` are refused in the texts of both-sides routes.
- The eight existing routes gain `group = "Sensory and motor"` and keep their other settings.

Build errors (each naming route and step): missing or empty group; unknown `sides` or `texts`
value; a `side` on a step of a both-sides route; a description whose step lines do not match the
route's text style; a side word in a both-sides route; and all B4 errors.

## 3. Stations on local-only structures

- A normal build leaves out structures shaped only by local-only sources (C4). A station whose
  structures are all left out is written to `pathways.json` as a text-only step (a relay with
  the structure names joined by " and ", same side), so the route keeps its name and lights
  nothing. Left-out ids in a station that also names kept ids are dropped from it.
- The build's shape check (every station lights shapes on each start side) skips left-out ids;
  ids missing from the source tree remain an error.
- A local build lights these stations as usual.

## 4. Package and loader

- `pathways.json` records gain `group`, `sides` and `texts`. Records without them read as
  `"Sensory and motor"`, `"one"` and `"lesion"`. `format_version` stays 1.
- `Pathway(key, name, start, steps, group="Sensory and motor", sides="one", texts="lesion")`.
- `StepText(role, lesion, disorders="", drugs="")`.
- `Atlas.pathway_text(key, side)`: side words are filled only in one-sided routes; for
  both-sides routes `side` is ignored (any of `left`, `right` is accepted).
- `resolve` for a both-sides route returns the union of the left and right resolutions in
  structure order (`resolve_both`).

## 5. Play

- The pathway page gets a Play / Pause button; `Space` toggles it while the panel has focus.
- Without a timeline: Play goes to the next step every 3 s and stops at the last step; Play at
  the last step restarts from step 1.
- With a timeline: Play advances a time cursor so the whole timeline plays in its `play_seconds`
  (default 30); whenever the cursor passes a mark the route goes to that mark's step; Play at the
  end restarts from time 0.
- Back, Next, clicking a step, switching side, choosing another route and leaving pause play.
- The timer runs every 50 ms while playing and is stopped otherwise.

## 6. Hormone timelines

### 6.1 Source files: `atlas_src/timelines/<route key>.toml`

```toml
route = "stress"
duration = 120
unit = "min"
play_seconds = 30
status = "draft"
note = "Schematic shapes after an acute stressor at time 0 [dickerson2004]."

[[curves]]
name = "Cortisol"
color = [235, 200, 90]
points = [[0, 0.2], [10, 0.3], [30, 1.0], [60, 0.6], [120, 0.25]]

[[marks]]
time = 0
step = 1
```

- Levels are relative (0 to 1); times run from 0 to `duration`.
- Marks name steps 1-based, like the description sections.
- Build errors: unknown route; `duration` or `play_seconds` not positive; no curves; a curve without points, with times out of order or
  outside `[0, duration]`, or levels outside `[0, 1]`; marks out of time order, outside the
  duration or naming a step that does not exist; a citation of an unknown reference; a second
  timeline for the same route.

### 6.2 Package and loader

- The build writes `timelines.json` (`[{route, duration, unit, play_seconds, status, note,
  curves: [{name, color, points}], marks: [{time, step}]}]`); packages without the file have no
  timelines.
- `Timeline`, `Curve`, `Mark` in `cns_atlas`; `Atlas.timelines: dict[str, Timeline]` keyed by
  route; `Timeline.step_at(time) -> int` (0-based index of the last mark at or before `time`,
  or the first mark's step before it); `Timeline.time_of(step) -> float | None` (time of the
  first mark for that step).

### 6.3 Activity chart

- While a route with a timeline is open, the chart shows its curves with a legend, x axis in
  the timeline's unit, y axis "relative level", a vertical cursor line, and below the chart the
  note with numbered citations and "Schematic shapes, not measured data".
- Going to a step moves the cursor to that step's time when the step has a mark; clicking in
  the chart moves the cursor there and goes to the matching step.
- Leaving the route, or opening one without a timeline, restores today's chart.

### 6.4 The three timelines

- `stress`: 0 to 120 min after a short stressor; CRH, ACTH and cortisol; marks for the
  paraventricular nucleus, pituitary, adrenal cortex and hippocampal feedback.
- `body-clock`: 0 to 24 h from midnight; melatonin and cortisol; marks for night (pineal),
  morning (suprachiasmatic nucleus and cortisol) and day (arousal centres).
- `hunger`: 0 to 24 h with meals at 7, 13 and 19 h; ghrelin and insulin; marks before and after
  meals (arcuate nucleus, lateral hypothalamus, ventromedial nucleus).

## 7. The ten behaviour routes

All both-sides, `group = "Behaviour"`, `texts = "behaviour"`; (text) marks a text-only step,
(local) a station on a local-only structure.

| Key | Name | Start | Steps |
|---|---|---|---|
| `dopamine` | Dopamine: reward and movement | ventral tegmental area | 2000; (text) medial forebrain bundle; 1440; 1090, 1100, 1300, 1310; 1400, 1350; 2010; 1410, 1420 |
| `serotonin` | Serotonin: mood and impulse | raphe nuclei | 2200, 2210; 1350; 1400; 1300, 1310, 1090; 1410, 1420, 1440; 2590 |
| `noradrenaline` | Noradrenaline: arousal and attention | locus coeruleus | 2100; (text) dorsal noradrenergic bundle; 21; 13, 14; 1350, 1400; 2510; 41 |
| `acetylcholine` | Acetylcholine: attention and memory | basal forebrain | 2660; 12; (text) medial septal nucleus; 1350; (text) pedunculopontine and laterodorsal tegmental nuclei; 21 |
| `fear` | Fear circuit | sound of danger | 1900; 1400; 2540, 2510; (text) periaqueductal grey; 2100; 1350; 1300, 1090 |
| `stress` | Stress axis (HPA) | stressor | 2510; 2700 (local); (text) adrenal cortex; 1350; 1090, 1300; 1400 |
| `body-clock` | Body clock, sleep and waking | light on the retina | (text) retinohypothalamic tract; 2590; 2510; 2710 (local); 2540; 2600, 2100, 2200, 2210; 21, 12; (text) ventrolateral preoptic nucleus |
| `hunger` | Hunger and satiety | gut and fat signals | (text) ghrelin, leptin and insulin; 2570; 2510; 2540; 2550; (text) nucleus of the solitary tract; 2000, 1440; 1200, 1120, 1130, 1140, 1150 |
| `memory` | Memory | an experience | 1600, 1640, 1660; 1360; 1350; 3340, 2630; 1090; 1400; 2660; 1410, 1420, 41 |
| `decision` | Decision and self-control | a choice | 1010, 1020; 1120, 1130, 1140, 1150; 1090, 1100; 1310, 1320; 1030, 1040; 1870, 1880; 1410, 1440 |

- Texts: `knowledge/en/pathway-<key>.md` with Overview and Step sections in the behaviour style,
  citing existing and new references; all `status = "draft"`.
- New references are added to `knowledge/references.toml` only after their DOI resolves to the
  cited work. Candidates: Damasio et al. 1994 (Phineas Gage), Dickerson and Kemeny 2004 (cortisol
  response to acute stressors), Cummings et al. 2001 (preprandial ghrelin rise), Thannickal et
  al. 2000 (orexin neurons in narcolepsy), Weitzman et al. 1971 (24-hour cortisol pattern).
- The routes, step choices and timeline shapes go on the owner's doctor review list.

## 8. Budgets

| Measure | Budget |
|---|---|
| Enter a route or switch side | under 100 ms (unchanged) |
| Move one step | under 30 ms (unchanged) |
| One cursor tick while playing | under 5 ms |
| First frame and memory | unchanged |

## 9. Testing

- Toy atlas: a both-sides behaviour route including a station on the toy local-only gland, and
  a timeline for it.
- Build: the new route keys and their errors; text style checks; the gland station as text-only
  in a normal build and lit in a local build; every timeline error of 6.1.
- Loader: new keys and defaults for old records; `resolve_both`; `StepText` with disorders and
  drugs; timelines, `step_at`, `time_of`; packages without `timelines.json`.
- Desktop: group headings; hidden side switch and side-free labels; both-side lighting; Role,
  Disorders and Drugs shown; Play steps a route (with a short test interval); the cursor drives
  the steps; clicking the chart or a step moves the cursor; pause on Back, Next, step click,
  side switch, leave; leaving restores the chart.
- Real atlas (slow): all 18 routes load; in a local build every station lights shapes; in a
  normal build only the gland stations are text-only; the budgets of section 8.

## 10. Scope

In scope: sections 2 to 9, the ten route descriptions and three timelines as drafts.

Out of scope: a simulation with adjustable feedback, quiz questions on circuits, animated flow
along tracts, a disease overlay, new structures (periaqueductal grey, septum, habenula,
adrenal gland).
