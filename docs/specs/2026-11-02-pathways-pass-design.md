# Pathways pass: the same frame as the Lab

Date: 2026-11-02
Status: approved by the owner in conversation on 2026-11-02 (mockup "Pathways on the same pattern as
the Lab")
Builds on: the design system (`cns_desktop/design/`), the Lab pass (decisions 81 and 82), behaviour
circuits and their timelines (`atlas_src/timelines/`)

## 1. Why

The owner finds that Pathways "feels not the same as the rest of the app": it neither behaves nor
looks like the Lab and Lesion. A side by side check on 2026-11-02 found why:

1. Everything sits in one narrow left panel (`cns_desktop/views/pathway_panel.py`): title, start,
   side switch, draft tag, play controls, step counter, steps, the step text, overview, references
   and a full width "Leave pathway" button. The step text, the most valuable part, ends in a small
   scroll box.
2. The right panel shows generic structure Info, which often says "No description yet" for the very
   step being walked, while the real explanation is in the left column.
3. Play controls live in the panel, not in the top bar as in the Lab.
4. The behaviour "Activity" chart (`cns_desktop/views/activity_chart.py`) looks unlike the Lab
   timeline, with a block of reference text beside the lanes.
5. The route list is a flat list without the groups, icons and search of the Lab and Lesion lists.
6. In 3D only the current step is outlined, the route never reads as a path, the camera does not
   frame it, and the slice plane cuts through it.
7. "Leave pathway" is a mode no other workspace has; the step text's disclaimer uses a hard coded red.

## 2. Goals, non goals, what would make it fail

Goals:

1. Pathways uses the frame the Lab and Lesion share: tabbed panels on the left and right, the 3D view
   in the middle with its controls in the top bar, time along the bottom.
2. The explanation of the current step has room to be read.
3. A route is visible from start to end in 3D and framed.
4. Every piece uses the design system's tokens, roles and widgets; nothing looks older than the Lab.

Non goals: new routes or texts; changes to route data or timelines; a circuit diagram for behaviour
routes (the Lab already has one, reached by "Open in the Lab"); the quiz; Explore and Slices.

It fails if any route, step, side, timeline or text shown today is lost; if keyboard walking (Space,
Left, Right) stops working; if the route list, steps or step text clip at the narrowest panel width
(`SIZE["panel_min"]`); if a step's text is shown for the wrong side; or if leaving a route does not
give back the hidden structures, selection, slice and camera the user had.

## 3. Layout

### 3.1 Left panel, tabs "Routes | Steps"

1. Routes: a list like the Lab's experiment list (`cns_desktop/lab/experiments_panel.py`): a search
   field ("Find a route"), collapsible groups from each route's `group`, in atlas order (today
   "Sensory and motor" and "Behaviour"), an icon per route from the bundled Lucide set (chosen by
   the builder; a group icon is fine where no fitting icon exists), one click opens the route.
2. Steps: the route name, "Start: ..." and the Draft chip, then the numbered steps. Each step shows a
   small number badge: passed steps in the accent colour, the current step highlighted, later steps
   dim. Crossings keep their ✕ mark and relays keep their muted colour. A "Close route" button beside
   the route name (inside the tab, not in the panel header, whose ✕ keeps hiding the panel) closes
   the route. Opening a route shows the Steps tab; closing it shows Routes. (Builder check, settled
   in design.)

### 3.2 Right panel, tabs "Step | Info | Slices"

1. Step: "STEP n OF m", the step name, then Role, Lesion or Disorders, Drugs, Overview and References
   exactly as today's details, written with the design system's rich text (`cns_desktop/design/rich`),
   and the disclaimer in the same style as the Info panel's disclaimer box, once. Without a route,
   Step explains in one line what a route is and how to start.
2. Info and Slices stay as they are today.
3. Opening a route shows the Step tab. Clicking a structure that is on the route moves to its step,
   as today; clicking one that is not keeps the step and updates Info, without switching tabs.

### 3.3 Top bar

In the Pathways group, before the existing Tracts and Quiz buttons: Back, Play or pause, Next, the
speed picker, the Left or Right switch (only for one sided routes), and "Open in the Lab" (only for
routes with a Lab system). They are disabled while no route is open. The panel keeps no play
controls of its own.

### 3.4 Bottom, behaviour timelines

For routes with a timeline, the activity chart is drawn in the Lab timeline's style: the same lane
height, name and unit column, playhead, axis and data palette (`cns_desktop/lab/timeline.py`,
`DATA_PALETTE`), clicking or dragging seeks. Its schematic note and references move out of the
chart into the Step tab under a "Timeline" heading.

### 3.5 3D view

While a route is open:

1. All of the route's structures are shown at once. Passed steps take the accent colour, the current
   step keeps today's selection emphasis and outline, later steps show in their own colour dimmed,
   and everything off the route fades further than today.
2. The slice plane is hidden.
3. On opening a route and on Reset view, the camera frames the route's structures (the same home
   framing the Lab uses, `BrainView.set_home`).
4. On closing the route, the camera, slice plane, hidden structures and selection come back as they
   were before it was opened.

## 4. Behaviour

1. A route stays open until another is picked or it is closed ("Close route" in the Steps tab, or
   Esc). There is no "Leave pathway" button. The status bar hint reads "Esc close".
2. Space, Left and Right walk the route as today. Playing moves step by step on routes without a
   timeline and follows the timeline on routes with one, as today.
3. Switching workspace keeps today's rule exactly: moving to the Lab or Lesion closes the route,
   moving to Explore or Slices keeps it open (`Workspaces.switch`). The route controls stay in the
   Pathways top bar group; Space, Left and Right keep working wherever the route is open.
4. Narrow windows (under `SIZE["narrow"]`): the left panel's tabs become "Routes | Steps | Info |
   Slices", and the Steps tab shows the step list with the current step's text below it, so "Steps"
   and "Step" never sit side by side and the tabs fit `SIZE["panel_min"]`. The owner's tiling window
   manager opens the app about 850 px wide, so this narrow layout is the one the owner sees most.
   (Builder check, settled in design.)

## 5. Checks

1. The existing Pathways and behaviour tests keep their meaning; tests that drive the old panel are
   moved to the new pieces.
2. New tests: route list search and groups; opening shows Steps and Step; step badges for passed,
   current and later; top bar controls enabled only with a route; closing restores camera, plane,
   hidden and selection; the timeline lanes use the Lab lane height and palette; nothing clips at 200
   px; no hard coded colours (`tests/test_design_no_stray_values.py`).
3. Screenshots of the visual pathway, the stress axis circuit and a lesion route at 1440 by 900 and
   at the narrow width, reviewed before merge.

## 6. Left to the builder

1. Whether the steps list is a list widget with a custom delegate or a column of small widgets.
2. Whether the activity chart is redrawn with the Lab timeline's painting code or restyled in
   place, as long as it looks the same.
3. The exact fade levels in 3D, within the design system's tokens.
4. The icons per route.

## 7. Decisions to log

1. Pathways uses the frame the Lab and Lesion share: Routes and Steps on the left, the step text on
   the right, route controls in the top bar, behaviour timelines in Lab style along the bottom.
2. A route stays open until another is picked or it is closed; there is no leave mode, and closing
   gives back what the user had before.
