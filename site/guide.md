# Using the app

Drag rotates, right-drag pans, the wheel zooms, F frames the selection, a click selects. In the
slice the wheel zooms and right-drag pans too.

| Key | Action |
|---|---|
| `H` | Hide the selection (a group hides everything inside it) |
| `I` | Isolate the selection |
| `U` | Show all |
| `T` | Show or hide all tracts |
| `R` | Reset the view |
| `C` | Centre the slice on the selection |
| `F` | Frame the selection (with the pointer over the slice: fit the whole slice) |
| `F1` | About, data sources and licences |
| `Q` | Start a quiz (Study menu) |
| `Left` / `Right` | Previous or next step of a pathway, anywhere but a text field |
| `Esc` | Leave the pathway, or end a quiz |
| `Space` | Play or pause the current pathway |
| `Ctrl+F` | Filter the structure tree (names, abbreviations, synonyms, atlas labels) |

Tree checkboxes show and hide structures; unticking a group hides its whole subtree. The info
panel shows the description with numbered references, the geometry source and its licence.
Entries marked **Draft** have not been reviewed yet. The Activity panel appears only for the
routes with a hormone timeline.

The **Slices** panel shows axial, coronal or sagittal cross-sections: coloured labels over an
MRI template (Colin27 for the brain; in local builds, PAM50 for the spinal cord, chosen with the
Brain and Spinal cord buttons), in neurological convention (the patient's left on the screen's
left, with L/R, A/P and S/I letters on the edges). Labels are drawn as sharp squares, one per
voxel, over a smoothly drawn template. The wheel zooms around the pointer, right-drag pans and
`F` over the slice fits it again. The slider moves the plane, which also appears as a
translucent sheet in the 3D view; the second slider sets label opacity. Hovering shows the
structure under the cursor, clicking selects it, and `C` (Centre slice) moves the plane
through the selected structure.

The **Study** menu starts a quiz (`Q`) or shows your progress. *Name it* highlights a structure on
both sides, fades everything else and asks for its name: type it (synonyms, abbreviations, any word
order and small typos count) or pick one of four. *Find it* names a structure and you click it in 3D
or in a slice. *Flashcards* show reviewed descriptions only, fading the rest the same way. Choose
single structures or bigger groups, the whole atlas or one part of it, and either what is due now or
a practice round that leaves your schedule alone. Scheduling uses FSRS, the spaced repetition method
Anki uses, with at most 20 new items a day per mode. Progress is saved after every answer in
`~/.local/share/mnemosyn/progress.sqlite`. During a quiz the tree, the info panel and hover names
are hidden; `Esc` ends the quiz and restores the window.

**Tracts** (43 white-matter pathways: 41 from the HCP-1065 atlas, among them the
corticospinal tract, the lemnisci, the cerebellar peduncles and seven cranial nerves, and the
mammillothalamic tract and inferior thalamic peduncle from the hypothalamus atlas) are hidden
when the app opens. `T` shows or hides them all, the tree shows single tracts, and selecting a
tract shows it. In slices, visible tracts are outlined in their colour, and hovering or
clicking where tracts overlap picks the smallest. Quizzes have a Tracts level of their own;
while a tract is named, the grey matter around it is dimmed.

The **Pathways** panel, a tab next to Structures, follows routes station by station in two
groups. Sensory and motor: the visual and auditory pathways, the Papez circuit, voluntary
movement, touch and position, pain and temperature, and the basal ganglia and cerebellar motor
loops. Behaviour: the dopamine, serotonin, noradrenaline and acetylcholine systems, the fear
circuit, the stress axis, the body clock, hunger, memory, and decision and self-control.
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

