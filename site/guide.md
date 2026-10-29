# Using the app

Drag rotates, right drag pans, the wheel zooms, F frames the selection, a click selects. In the
slice the wheel zooms and right drag pans too.

| Key | Action |
|---|---|
| `H` | Hide the selection (a group hides everything inside it) |
| `I` | Isolate the selection |
| `U` | Show all |
| `T` | Show or hide all tracts |
| `R` | Reset the view |
| `C` | Centre the slice on the selection |
| `F` | Frame the selection (with the pointer over the slice: fit the whole slice) |
| `F1` | About Mnemosyn: data sources and licences (Help menu) |
| `Q` | Start a quiz (Study menu) |
| `Left` / `Right` | Previous or next step of a pathway, anywhere but a text field |
| `Esc` | Leave the pathway, or end a quiz |
| `Space` | Play or pause the current pathway, or in the Lab the run |
| `Ctrl+F` | Find a structure in the tree (names, abbreviations, synonyms, atlas labels) |
| `Ctrl+1` to `Ctrl+4` | Switch workspace: Explore, Slices, Pathways, Lab |
| `V` | In the Lab, switch the centre between the brain and the circuit |
| `Home` | In the Lab, go back to the start of the run |
| `Delete` | In the Lab, remove the selected change |
| `Ctrl+Z` / `Ctrl+Shift+Z` | In the Lab, undo or redo a change |
| `Ctrl+N` / `Ctrl+O` | New or open a Lab experiment |
| `Ctrl+S` / `Ctrl+Shift+S` | Save, or save as, a Lab experiment |

Tree checkboxes show and hide structures; unticking a group hides its whole subtree. The info
panel shows the description with numbered references, the geometry source and its licence.
Entries marked **Draft** have not been reviewed yet. The Activity panel appears only for the
routes with a hormone timeline.

The **Slices** panel shows axial, coronal or sagittal cross sections: coloured labels over an
MRI template (Colin27 for the brain; in local builds, PAM50 for the spinal cord, chosen with the
Brain and Spinal cord switch), in neurological convention (the patient's left on the screen's
left, with L/R, A/P and S/I letters on the edges). Labels are drawn as sharp squares, one per
voxel, over a smoothly drawn template. The wheel zooms around the pointer, right drag pans and
`F` over the slice fits it again. The slider moves the plane, which also appears as a
translucent sheet in the 3D view; the second slider sets label opacity. Hovering shows the
structure under the cursor, clicking selects it, and `C` (Centre slice, or the crosshair
button under the slice) moves the plane through the selected structure.

The **Study** menu starts a quiz (`Q`) or shows your progress. *Name it* highlights a structure on
both sides, fades everything else and asks for its name: type it (synonyms, abbreviations, any word
order and small typos count) or pick one of four. *Find it* names a structure and you click it in 3D
or in a slice. *Flashcards* show reviewed descriptions only, fading the rest the same way. Choose
single structures or bigger groups, the whole atlas or one part of it, and either what is due now or
a practice round that leaves your schedule alone. Scheduling uses FSRS, the spaced repetition method
Anki uses, with at most 20 new items a day per mode. Progress is saved after every answer in
`~/.local/share/mnemosyn/progress.sqlite`. During a quiz the tree, the info panel and hover names
are hidden; `Esc` ends the quiz and restores the window.

**Tracts** (43 white matter pathways: 41 from the HCP-1065 atlas, among them the
corticospinal tract, the lemnisci, the cerebellar peduncles and seven cranial nerves, and the
mammillothalamic tract and inferior thalamic peduncle from the hypothalamus atlas) are hidden
when the app opens. `T` shows or hides them all, the tree shows single tracts, and selecting a
tract shows it. In slices, visible tracts are outlined in their colour, and hovering or
clicking where tracts overlap picks the smallest. Quizzes have a Tracts level of their own;
while a tract is named, the grey matter around it is dimmed.

The **Pathways** panel, in the Pathways workspace (`Ctrl+3`), follows routes station by station in
two groups. Sensory and motor: the visual and auditory pathways, the Papez circuit, voluntary
movement, touch and position, pain and temperature, and the basal ganglia and cerebellar motor
loops. Behaviour: the dopamine, serotonin, noradrenaline and acetylcholine systems, the fear
circuit, the stress axis, the body clock, hunger, memory, and decision and self control.
For a sensory or motor route, choose a pathway and a start side (Left or Right): everything
off the route fades and cannot be clicked, the route's tracts are shown, and the current
station is highlighted with its role and the effect of a lesion there, with references. Back
and Next in the Pathways panel (or the arrow keys) move along the route and the slice
follows; crossings and relays the atlas has no shape for are steps of their own. Leaving
(`Esc` or the Leave button) restores the view as it was. Behaviour routes light both sides and
show, for each step, its role, the disorders linked to it and the drugs that act there.

While a pathway is open, the Pathways panel holds the playback controls above the steps, drawn as
media symbols: back, play or pause, next, a speed choice (½×, 1×, 2×) and the current step. Play
(`Space`) steps through a route on its own. The stress axis, body clock and hunger routes also open
the Activity panel, which appears only for them: it plays a schematic hormone timeline in which a
cursor follows the steps, the time is shown above the chart, the note and references sit beside it,
and a click in the plot jumps to that moment. All pathway texts and timelines are drafts awaiting
review.

## Workspaces

The bar under the window title holds the menus (File, Edit, View, Study, Experiment, Window and
Help), the tools of the current workspace as icons, and at the right the switch between four
arrangements of the window: **Explore** (the 3D view with the structure tree on the left and Info
and Slices on the right), **Slices** (a large slice view beside the structure tree and Info),
**Pathways** (the Pathways panel, Info and Slices, and the Activity panel when a route has a
timeline) and the **Lab**. Every icon names its key when you hover it. The 3D view has its own small
bar with Frame selection, Reset view and Tracts.

Panels that share a place, such as Info and Slices, switch with the control in their header. Drag a
header to move or float a panel; the buttons beside it float or close it. Each workspace remembers
its own arrangement, the **Window** menu brings a closed panel back, and **Reset layout** restores
the default. In a narrow window the default arrangements put the right panel's pages into the left
panel and the menus fold into one menu button; an arrangement you made yourself is never changed.

## The Lab

The Lab runs a computed model of a body system, so you can change it and watch what follows over
minutes to weeks. The first system is the stress axis (hypothalamus, pituitary, adrenal cortex and
cortisol), after Karin and colleagues (2020), with every number and sentence citing its source.

Drag a change from **Experiments** onto the **Timeline**, or double click it to add it at the
playhead (the search field above the list finds one by name): remove the pituitary or the adrenal glands, cut the pituitary stalk, give dexamethasone or
hydrocortisone (once or every day), switch on Addison's disease, Cushing's disease or an adrenal
tumour, add a short or long stressor, or run a clinical test (the overnight 1 mg and 8 mg
dexamethasone tests, the ACTH stimulation test). Drag a change to move it, drag its right edge to
make it last longer, and select it to edit its dose, time or strength in the **Inspector**. Diseases
are present from the start of a run unless you set them to begin at a time.

The centre shows the brain, with the parts of the model coloured by how far they are from normal and
labelled with their current level, or (`V`) the model as a live circuit whose arrows thicken and
thin with each signal. Parts outside the brain, such as the adrenal cortex and the blood, sit as cards
beside the brain. The **Timeline** and **Charts** show each value over time with the untouched
normal run in grey behind it: the charts give every value a row of its own with its name, unit and
current level, and one time axis at the bottom; **Take snapshot** keeps a copy of the current run to compare against.
**Why** explains the difference from normal at the playhead as a numbered chain of causes, each
marked with what it does (drives, holds back, grows and so on) and with its sources, and with no changes it explains the normal day. **Model** opens every value of the
model for experts, each with its normal value, range and source; edited values are marked in gold.
**What this model includes** says what the model covers and leaves out.

**File** saves an experiment as a small `.mnemolab` text file that you can open again or send to
someone; it holds only the experiment. All Lab texts are drafts until reviewed, and the Lab is for
studying, not for diagnosis or treatment.

