# One Lab timeline

Date: 2026-11-01
Status: approved by the owner in conversation on 2026-11-01 (direction A of the mockups)
Builds on: the Simulation Lab (decision 63 onwards), the design system (decisions 67 to 71), the
timeline fixes of 2026-11-01 (`81cc1d1`)

## 1. Why

The Lab shows the same values twice. The Timeline tab is where changes are placed and moved, but
its lanes have no numbers. The Charts tab has scales and the value at the playhead, but no changes
and no editing, and its time axis starts at a different place, so the curves jump sideways when
switching tabs. The owner found the timeline clumsy to work in and asked for it to be "the best
for its purpose, whatever it costs": smart, advanced and well engineered.

## 2. Goals, non goals, what would make it fail

Goals:

1. One timeline holds everything the two tabs held: changes, curves, scales, live values.
2. You always know where you are in time and in the run, even zoomed in and scrolled down.
3. You can see where each curve reacts to each change without reading numbers.
4. Moving the playhead feels direct and smooth; nothing else on screen flickers while it moves.
5. Its display options are named preferences, so a future Settings window can offer them (the
   owner asked to keep a Settings window in mind; none exists yet).

Non goals: a Settings window; new Lab systems; changes to the model, the engine, the Why chain or
the `.mnemolab` format; the Activity charts of the Pathways workspace (they keep the small
multiples of decision 70); a light theme.

It fails if any lane, change or label is ever drawn over another region, if the curves move when
switching from one view to another, if the playhead is hard to grab, or if anything the Charts tab
could show is lost.

## 3. The timeline (direction A)

The Lab's bottom panel, "Lab time", holds only the Timeline. The Charts tab and `LabCharts` are
removed. "Show its chart" in the circuit and brain menus becomes "Show on the timeline": it reveals
the Timeline and briefly highlights that value's lane.

From top to bottom:

1. **Overview strip** (fixed). The whole run as a thin bar with a tick at the start of each change,
   the playhead as a short line, and a window showing the zoomed span. Drag inside the window to
   move it, drag its edges to zoom, press outside it to centre the window there, double click to
   show the whole run. When the whole run is shown the window fills the bar.
2. **Ruler** (fixed). Time labels that never leave the widget (as fixed on 2026-11-01). The playhead
   carries a badge with its time (`time_text`) on the ruler. Double click shows the whole run.
3. **Changes** (scrolls with the lanes). Overlapping changes stack in rows, as now. A faint dashed
   guide in the change colour drops from the start of every timed change through all lanes; it
   follows a change while it is dragged.
4. **Lanes** (scroll). Each lane's name column shows the name, the unit, the value at the playhead
   (`plain(value, 3)` in display units, toned `raised` or `lowered` against the normal run as the
   Charts tab did, plain when within 2 percent), and the lane's low and high marks beside the plot
   edge. The scale of a lane covers the whole run for every line shown (run, normal, snapshot), so
   zooming and panning never rescale it. The normal line and the dashed snapshot line stay.

The overview and ruler stay put while the changes and lanes scroll under them. The timeline
scrolls its own body with a scrollbar at the right that appears only when needed, so the panel
around it never scrolls. Rows and lanes keep the design system heights (44, decision 67): the
body scrolls instead of squashing them; lanes stretch to share extra height, as now.

## 4. Moving through time

1. The playhead can be grabbed anywhere along its line (as now) and in the ruler.
2. Hovering over the lanes shows a faint hover line with a small muted tag on each lane giving the
   value under the pointer, and the hover time on the ruler, so two moments can be compared without
   moving the playhead. It disappears when the pointer leaves or a drag starts.
3. With the timeline focused, Left and Right move the playhead by one screen pixel's worth of time,
   Shift with Left or Right by a tenth of the visible span, Home and End to the start and end.
4. The wheel over the plot zooms around the pointer; a sideways swipe or Shift with the wheel pans;
   the wheel over the name column scrolls the lanes up and down.

## 5. Smoothness

While the playhead moves, the timeline repaints at once. The Why panel refreshes at most every
100 ms and once more exactly when the playhead stops (a trailing refresh), keeps its scroll
position, and does not rebuild its text when the text is unchanged. The circuit, brain cards and
Inspector stay as they are (they cost well under a millisecond each, and the Inspector already
waits). The curves and lane backgrounds stay cached; only the playhead, hover line, values, guides
and changes are drawn per frame.

## 6. Preferences

Kept as attributes on the timeline with these names, defaults in brackets, ready for a Settings
window: `compare_on` (on, existing), `show_guides` (on), `show_hover` (on), `show_overview` (on).
The context menu offers the first two as now plus "Show change guides"; nothing is stored yet.

## 7. Left to the builder

Exact pixel sizes inside the 44 heights, the overview height (a design token), the tag and badge
styling within the design system tokens, how the lane highlight looks, and how to split the code
(one painted widget or a few) as long as all regions share one time mapping.

## 8. Tests

Every point of sections 3 to 5 gets a test, in the style of `tests/test_desktop_lab_timeline.py`:
regions never overlap at any zoom or scroll, values and tones match the run, the scale does not
change with zoom, the overview drags and zooms, keys move the playhead, the hover tags show and
hide, and the Why panel refreshes at most every 100 ms with a final refresh. Tests that used the
Charts tab move to the timeline. The timing budget for a playhead move stays within the existing
budgets (decision 13).

## 9. Decisions to log

1. The Lab has one timeline carrying the charts' scales and live values; the Charts tab is gone
   (the Activity charts keep decision 70).
