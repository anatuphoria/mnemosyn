# Simulation Lab (subproject D, part 1: the stress axis)

Date: 2026-10-29
Status: approved by the owner on 2026-10-29
Builds on: the behaviour circuits (decision 21), the stress axis route and its schematic timeline
(`atlas_src/pathways.toml`, `atlas_src/timelines/stress.toml`)

## 1. Why

The original roadmap (atlas foundation design, section 2) lists subproject D, the physiology
layer: values on structures, one simulation from start to finish, and charts linked to it. Today
the closest thing is the behaviour circuits. The stress axis, body clock and hunger routes play
step by step over hand drawn curves (decision 21 calls a real simulation "a later project").
Nothing the user does changes those curves.

The owner wants a real simulation lab: a place where anyone can change the physiology freely and
see what logically follows, with a description and real information about what is happening and
why. In the owner's words, it must be "a real thing", not effects stacked on top of the current
app with small changes in its behaviour. It must feel like a professional program, in the way it
is arranged and the way you work in it, like Unity, Unreal or Adobe Premiere. It is for people as
well as for the owner: students, teachers and anyone curious will use it, so it is not shaped
around one person's way of studying.

The first system is the stress axis (the hypothalamic, pituitary and adrenal axis, HPA). It is the
classic feedback loop, well modelled in published work, already present as a behaviour circuit,
and it allows real clinical experiments (the dexamethasone test, Addison's disease, Cushing's
disease). It is the foundation: later systems use the same engine, screen and file format.

## 2. Goals, what it is not, what would make it fail

Goals:

1. A Lab workspace where the user changes the stress axis and sees the result as it unfolds, over
   minutes, hours, days or weeks as the physiology needs: live charts, the affected structures in the 3D atlas, a live circuit diagram,
   and a chain of cause and effect with its sources.
2. The behaviour comes from a quantitative model in real units, not from scripted results.
3. Every number, every link and every sentence of explanation traces to a cited source.
4. Two levels of freedom: a curated set of real experiments by default, and every model value open
   to experts.
5. A professional way of working: workspaces, docking panels, a timeline editor, an Inspector, undo
   and redo, shortcuts, right click menus.
6. Experiments can be saved to a file, opened again and shared.
7. Adding a second system later means writing a new model file, not new engine or screen code.

Not goals:

1. A new visual style. The owner likes the app's look as it is (the dark Fusion palette in
   `cns_desktop/app.py`, the ΜΝΗΜΟΣΥΝΗ identity). Premium means arrangement and interaction.
2. A tool shaped only around the owner. The Lab is built for everyone who uses Mnemosyn: texts
   explain things for someone meeting them for the first time, and nothing assumes the owner's
   habits or set up. There are no accounts and nothing is sent anywhere; app settings (window
   layouts, the recent files list) stay on the computer as they do today (my call).
3. Other systems in this part (blood pressure, sleep, thirst and so on). The design must leave room
   for them; it does not build them.
4. Changing the behaviour circuits in the Pathways panel. They stay as they are.

Failures (it fails even if it technically works):

1. Results that are typed in rather than computed, or explanations that can disagree with the
   charts.
2. An answer made up for something the model does not cover. The Lab says plainly what it does not
   model.
3. A cramped panel bolted onto the current window. The Lab is its own workspace.
4. Numbers without units, sources or normal ranges. A value that has never been measured in people
   (above all CRH in the pituitary's own blood supply) is shown as a multiple of normal, labelled as
   such, with a note saying why no measured unit exists (my call).
5. Anything that reads as medical advice. The project disclaimer (decision 8) applies here too.

## 3. What the owner decided

1. The Lab layout: controls on the left, one large centre view, the "why" chain on the right, live
   charts and the timeline along the bottom (layout A of the mockups).
2. The centre view switches between Brain (the real 3D atlas) and Circuit (a live diagram of the
   system), with one key or a switch at the top of the view. Controls, chain and charts stay where
   they are when it switches.
3. The stress axis is the first system.
4. Both levels of freedom: real experiments first, every value for experts.
5. The professional workspace as shown in the last mockup (workspaces, docking and floating
   panels, a timeline of draggable change blocks, an Inspector, undo and redo, shortcuts, a status
   bar that always says where you are).
6. Experiments can be saved as files.

The mockups are kept in `.superpowers/brainstorm/771641-1793238595/content/` (`lab-layout.html`,
`lab-combine.html`, `lab-pro.html`; not committed). `lab-pro.html` is the reference for the
arrangement.

## 4. The Lab screen

The Lab is a workspace in the main window (section 7). Its default arrangement:

1. **Menu bar and toolbar.** The toolbar carries play, pause, back to start, playback speed, undo,
   redo, "Compare with normal", "Snapshot", and the system picker (only the stress axis for now).
   The File menu has New experiment, Open, Save, Save as, and the recent files list. An Experiment
   menu repeats the experiment actions.
2. **Left: Experiments and Model**, tabbed in one dock.
   1. Experiments lists the curated changes in groups (Remove or cut, Drugs, Conditions, Tests,
      Stressors). Each item has a short description of what it is in real life. Items are dragged
      onto the timeline, or double clicked to add at the playhead.
   2. Model lists every model value (section 5.5) for experts.
3. **Centre: Viewport**, with the Brain and Circuit switch.
   1. Brain: the existing 3D atlas view. Structures in the model are coloured by how far they are
      from normal at the playhead (a raised and a lowered colour), with a short live label each
      ("PVN · CRH ↑ 2.4×"). A removed part is marked as removed. Other structures stay as they
      are. Clicking a structure selects it in the Inspector.
   2. Circuit: a diagram of the model. Each part is a box with its current level; each link is an
      arrow whose thickness follows its current strength; removed parts and cut links are drawn
      dashed. Parts outside the brain (adrenal cortex, blood) are boxes like any other.
4. **Right: Why and Inspector**, tabbed in one dock.
   1. Why: the chain of cause and effect at the playhead (section 5.4), numbered, in plain words,
      each step with its reference, and the time it refers to ("At 8 h 40 min, 2 h after
      dexamethasone 1 mg").
   2. Inspector: the properties of whatever is selected (a change block, a part, a link or a
      structure): its values with units, normal ranges and sources, editable where that makes
      sense (a dose, a time).
5. **Bottom: Timeline and Charts**, tabbed in one dock.
   1. Timeline: a time ruler, a playhead scrubbed with the mouse, a Changes lane holding the
      change blocks, and one lane per main value (CRH, ACTH, cortisol, adrenal size) with the
      untouched normal run drawn behind in grey. Blocks are moved, stretched (for changes that
      last, like an infusion or a stressor) and deleted. The run length is set by the user, from
      hours to several weeks, and adding an experiment whose effect takes weeks offers to extend
      it. The ruler zooms with the wheel from minutes to the whole run, as editors do, so a 20
      minute stressor and a month of adrenal shrinking are both readable in one run.
   2. Charts: the same values in larger charts with axes and units, for reading numbers.
6. **Status bar**: the system and baseline ("Stress axis · healthy adult"), how many changes and
   edited values are active, and a short hint for the current pointer target.

Every dock can be moved, tabbed with another, floated and closed. Window brings back any closed
panel. "Reset layout" restores the Lab's default arrangement. The Viewport itself stays the fixed
centre of the window, as the 3D view is today, so it never floats or closes; the docks arrange
around it (my call: moving a VTK render window into a floating dock is fragile and would change
how quizzes and routes save and restore the layout).

## 5. The simulation

### 5.1 One model file per system

A system is described by a model file in the atlas sources, for example `atlas_src/models/stress.toml`,
built into the atlas package like the pathways and timelines. A model file holds:

1. The **parts** (for example paraventricular nucleus, anterior pituitary, adrenal cortex, blood),
   each linked to an atlas structure id where one exists, with its position in the circuit
   diagram (placed by hand in the file).
2. The **values** the model tracks over time (for example CRH, ACTH, cortisol, glucocorticoid
   receptor), with units, normal ranges and sources.
3. The **parameters** (rates, half lives, strengths of feedback, the shape of the daily rhythm),
   each with its normal value, units, allowed range, a one line meaning and its source.
4. The **links** between parts (for example "ACTH drives cortisol production in the adrenal
   cortex", "cortisol holds back CRH release"), each with its direction (drives or holds back), a
   short explanation for the Why panel and its source. Every term of the equations belongs to a
   link, so the equations and the explanations come from the same place.
5. The **experiments** (section 5.3), each as a change to parts, links or parameters, with a real
   life description and its source.
6. The **checks** (section 5.6) the model must pass.
7. A version, so saved experiments can tell which model they were made with.

### 5.2 The engine

1. A general engine reads a model file and integrates its equations over time. It holds no
   knowledge of the stress axis; everything specific is in the file.
2. A run starts from the model's settled state for its baseline (a healthy adult, starting at a
   stated clock time), so nothing jumps at time zero. Because of the daily rhythm, "settled" means
   the repeating daily pattern, not a fixed point.
3. Changes take effect in one of two ways (my call):
   1. **From a time:** surgery, drugs, stressors and tests start at their block's time on a healthy
      run, so the user watches the axis move to a new balance.
   2. **Present from the start:** conditions (Addison's disease, Cushing's disease, an adrenal
      tumour) and expert values default to being there from time zero, and the run starts already
      settled in that changed state, so a test given on the timeline meets an established
      disease. A condition can be switched to "from a time" in the Inspector to watch it begin.

   The Why chain orders steps by when they took effect; for changes present from the start it
   orders them along the links from the change outward.
4. After every edit the whole run is computed again, together with the untouched normal run, so
   the timeline can be scrubbed freely and compared at once. Playing only moves the playhead.
5. Values are in real units (for example cortisol in µg/dL with nmol/L shown alongside), never
   scaled to a peak like today's schematic timeline.
6. The model is taken from published HPA models with their parameters and cited. The builder
   chooses the model (section 10). Its structure must cover the daily rhythm, the response to a
   stressor, cortisol feedback on the pituitary and the hypothalamus, the action of
   dexamethasone as a feedback agent that the cortisol measurement does not see, and the slow
   change in the adrenal cortex's size and capacity under too much or too little ACTH over days
   and weeks.
7. Fast and slow processes run in the same model, so one run can hold a stressor lasting minutes
   and adrenal shrinking over weeks. Playback speed adapts to the zoom of the timeline (for
   example minutes per second when zoomed in, days per second over a whole month).

### 5.3 Experiments for the stress axis

The curated set for this part. Each one is a change block on the timeline with values the
Inspector can edit (dose, strength, start, length):

1. Remove or cut: remove the pituitary (hypophysectomy), cut the pituitary stalk, remove both
   adrenal glands.
2. Drugs: dexamethasone (dose), hydrocortisone (dose, as a single dose or a daily course over
   weeks, and stopping it), metyrapone (dose), a glucocorticoid receptor blocker such as
   mifepristone (dose).
3. Conditions: primary adrenal failure (Addison's disease), an ACTH making pituitary tumour
   (Cushing's disease), a cortisol making adrenal tumour.
4. Stressors: a short stressor and a long lasting one, each with a strength.
5. Tests: the overnight 1 mg dexamethasone test, the high dose dexamethasone test, the ACTH
   stimulation test. A test reads its result off the run and states it with the clinical cut off
   and its source.

The builder may adjust this list where the chosen model cannot represent an item honestly. An item
that cannot be represented is left out, not faked.

### 5.4 The "why" chain

1. The chain explains the difference between the user's run and the normal run at the playhead.
2. It starts at the changes the user made, then follows the links whose contribution changed the
   most, in the order the changes took effect, and stops when the remaining effects are small.
3. Each step is a declared link from the model file: its explanation text, the direction and size
   of the change ("ACTH falls to 10% of normal"), and its reference. No sentence is written
   outside the model file.
4. With no changes, the Why panel explains the normal state at the playhead (for example the
   morning rise of cortisol).
5. The exact method for ranking the links is the builder's (section 10), but the same run must
   always give the same chain.

### 5.5 Expert values

1. The Model tab lists every parameter with its normal value, units, allowed range, meaning and
   source.
2. Editing a value applies from the start of the run (time zero) and recomputes at once. An edited
   value is marked in the list, in the Inspector and in the status bar count, so the user always
   knows they have left the textbook values. Each value has its own reset, and there is a reset
   for all.
3. Values outside the allowed range cannot be entered. The allowed range is set in the model file.

### 5.6 Checks the model must pass

The model file lists expected behaviours from the literature, each with its source, and the test
suite runs every one of them. At least:

1. A daily cortisol rhythm with its peak in the early morning and its low around midnight, within
   cited normal ranges.
2. After a short stressor, ACTH peaks before cortisol, and both return toward baseline within a few
   hours.
3. The overnight 1 mg dexamethasone test suppresses morning cortisol below the cited cut off in the
   normal model.
4. Removing the pituitary: ACTH and cortisol fall, CRH rises.
5. Removing the adrenal glands, or Addison's disease: cortisol falls, ACTH and CRH rise.
6. Metyrapone: cortisol falls and ACTH rises.
7. Cushing's disease: ACTH and cortisol are high and not suppressed by the low dose test, and the
   adrenal cortex grows over weeks.
8. Weeks after the pituitary is removed, or after weeks of high dose hydrocortisone, the adrenal
   cortex has shrunk, so the ACTH stimulation test gives a low response; given hours after
   removal it still responds.
9. After long hydrocortisone is stopped, cortisol stays low for days to weeks while the axis
   recovers.

The numbers above are behaviours to confirm against the chosen sources, not values decided here.

### 5.7 Honesty about limits

1. The model's scope is written in the model file and shown in the Lab (a short "What this model
   includes and leaves out" text, opened from the system picker).
2. An experiment the model cannot represent is not offered.
3. All Lab texts are drafts until reviewed, like every description (decision 7), and carry the
   project disclaimer.

## 6. The atlas and the circuit

1. Model parts linked to atlas structures: the paraventricular nucleus (2510, from Neudorfer 2020,
   shareable), the pituitary gland (2700, from Tang 2024, local only), and, where the chosen model
   includes feedback from them, the hippocampus (1350) and the amygdala (1400).
2. The adrenal cortex and the blood are not in the atlas (it covers the CNS and the glands in it).
   They appear in the Circuit view and in the Inspector, and in the Brain view as labelled parts in
   a strip along the edge of the view.
3. In a shareable build the pituitary has no shape (decision 20). The Lab must work the same with
   the pituitary shown only in the Circuit view and in the edge strip.
4. The existing stress axis route stays in Pathways. Its info texts gain an "Open in the Lab"
   action that switches to the Lab with the stress axis loaded (my call).

## 7. Workspaces across the app

1. Workspaces sit at the right end of the menu bar: Explore, Slices, Pathways, Lab. Each is a named
   arrangement of the window's docks, remembered between sessions, with "Reset layout" per
   workspace.
2. Explore is today's arrangement. Slices gives the slice panel most of the window. Pathways is
   today's arrangement with the Pathways panel raised; the Activity panel still follows decision 47
   (shown only while a route with a timeline is open). Lab is section 4.
3. Inside Explore, Slices and Pathways, everything behaves exactly as today: entering a route, the
   quizzes, selection and the camera rules (decisions 26 and 27) do not change.
4. The Lab's own docks (Experiments, Model, Why, Inspector, Timeline, Charts) belong to the Lab
   workspace only. The 3D view is shared; leaving the Lab returns it to the state it had before.
5. Entering a quiz or a route from another workspace keeps working as today. Switching workspace
   while a quiz runs is not possible, as the quiz already locks the window today (my call).

## 8. Working in the Lab

1. **Undo and redo** cover every change to the experiment: adding, moving, stretching, editing and
   deleting change blocks, and editing expert values. Not camera moves or panel moves.
2. **Shortcuts**: Space plays and pauses, Home goes to the start, Delete removes the selected block,
   Ctrl+Z and Ctrl+Shift+Z undo and redo, Ctrl+S saves, one key switches Brain and Circuit. The
   builder picks keys that do not clash with today's (H, I, U, T, R, F, C, F1, N, Esc) and lists
   them in the README key table.
3. **Right click menus** on blocks (edit, duplicate, delete), on parts (show in the atlas, show its
   chart) and on lanes (hide, show the normal line).
4. **Compare with normal** shows the grey normal run behind every lane and chart; it is on by
   default. **Snapshot** keeps a copy of the current run as a second grey line, so two versions of
   an experiment can be compared.
5. Selection is shared: selecting a part in the Circuit selects its structure in the Brain view and
   shows it in the Inspector, and the other way round.

## 9. Experiment files

1. File, Save writes an experiment file with the extension `.mnemolab` (my call), a plain text
   TOML file so people can read and share it.
2. It holds: the system and model version, the run length and start clock time, the change blocks
   with their values, the edited expert values, and an optional title and note written by the user.
   Nothing about the person, the computer or the app's state.
3. Opening a file made with another model version opens it with a clear message about what
   differs; anything that no longer exists in the model is listed and dropped, never guessed.
4. The window title shows the file name and an unsaved mark. Closing with unsaved changes asks
   first.
5. Opening a `.mnemolab` file from the desktop or the installer's file association is left for
   later (section 11).

## 10. Left to the builder

1. Which published HPA model or models to base the equations on, as long as section 5.2 point 6
   and the checks in section 5.6 hold, every parameter is cited, and the papers' licences allow
   using their equations and values (equations themselves are facts; text and figures are not
   copied).
2. The numerical method and whether `scipy` joins the app's runtime dependencies (it is a build
   dependency today), weighed against the package size.
3. The method for ranking links in the Why chain, within section 5.4.
4. The colours for raised and lowered values, taken from the app's existing palette.
5. The model file's exact format and the experiment file's exact keys.
6. How the Circuit view is drawn (Qt graphics view or the existing chart library).
7. Speed limits for the Lab, added to the timing tests like every other view (decision 9): at least
   entering the Lab, recomputing after an edit, scrubbing the playhead, and switching Brain and
   Circuit.

## 11. Out of scope

1. Other systems (blood pressure, sleep, thirst, hunger and so on).
2. Quiz questions about the Lab.
3. Opening experiment files from outside the app (file associations).
4. Translating the Lab texts (they are ready for translation like every other text).
5. Changing the look of the app.
6. Changing the behaviour circuits in the Pathways panel, other than the "Open in the Lab" action.
7. Fitting the model to one real person (patient specific fitting), and accounts of any kind.

## 12. Decisions to log

1. The physiology layer is a Lab workspace driven by model files, starting with the stress axis.
2. Lab results are computed from cited models in real units, and the Why chain comes only from
   declared links.
3. Workspaces (Explore, Slices, Pathways, Lab) arrange the window; behaviour inside the existing
   ones does not change.
4. Experiments are saved as plain text `.mnemolab` files that hold nothing personal.
