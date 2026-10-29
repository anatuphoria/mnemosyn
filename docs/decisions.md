# Decisions

Every choice that shapes Mnemosyn, newest last, with the reason and the design document behind it.
Each one was approved by the project owner. A decision is never edited away: when it changes, a new
entry replaces it and the old one says so.

| No. | Date | Decision | Status |
|---|---|---|---|
| 1 | 2026-10-11 | Desktop app in Python with PySide6, VTK and PyVista | in force |
| 2 | 2026-10-11 | Own atlas package with a BrainGlobe-compatible core | in force |
| 3 | 2026-10-11 | Structure ids never change and are never reused | in force |
| 4 | 2026-10-11 | Every source pinned by checksum and licence | in force |
| 5 | 2026-10-11 | AAL3 as the first source, on its 1 mm grid | in force |
| 6 | 2026-10-11 | The built atlas is not kept in git | in force |
| 7 | 2026-10-11 | Descriptions are cited drafts until a doctor reviews them | in force |
| 8 | 2026-10-11 | A disclaimer in four places | in force |
| 9 | 2026-10-11 | Speed is enforced by tests | in force |
| 10 | 2026-10-11 | The label volume decides where a structure is | in force |
| 11 | 2026-10-11 | No surface smoothing | replaced by 33 |
| 12 | 2026-10-11 | Slices over the Colin27 MRI, beside the 3D view | in force |
| 13 | 2026-10-11 | App memory: 600 MB, later 400 MB of the app's own memory | in force |
| 14 | 2026-10-11 | Self-testing with three modes and spaced repetition | in force |
| 15 | 2026-10-11 | The project is named Mnemosyn | in force |
| 16 | 2026-10-11 | The terminal viewer stays a companion with no new features | replaced by 25 |
| 17 | 2026-10-11 | Tracts are hidden until asked for and have their own quiz level | changed by 29 |
| 18 | 2026-10-11 | MNI template variants are combined without registration | in force |
| 19 | 2026-10-12 | Pathways teach the route and lesions, one side at a time | in force |
| 20 | 2026-10-12 | Data without a licence is used in local builds only | changed by 59 |
| 21 | 2026-10-12 | Behaviour circuits as routes, with play and schematic hormone curves | changed by 48 |
| 22 | 2026-10-13 | Brainstem nuclei from three open sources, the Navigator local only | in force |
| 23 | 2026-10-13 | The spinal cord from PAM50, local only | in force |
| 24 | 2026-10-13 | The spinal cord waits on its branch until the whole audit is fixed | in force |
| 25 | 2026-10-18 | The terminal viewer moves to its own repository | in force |
| 26 | 2026-10-18 | Wheel zooms to the pointer, right drag pans, rotation turns around the brain | in force |
| 27 | 2026-10-18 | The camera never moves on its own; F frames the selection | in force |
| 28 | 2026-10-18 | The Tracts group lives inside Brain | in force |
| 29 | 2026-10-18 | Tracts shown by a selection hide again when the selection moves on | in force |
| 30 | 2026-10-18 | One x-ray outline highlights every selection | in force |
| 31 | 2026-10-18 | Selection time limits | in force |
| 32 | 2026-10-18 | A fixed-size About window with a list of sources | in force |
| 33 | 2026-10-18 | Smooth surfaces with a 2 mm blur | in force |
| 34 | 2026-10-18 | A brainstem body from Iglesias 2015, local only | in force |
| 35 | 2026-10-18 | The brainstem bodies are see-through | in force |
| 36 | 2026-10-18 | Entering a route takes under 100 ms | in force |
| 37 | 2026-10-18 | Questions and feedback go to GitHub Discussions | in force |
| 38 | 2026-10-18 | The website is built from the repository with MkDocs at mnemo.saeed.cool | in force |
| 39 | 2026-10-18 | One continuous banded cord, solid until you look inside | in force |
| 40 | 2026-10-18 | Spinal tracts tile the white matter | in force |
| 41 | 2026-10-18 | Colours that neighbours can tell apart | in force |
| 42 | 2026-10-18 | Tiny spinal tracts stay in the atlas and the quizzes | in force |
| 43 | 2026-10-18 | Speed limits for first use, groups, hiding and the slider | in force |
| 44 | 2026-10-19 | Timing tests also catch a quarter slowdown under the limits | in force |
| 45 | 2026-10-19 | Slice labels are sharp squares over a smooth MRI | in force |
| 46 | 2026-10-19 | Slices zoom with the wheel and pan with the right button | in force |
| 47 | 2026-10-19 | The Activity panel appears only for a route with a timeline | in force |
| 48 | 2026-10-19 | Route play controls are media symbols in the Pathways panel | in force |
| 49 | 2026-10-19 | Name it and Flashcards fade everything but the asked structure | in force |
| 50 | 2026-10-19 | The status bar shows the selection and the mouse hint only | in force |
| 51 | 2026-10-19 | Full names in the tree, the side only in the info panel, wrapped route lists | in force |
| 52 | 2026-10-19 | The atlas build never ignores a setting | in force |
| 53 | 2026-10-19 | Lint stays at zero, with settings that match the code | in force |
| 54 | 2026-10-19 | The review booklet PDF is published on the website | in force |
| 55 | 2026-10-19 | Access to the review form is by request and the owner's reply | in force |
| 56 | 2026-10-19 | Reviewers are credited on the website only with their consent | in force |
| 57 | 2026-10-19 | Downloads for Windows and Linux only | in force |
| 58 | 2026-10-19 | Test releases are not signed | in force |
| 59 | 2026-10-19 | Local-only data may be packaged for the owner's own machines, never shared | in force |
| 60 | 2026-10-19 | Releases come from version tags, as pre-releases below 1.0 | in force |
| 61 | 2026-10-19 | ΜΝΗΜΟΣΥΝΗ is the project's identity | in force |
| 62 | 2026-10-19 | The README is a clean front page; the website holds the details | in force |
| 63 | 2026-10-29 | The physiology layer is a Lab workspace driven by model files, starting with the stress axis | in force |
| 64 | 2026-10-29 | Lab results are computed from cited models in real units, and the Why chain comes only from declared links | in force |
| 65 | 2026-10-29 | Workspaces arrange the window; behaviour inside the existing ones does not change | in force |
| 66 | 2026-10-29 | Experiments are saved as plain text .mnemolab files that hold nothing personal | in force |

## 1. Desktop app in Python with PySide6, VTK and PyVista

2026-10-11. The app is a desktop program built on PySide6 (Qt), VTK through PyVista and pyqtgraph;
the atlas build tool and later simulations are Python too.
Why: a desktop app can draw thousands of structures at the display's refresh rate, and one language
covers the app, the build and the science libraries.
Design: [atlas foundation, section 1](specs/2026-10-11-atlas-foundation-design.md).

## 2. Own atlas package with a BrainGlobe-compatible core

2026-10-11. Mnemosyn writes its own package format. The core files keep BrainGlobe's field names and
meanings; everything else lives in extra fields and files.
Why: BrainGlobe tools can still read the core, while Mnemosyn gets what BrainGlobe lacks: one
citation per structure, mesh detail levels and several volumes. The BrainGlobe format as it is and
glTF were both rejected.
Design: [atlas foundation, section 3](specs/2026-10-11-atlas-foundation-design.md).

## 3. Structure ids never change and are never reused

2026-10-11. Every structure has a number below 65536 that never changes; a removed structure's number
is retired for good. `atlas_src/ids.lock` records every number ever published.
Why: quiz progress, routes and links refer to structures by number and must survive renames.
Design: [atlas foundation, section 4](specs/2026-10-11-atlas-foundation-design.md).

## 4. Every source pinned by checksum and licence

2026-10-11. Every downloaded file is checked against a fixed sha256, and every source records its
citation, version and licence. The build fails without them, and the same inputs always give the
same package.
Why: research-grade traceability: anyone can tell where each shape came from and whether it may be
shared.
Design: [atlas foundation, section 6](specs/2026-10-11-atlas-foundation-design.md).

## 5. AAL3 as the first source, on its 1 mm grid

2026-10-11. The brain regions come from AAL3 (GNU General Public License), and its 1 mm MNI grid is
the atlas's label grid.
Why: its licence was verified to allow sharing, and it covers the whole brain.
Design: [atlas foundation, section 13](specs/2026-10-11-atlas-foundation-design.md).

## 6. The built atlas is not kept in git

2026-10-11. `atlases/` is built locally with `python -m tools.build_atlas` and is not committed.
Why: the package is about 35 MB, over the 20 MB limit set for the repository.
Design: [atlas foundation, section 13](specs/2026-10-11-atlas-foundation-design.md).

## 7. Descriptions are cited drafts until a doctor reviews them

2026-10-11. Descriptions are drafted from open, cited sources; every claim carries a reference and the
app marks unreviewed entries as Draft. Drafts and judgment calls in the hierarchy (for example where
the pituitary or the cochlear nuclei sit) are not changed until the owner's review with a doctor.
Why: the atlas is made by a student for students, so accuracy has to come from sources and review.
Design: [atlas foundation, sections 1 and 5](specs/2026-10-11-atlas-foundation-design.md).

## 8. A disclaimer in four places

2026-10-11. On first launch, in the About window, under every description and in the README: the
atlas is a personal study project, not built or reviewed by a specialist, not for diagnosis or
treatment, and feedback is welcome.
Design: [atlas foundation, section 9](specs/2026-10-11-atlas-foundation-design.md).

## 9. Speed is enforced by tests

2026-10-11. Every time limit (opening, first frame, search, selection, slices, quizzes, routes) has a
test that fails when it is exceeded; the ones on the real atlas run with `pytest -m slow`.
Why: performance must be excellent, not merely acceptable, and stay that way.
Design: [atlas foundation, section 8](specs/2026-10-11-atlas-foundation-design.md).

## 10. The label volume decides where a structure is

2026-10-11. The labelled volume is the single record of where every structure lies; slices, clicks
and centring read it. Surfaces only decide the look, and may be built from a source's own finer grid.
Why: one place to check and correct, which future importers rely on.
Design: [viewer and slices, section 1](specs/2026-10-11-viewer-slices-design.md),
[tracts and hypothalamus, section 1](specs/2026-10-11-tracts-hypothalamus-design.md).

## 11. No surface smoothing

2026-10-11. Replaced by 33. A blur before surface extraction was tried and dropped because it changed
little on the AAL3 shapes of that time.
Design: [viewer and slices, section 1](specs/2026-10-11-viewer-slices-design.md).

## 12. Slices over the Colin27 MRI, beside the 3D view

2026-10-11. Slices show coloured labels over the grey Colin27 MRI, like an MRI viewer, in a panel
next to the 3D view; buttons switch the axis.
Why: atlas plates are how anatomy is studied, and Colin27 sits exactly on the AAL3 grid.
Design: [viewer and slices, section 4](specs/2026-10-11-viewer-slices-design.md).

## 13. App memory: 600 MB, later 400 MB of the app's own memory

2026-10-11. The app's memory limit became 600 MB instead of 500 MB, because Qt, VTK and PyVista alone
take about 316 MB and keeping full detail mattered more. The limit later became 400 MB of the app's
own memory, with shared libraries not counted, since how much of them is resident depends on the
system.
Design: [viewer and slices, section 8](specs/2026-10-11-viewer-slices-design.md).

## 14. Self-testing with three modes and spaced repetition

2026-10-11. Name it (typed or four choices), Find it and Flashcards, scheduled with FSRS. Left and
right count as one item; groups and single structures are separate levels. Flashcards use reviewed
descriptions only.
Design: [self-testing, section 1](specs/2026-10-11-self-testing-design.md).

## 15. The project is named Mnemosyn

2026-10-11. After Mnemosyne, the Greek goddess of memory. The progress file moved to
`~/.local/share/mnemosyn/`.
Design: [self-testing, section 12](specs/2026-10-11-self-testing-design.md).

## 16. The terminal viewer stays a companion with no new features

2026-10-11. Replaced by 25.
Design: [atlas foundation, section 1](specs/2026-10-11-atlas-foundation-design.md).

## 17. Tracts are hidden until asked for and have their own quiz level

2026-10-11. Changed by 29. White-matter tracts (HCP-1065) are hidden when the app opens; T shows them,
and selecting a tract shows it. Tracts are quizzed on their own level.
Why: tracts cover most of the brain and would hide the grey matter.
Design: [tracts and hypothalamus, section 1](specs/2026-10-11-tracts-hypothalamus-design.md).

## 18. MNI template variants are combined without registration

2026-10-11. AAL3, HCP-1065, Neudorfer and the later sources are all in MNI ICBM 152 variants and are
placed together as they are.
Why: the variants differ by a few millimetres at most.
Design: [tracts and hypothalamus, section 2](specs/2026-10-11-tracts-hypothalamus-design.md).

## 19. Pathways teach the route and lesions, one side at a time

2026-10-12. A route is followed station by station with what each station does and what a lesion
there causes. The whole route stays visible with the current station lit; a Left and Right switch
picks the side; crossings are steps of their own. Quiz questions on routes come later.
Design: [pathways, section 1](specs/2026-10-12-pathways-design.md).

## 20. Data without a licence is used in local builds only

2026-10-12. Changed by 59. A source whose files carry no licence is marked local only: `python -m
tools.build_atlas --local` includes it, the normal build leaves it out and stays shareable, and its
authors are asked for permission. A source moves to the normal build once they agree. An installer
must refuse a local package.
Why: some shapes exist nowhere else (pituitary, pineal, spinal cord, small brainstem nuclei), but
nothing is shared without permission.
Design: [endocrine glands, sections 1 and 4](specs/2026-10-12-endocrine-glands-design.md).

## 21. Behaviour circuits as routes, with play and schematic hormone curves

2026-10-12. Changed by 48. Ten behaviour circuits live in the Pathways panel under Behaviour, on
both sides at once, with Role, Disorders and Drugs texts. Play steps any route; the stress axis,
body clock and hunger show schematic hormone curves. A real simulation is a later project. The
playback controls sit in the Activity panel, where the change is shown.
Design: [behaviour circuits, section 1](specs/2026-10-12-behaviour-circuits-design.md),
[finishing pass, section 2](specs/2026-10-12-finishing-pass-design.md).

## 22. Brainstem nuclei from three open sources, the Navigator local only

2026-10-13. Edlow 2023, Diedrichsen 2009 and Sitek 2019 are shipped to everyone; the Brainstem
Navigator adds nuclei no open source draws, in local builds only. Existing shapes never change, and
each new structure comes from exactly one source.
Design: [brainstem nuclei, section 1](specs/2026-10-13-brainstem-nuclei-design.md).

## 23. The spinal cord from PAM50, local only

2026-10-13. The 30 spinal segments, six grey matter regions and 30 white matter tracts come from
PAM50, in local builds only until its authors allow sharing. Where tracts cover the white matter, a
second label layer keeps the segment underneath visible in slices. The start view still frames the
brain.
Design: [spinal cord, sections 1 and 4](specs/2026-10-13-spinal-cord-design.md).

## 24. The spinal cord waits on its branch until the whole audit is fixed

2026-10-13. The `spinal-cord` branch is merged only when all 37 items of the audit done on that day
are fixed, not only the ones first noticed. Reconfirmed on 2026-10-18, when a pull request was closed
unmerged.
Why: `main` should never carry known problems in how the atlas looks and behaves.

## 25. The terminal viewer moves to its own repository

2026-10-18. Replaces 16. The terminal viewer lives at github.com/anatuphoria/mnemosyn-tui with its own
copy of the atlas reader, and this repository is the desktop app and the atlas. When the package
format changes, the reader is copied there too.

## 26. Wheel zooms to the pointer, right drag pans, rotation turns around the brain

2026-10-18. The wheel zooms toward the point under the pointer, right drag slides the scene, left
drag rotates and R returns to the start view. Rotation always turns like a turntable around the
brain's own centre, never around a grabbed point or the screen centre.
Design: [navigation and selection, section 2](specs/2026-10-18-navigation-selection-design.md).

## 27. The camera never moves on its own; F frames the selection

2026-10-18. Selecting from anywhere never moves the camera. F frames the selection whole, keeping the
viewing direction; with nothing selected it frames the brain.
Why: the same action must always do the same thing.
Design: [navigation and selection, section 3](specs/2026-10-18-navigation-selection-design.md).

## 28. The Tracts group lives inside Brain

2026-10-18. Group 70 Tracts moved inside Brain, as the spinal tracts sit inside Spinal cord. Ids did
not change.
Design: [navigation and selection, section 4.1](specs/2026-10-18-navigation-selection-design.md).

## 29. Tracts shown by a selection hide again when the selection moves on

2026-10-18. Changes 17. Tracts turned on with T stay on until T again. Tracts shown because they were
selected hide as soon as the selection moves to something that does not contain them, so browsing
shows one tract at a time. Selecting Brain, Spinal cord or the whole CNS shows no tracts.
Design: [navigation and selection, section 4.2](specs/2026-10-18-navigation-selection-design.md).

## 30. One x-ray outline highlights every selection

2026-10-18. Every selection, one nucleus or a whole group, gets one bright outline around its outer
edge that shows through whatever is in front of it; the selected shapes keep their own colour.
Why: a structure buried inside the cortex or the cord must still visibly change when it is picked.
Design: [navigation and selection, section 4.3](specs/2026-10-18-navigation-selection-design.md).

## 31. Selection time limits

2026-10-18. Selecting one structure takes under 7 ms and under 16 ms with its redraw; a large group
(the CNS, Brain, Spinal cord) under 10 ms and under 20 ms with its redraw; a tract group under 50 ms
with its redraw. Measured on a local build.
Why: the first design asked for 7 ms including the redraw, which large groups could not meet; the
selection itself keeps 7 ms and the redraw gets its own limit.
Design: [navigation and selection, section 4.4](specs/2026-10-18-navigation-selection-design.md).

## 32. A fixed-size About window with a list of sources

2026-10-18. The About window fits a 1366 x 768 screen and never grows. One tab holds the app,
the atlas and the disclaimer; the other lists the data sources with what each gives the atlas, its
licence and a local only tag, and shows the full citation of the chosen one.
Design: [navigation and selection, section 5](specs/2026-10-18-navigation-selection-design.md).

## 33. Smooth surfaces with a 2 mm blur

2026-10-18. Replaces 11. Every structure's mask is blurred by 2 mm before its surface is extracted,
then lightly evened. Small structures are protected: their volume stays within 10% and their centre
within 1 mm, using less blur or a finer grid. Each structure is smoothed on its own.
Why: every shape looked like stacked 1 mm cubes; one voxel of blur still left ridges on the cortex.
Design: [smooth surfaces and the brainstem body, sections 2 and 6](specs/2026-10-18-surfaces-brainstem-design.md).

## 34. A brainstem body from Iglesias 2015, local only

2026-10-18. Midbrain, pons and medulla bodies come from the FreeSurfer brainstem atlas (Iglesias et al.
2015), in local builds only until its authors allow sharing. They are trimmed where they meet the
cerebellum and the spinal cord and never overwrite a nucleus in the slices.
Why: without them the brainstem was a cloud of floating nuclei with a gap above the cord.
Design: [smooth surfaces and the brainstem body, section 3](specs/2026-10-18-surfaces-brainstem-design.md).

## 35. The brainstem bodies are see-through

2026-10-18. The bodies are drawn like glass so the nuclei inside stay visible, and a click goes to
the nucleus behind the body when there is one.
Design: [smooth surfaces and the brainstem body, section 3.3](specs/2026-10-18-surfaces-brainstem-design.md).

## 36. Entering a route takes under 100 ms

2026-10-18. The limit for entering a route or switching its side was raised from 100 to 130 ms on
2026-10-13, when the spinal cord added faded geometry. It went back to 100 ms once routes opened in
75 to 85 ms.
Design: [spinal cord, section 7](specs/2026-10-13-spinal-cord-design.md).

## 37. Questions and feedback go to GitHub Discussions

2026-10-18. The repository's Discussions tab is open for questions, corrections and feedback, and
the website links to it.
Why: students and reviewers need one public place to ask and correct; the first design already
planned it for later.
Design: [atlas foundation, section 1](specs/2026-10-11-atlas-foundation-design.md).

## 38. The website is built from the repository with MkDocs at mnemo.saeed.cool

2026-10-18. The website uses MkDocs with the Material theme in the app's colours and lives at
mnemo.saeed.cool, published by GitHub Pages on every push to `main`. Its structure list, data
sources, decisions and design documents are generated from the repository, never copied by hand. An
earlier plain HTML test site was set aside. MkDocs stays below version 2, which drops Material's
themes; its successor can read the same pages later.
Why: one source for every fact, so the site cannot fall out of date with the atlas.

## 39. One continuous banded cord, solid until you look inside

2026-10-18. The spinal cord is one smooth surface from PAM50's cord mask, cut into one open piece per
segment, so no ring shows between segments; clicking it selects the segment at that height. It is
solid by default and turns see-through while spinal grey matter or a spinal tract is selected, shown
with T or asked for in a Find quiz. Grey matter and tracts stop where the segments stop.
Why: the 30 closed segment slabs looked like stacked bamboo, and a real cord has no visible joins.
Design: [the cord's look and colours, sections 2 to 4](specs/2026-10-18-cord-colours-design.md).

## 40. Spinal tracts tile the white matter

2026-10-18. A white matter voxel belongs to the tracts when the summed probability of the 30 PAM50
tract maps is at least 0.5, and then to its single most likely tract, with ties split by side so
left and right stay mirror images. Tracts never overlap.
Why: at probability 0.3 a quarter of tract voxels sat in two or three tracts, which drew one ridged
column and flickered with T on.
Design: [the cord's look and colours, section 5](specs/2026-10-18-cord-colours-design.md).

## 41. Colours that neighbours can tell apart

2026-10-18. Spinal segments use one hue per region with neighbours alternating light and dark;
ascending spinal tracts are blue and descending ones red or orange; in the brainstem, thalamus,
hypothalamus and deep cerebellar nuclei every member gets a clearly different colour, nearest
neighbours differing most. Left and right share a colour.
Why: shading one colour by 15% made neighbours look the same in 3D, in slices and in quizzes.
Design: [the cord's look and colours, section 6](specs/2026-10-18-cord-colours-design.md).

## 42. Tiny spinal tracts stay in the atlas and the quizzes

2026-10-18. The lateral reticulospinal tract (19 voxels a side) and the spinal part of the medial
longitudinal fasciculus (69 voxels a side) come out very small once the tracts tile, but they stay
in the atlas and in the tract quizzes like every other tract.
Why: they are real tracts students meet in textbooks; the build report lists them as small shapes.

## 43. Speed limits for first use, groups, hiding and the slider

2026-10-18. Every route step, the first step into the cord included, stays under 30 ms; the first
selection of the CNS, Brain or Spinal cord stays under 20 ms with its redraw, like later ones; the
Tracts group under 40 ms (was 50); hiding, showing or isolating any group under 30 ms; one step of
the slice slider under 16 ms. First-use work happens in idle steps right after the first frame.
Timing tests run in fresh processes and judge medians, so only a real slowdown fails them.
Why: the owner cannot measure the app; every action a person takes must feel instant and be
guarded by a test that does not cry wolf.
Design: [speed](specs/2026-10-18-speed-design.md).

## 44. Timing tests also catch a quarter slowdown under the limits

2026-10-19. Every timing test records what each action takes in a file kept out of git
(`.timing-baseline.json`, since the numbers belong to one computer and one build). Later runs fail
when an action is at least 25% and at least 1 ms slower than its record, even under its limit. The
record is written the first time and changes only when the owner runs the tests with
`--reset-timing-baseline`; a faster run never lowers it.
Why: an action can creep slower for many changes in a row and stay under its limit until the last
one; the 1 ms floor keeps actions that take under a few milliseconds from failing on noise.

## 45. Slice labels are sharp squares over a smooth MRI

2026-10-19, on the builder's advice. In the slices every label voxel is drawn as a sharp square at
any zoom, and outlines stay sharp; the grey MRI template under the labels is drawn smooth. This
holds for the brain and the cord, and the Labels slider changes only the labels.
Why: each label square is a real decision in the atlas data, and smoothing it would draw boundaries
nobody measured, which would mislead a researcher reading a structure's edge; research viewers
(FSLeyes, ITK-SNAP, 3D Slicer) show labels this way. The MRI is a measured brightness, and showing
it smooth, as those viewers do, makes the cord's shape easy to read for a student.
Design: [slices and looks, section 3](specs/2026-10-19-slices-looks-design.md).

## 46. Slices zoom with the wheel and pan with the right button

2026-10-19. The slices take the same moves as the 3D view: the wheel zooms around the pointer and a
right drag pans, while a left click still selects. The zoom stays while the slider moves and the
selection changes, and the slice fits the whole volume again when the volume (brain or cord) or
the view direction changes, or when F is pressed with the pointer over the slice. Nothing zooms on
its own. The closest zoom shows 20 voxels across.
Why: the cord was about a fifth of the slice panel wide in axial view and a sliver in the other
two; the owner wanted the moves people already know from the 3D view, not an automatic zoom.
Design: [slices and looks, section 2](specs/2026-10-19-slices-looks-design.md).

## 47. The Activity panel appears only for a route with a timeline

2026-10-18 and 2026-10-19. The Activity panel is hidden, and its menu entry disabled, unless a
route with a timeline is open (today the stress axis, the body clock and hunger); it then opens at
about a third of the window height. The placeholder wave shown for every structure is gone. The
timeline's note and references sit in a narrow column to the right of the chart, which takes the
panel's full height (layout B, chosen by the owner from mockups).
Why: a random placeholder wave took a fifth of the window for every structure, and the note under
the stress-axis chart squashed its curves almost flat.
Design: [slices and looks, section 4](specs/2026-10-19-slices-looks-design.md).

## 48. Route play controls are media symbols in the Pathways panel

2026-10-19. Back, play or pause, next and the speed picker sit in the Pathways panel just above the
step list, for every route. They are drawn as the system's standard media symbols (skip back, play,
pause, skip forward) with tooltips naming each and its key, and the speed picker shows "½×", "1×"
and "2×". Space plays and pauses during a route from anywhere in the window, except while typing in
a text field.
Why: every route uses these controls, not only the routes with a timeline, so they cannot live in
the Activity panel once it appears only for timelines (decision 47); media symbols are what people
already know from video and music players.
Changes 21, which put these controls in the Activity panel.
Design: [slices and looks, section 4a](specs/2026-10-19-slices-looks-design.md).

## 49. Name it and Flashcards fade everything but the asked structure

2026-10-18 (Name it, the owner) and 2026-10-19 (Flashcards, the builder's call the owner checked).
While a Name it question or a flashcard is shown, the asked structure stays solid and everything
else fades, in 3D and in the slice, the same way a route step fades all but its stations. Find it
never fades, because fading would point at the answer; the tract quiz keeps dimming the grey
matter as before. The fade ends with the quiz or on its summary screen.
Why: a small buried structure, such as a hypothalamic nucleus, showed in 3D only as a tiny ring on
the cortex, so only the slice made the question answerable.
Cost: starting a quiz takes about 45 ms instead of 22 and each next question about 13 ms instead of
7 (limits 100 and 50 ms), because the whole brain is redrawn see-through; the owner accepted this
on 2026-10-19.
Design: [slices and looks, section 5](specs/2026-10-19-slices-looks-design.md).

## 50. The status bar shows the selection and the mouse hint only

2026-10-18. The status bar names the selected structure and gives the correct mouse hint (drag
rotates, right-drag pans, the wheel zooms, F frames the selection, a click selects); during a quiz
or a route it says so and how to leave. The last frame time, the GPU name and the visible count are
gone from it; `--bench` still prints the frame times and the GPU.
Why: the old hint said right-drag zooms, which stopped being true when right-drag became pan, and
the developer read-outs mean nothing to a student.
Design: [slices and looks, section 6](specs/2026-10-19-slices-looks-design.md).

## 51. Full names in the tree, the side only in the info panel, wrapped route lists

2026-10-19, the builder's calls the owner accepted. The Structures panel opens 320 pixels wide,
taking the room from the slice and info panels rather than the 3D view, with tree levels indented
12 pixels, and every tree item shows its full name on hover. The info panel no longer names how a
shape is drawn ("cover", "shell", "nucleus"); it keeps only the side, left or right. The route list
and the step list wrap long names onto a second line instead of scrolling sideways.
Why: names such as "Hippocampus (left)" were cut off at the old width, the drawing kind means
nothing to a reader, and long route names hid behind a sideways scroll bar.
Design: [slices and looks, section 7](specs/2026-10-19-slices-looks-design.md).

## 52. The atlas build never ignores a setting

2026-10-19. A recipe setting the build would not apply is a build problem, never silently skipped:
multi-file sources reject drop, crop, mask and label_names; margin must be zero or more and needs
crop; numbers and member paths must have the right type; tracts on a volume left out of the build
are named. Bad data found while loading (an image with several frames, a missing channel, an
empty cord piece) stops the build with a message that names the source and what to do. All
problems found in one pass are listed together.
Why: several settings were accepted and then quietly did nothing, and some mistakes crashed with a
raw Python error (audit items 28 to 31).
Design: [build checks and finish, section 2](specs/2026-10-19-build-checks-finish-design.md).

## 53. Lint stays at zero, with settings that match the code

2026-10-19. Ruff reports nothing, and a fast test fails on any new finding. The settings follow the
code's existing style rather than the other way round: strings split over lines inside lists are
allowed, and import order is kept by hand because ruff cannot write the code's wrapped import
style. Ruff is pinned to the 0.17 series, since a newer one may check more rules. The review
folder, which is never committed, is left out. The code needs numpy 2 or later.
Why: 138 findings nobody read hid the few real ones (unused imports, an unused import that a test
relied on, needless casts).
Design: [build checks and finish, section 4](specs/2026-10-19-build-checks-finish-design.md).

## 54. The review booklet PDF is published on the website

2026-10-19. The latest edition of the specialist review booklet can be downloaded from the
website's Review page, and every edition is listed with its date and what changed. Only the PDF is
committed (under `site/files/`); the rest of the review material stays out of git. The booklet
and the Review page give the owner's Gmail as the contact.
Why: the project is open source and open to specialist review, and reviewers could not find the
booklet unless they were emailed it.
Design: [review pages, sections 3 and 4](specs/2026-10-19-review-pages-design.md).

## 55. Access to the review form is by request and the owner's reply

2026-10-19. A specialist asks for access with a short request form on the Review page (name,
email, speciality, institution if they wish, the date they want access from, consent to be
contacted). Each request reaches the owner by email and is kept in a private sheet; the owner
replies with the answer form link on or before that date. The answer form link is never published.
Why: an open answer form would attract spam and answers from people outside the field, and the
statistics need to know who answered.
Design: [review pages, section 2](specs/2026-10-19-review-pages-design.md).

## 56. Reviewers are credited on the website only with their consent

2026-10-19. The website's Reviewers page lists only reviewers who chose to be credited in the
review form, with their name as they asked and their institution if they chose. The owner keeps
the list by hand; the website never reads the private answer sheet.
Why: reviewers decide whether they are named, as the booklet promises.
Design: [review pages, section 3](specs/2026-10-19-review-pages-design.md).

## 57. Downloads for Windows and Linux only

2026-10-19. Mnemosyn is packaged for 64-bit Windows (an installer) and Linux (an AppImage). There
is no macOS version.
Why: Apple's paid signing is out of reach for now, and an unsigned app is awkward to open on
current macOS (System Settings, Privacy and Security, Open Anyway, and not at all on many school
Macs).
Design: [packaging, section 2](specs/2026-10-19-packaging-design.md).

## 58. Test releases are not signed

2026-10-19. While Mnemosyn is a test version, its packages are not code signed. Windows shows
SmartScreen on first launch ("More info", then "Run anyway"), and some antivirus programs may flag
the app; the Download page says how to open it. Signing, for example through the free SignPath
Foundation programme, can be switched on later without changing the rest of the build.
Why: this version is for testing, not production, and signing costs time or money that can wait.
Design: [packaging, section 2](specs/2026-10-19-packaging-design.md).

## 59. Local-only data may be packaged for the owner's own machines, never shared

2026-10-19. Changes 20. `python -m tools.package --local` makes a full package with the local-only
sources, named `local-not-for-sharing`, for the owner's own machines. It is made only on the
owner's computers, never on GitHub Actions, never uploaded, attached to a release or offered on
the website.
Why: the owner needs to test the full atlas on his other machines, and keeping the package in his
hands still honours the promise to the data authors that nothing is shared before they agree.
Design: [packaging, sections 2 and 7](specs/2026-10-19-packaging-design.md).

## 60. Releases come from version tags, as pre-releases below 1.0

2026-10-19. Pushing a tag `v<version>` that matches `pyproject.toml` makes GitHub Actions build,
smoke-test and publish the shareable Windows and Linux packages with a checksums file. Below
version 1.0 a release is marked pre-release and called a test version in the app and on the
Download page, whose buttons point at the version set in `site/download.toml` once its release
is published.
Why: one reproducible path from a tag to the files students download, with no hand-made uploads.
Design: [packaging, sections 5 and 6](specs/2026-10-19-packaging-design.md).

## 61. ΜΝΗΜΟΣΥΝΗ is the project's identity

2026-10-19, chosen by the owner from mockups. The wordmark is ΜΝΗΜΟΣΥΝΗ in GFS Didot, spaced like an
inscription, between two blue Greek key (meander) bands; the mark is the single character 𖡎
(Bamum letter MAEM, chosen for its shape) on the app's dark square, used as the app, installer,
AppImage and website icon; the meander is the divider between sections; the badges are our own, in
the same lettering between thin rules. Everything is drawn as outlines by `python -m tools.brand`
from the two fonts kept in `brand/fonts/` under the SIL Open Font Licence.
Why: the owner likes the Greek letters in this classical style and wants them to be the look of the
whole project, not only the website's home page.
Design: [identity](specs/2026-10-19-identity-design.md).

## 62. The README is a clean front page; the website holds the details

2026-10-19. The README keeps what a visitor needs (what Mnemosyn is, a screenshot, how to get or
build it, the data sources and their licences, the disclaimer and review, how to contribute) and
links to the website for everything detailed. The website keeps all its content in its own files
and no longer builds pages from README sections.
Why: since the website exists it is the full documentation, and the README had grown into a second
copy of it.
Design: [identity, sections 4 and 5](specs/2026-10-19-identity-design.md).

## 63. The physiology layer is a Lab workspace driven by model files, starting with the stress axis

2026-10-29, chosen by the owner. Subproject D becomes the Lab: a workspace of its own where anyone
changes a system freely (removing parts, drugs, diseases, stressors, clinical tests, or any model
value) and sees what follows over minutes to weeks. A system is a model file in `atlas_src/models/`
with its texts in `atlas_src/knowledge/en/lab-<key>.toml`; a general engine (`cns_lab`) runs any
model, so a new system is a new file. The first system is the stress axis.
Why: the owner wants a real simulation lab for people as well as for themselves, not effects added on
top of the current app, and a foundation that later systems reuse.
Design: [simulation Lab, sections 1 to 5](specs/2026-10-29-simulation-lab-design.md).

## 64. Lab results are computed from cited models in real units, and the Why chain comes only from declared links

2026-10-29. The stress axis follows Karin et al. (2020), with clearance rates from Andersen et al.
(2013) and the paper's own values for feedback and gland turnover. Every effect and term of the
equations is declared once with its explanation and source, and the Why chain is built only from
those, so it cannot disagree with the charts. Values that are not measured in people (CRH in portal
blood, the gland masses) or whose reference range depends on the assay (ACTH) are shown as multiples
of normal; cortisol is in µg/dL with nmol/L. Settling finds the exact repeating day with Newton's
method. Three assumptions of this project are added and named in the model's scope text: the MR
brake follows a Michaelis Menten curve (K_MR 0.15) so it stays finite without cortisol, the adrenal
answer to ACTH levels off (K_sat 4), and gland growth slows smoothly toward a ceiling (3 times
normal for corticotrophs, 2 for the adrenal cortex). Values fitted to cited data, each named in its
text: the daily rhythm (depth 1, a second twice daily term 0.3, phases 08:20 and 06:10) to Debono et
al. (2009), giving a cortisol peak of 15.5 µg/dL at 08:38 and a low of 1.6 µg/dL at 23:50;
dexamethasone strength 35 so the overnight 1 mg test is normal (Nieman et al. 2008);
hydrocortisone so 20 mg peaks near the measured level (Möllmann et al. 1991); the ACTH test given as
an ACTH level 40 times normal. Metyrapone and mifepristone are left out until their behaviour can be
tied to checked sources. Speed limits: one day under 30 ms, eight weeks under 450 ms, a first settle
under 400 ms.
Why: the owner asked that the Lab be real and honest: computed, sourced, and plain about what it
leaves out.
Design: [simulation Lab, section 5](specs/2026-10-29-simulation-lab-design.md).

## 65. Workspaces arrange the window; behaviour inside the existing ones does not change

2026-10-29, chosen by the owner from mockups. Explore, Slices, Pathways and Lab sit at the right end
of the menu bar and on Ctrl+1 to Ctrl+4. Each is an arrangement of the window's panels, remembered
between sessions (a stored arrangement from another layout version is dropped), with Reset layout in
the Window menu. Explore is the arrangement the app always had; Slices gives the slice panel most of
the width; Pathways raises the Pathways panel, and the Activity panel still follows decision 47. The
3D view stays the fixed centre. Switching is locked during a quiz, and switching to the Lab leaves an
open route first.
Why: a professional program arranges its panels by task, like Premiere's workspaces, while the
existing views keep working exactly as before.
Design: [simulation Lab, section 7](specs/2026-10-29-simulation-lab-design.md).

## 66. Experiments are saved as plain text .mnemolab files that hold nothing personal

2026-10-29, chosen by the owner. File, Save writes the experiment (the system and model version, the
run length and start time, the changes with their settings, the edited values, and an optional title
and note) as a readable TOML file with the extension `.mnemolab`. Nothing about the person, the
computer or the app is written. Opening a file from another model version says what differs; unknown
changes, options and values are left out and values out of range are brought into range, each named
in a message. The File menu keeps the eight most recent files, and closing, New or Open with unsaved
changes asks first.
Why: people will share experiments with friends and students, so a file must be safe to pass on and
readable without the app.
Design: [simulation Lab, section 9](specs/2026-10-29-simulation-lab-design.md).
