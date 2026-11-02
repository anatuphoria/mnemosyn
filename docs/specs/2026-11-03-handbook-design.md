# Handbook design

2026-11-03. Agreed with the owner in conversation. Replaces the single guide page with a handbook
on the website.

## Intent

A student has just downloaded Mnemosyn and wants to understand it: what it is, what they can do
with it, and why each part is worth their time. The handbook answers that. It is not a button
manual. For every important thing it says three things:

1. **How** to use it: the steps, buttons and shortcuts, with a real screenshot.
2. **Why here**: what this lets the student do that the tools they already use cannot.
3. **What you will see**: concrete things to try and what happens when they do.

The reader is a neuroscience or medical student who knows some anatomy but has never seen the app.
The handbook explains the app completely and does not teach anatomy from zero.

## The honest picture behind "why here"

Research done on 2026-11-03 (sources at the end) found that students mostly use five kinds of tool.
The handbook compares Mnemosyn with these kinds and names no product, so nothing goes stale and
nobody is run down.

1. Printed atlases and textbooks: accurate but flat; working out 3D from them takes effort.
2. 3D anatomy apps: good for turning shapes around; the polished ones are paid and rarely link
   shapes to slices, pathways or function.
3. Flashcard apps: strong for memorising, but the cards are made by hand and show no anatomy in
   space.
4. Physiology simulators: usually reached through a course bundle and covering nerve, muscle,
   heart and blood, not hormone axes. Nothing comparable was found for water balance.
5. Lesion localisation tools: a few draw pathways from symptoms; none was found that places a
   stroke on arterial territories.

Mnemosyn's case: it joins 3D, slices, pathways, a physiology lab, lesions and spaced repetition on
the same anatomy, free and offline, with every shape and model citing its source. Its limits are
stated as plainly: shapes come from MRI atlases and are less detailed than artist made models; it
runs on desktop only; no specialist has reviewed it yet; it has no cranial nerves; the spinal cord
is not in the public download.

## Goals

1. A reader who finishes "Start here" can open every workspace and knows why they would.
2. Every workspace page answers How, Why here and What you will see.
3. About eight experiments, each a question, a prediction, a way to open it, and a revealed answer
   with why and sources.
4. A page that says plainly why the content can be trusted and where it cannot yet.
5. Pages that cannot quietly go wrong: screenshots come from the real app by a script, and every
   stated experiment result and every listed shortcut is checked by a test.

## Non goals

1. Opening an experiment straight from the web page into the app. That needs the app to open
   `.mnemolab` files from the file manager, which stays on the later list. The page offers the file
   to download and says how to open it.
2. Teaching anatomy or physiology beyond what a reader needs to follow an experiment.
3. Videos, translations, help links inside the app.

## Anti goals

1. Overselling. A claim the app cannot back, or a comparison that runs a product down, makes the
   whole handbook untrustworthy.
2. A button list. A page that says what each control does but not why the reader should care has
   failed even if it is complete.
3. Pages that drift from the app. A screenshot or result that no longer matches is worse than none.

## Structure

The website gains a **Handbook** tab in place of "Using the app". Pages live in `site/handbook/`.

1. **Start here** (`index.md`): what Mnemosyn is in two sentences, a link to Download, then a ten
   minute tour: one short paragraph and one screenshot per workspace, each ending with a link to
   its page. It closes with where to go next (an experiment, the quizzes).
2. **Why Mnemosyn** (`why.md`): the honest picture above, written for students, with its sources.
3. **Workspaces**, one page each: Explore, Slices, Pathways, Lab, Lesion, Quizzes. The Lab has one
   page for the Lab in general and one each for the stress axis and water balance. Every page
   follows the approved mockup: a one line summary, three small boxes (How, Why here, What you
   will see), a screenshot with a caption, then sections "How to use it", "Why use it here", "What
   you will see", and the shortcuts that belong to it.
4. **Experiments**, one page each, in this shape: the question; "predict before you open it"; how to
   open it (a downloadable `.mnemolab` file for Lab experiments, numbered steps for the others);
   what to look at; a folded "What you will see, and why" with sources.
5. **Sources and review** (`trust.md`): where shapes and models come from (linking the existing Data
   sources and Structures pages), how decisions are recorded (linking Decisions), the specialist
   review and its status, the disclaimer, and the limits listed above.

The old `/guide/` address stays as a short page pointing into the handbook, so links already posted
keep working. Its content moves into the workspace pages; nothing in it is lost.

## The first experiments

Each stated result must come out of the model or atlas as it is. If a test shows the model says
something else, the experiment is rewritten or dropped. The model is never changed to fit a page;
a model change needs its own decision.

1. **Central or nephrogenic?** Desmopressin after a night without water: urine rises by more than
   half in central diabetes insipidus, hardly at all in nephrogenic.
2. **A night without water.** The deprivation test in a healthy body and in central diabetes
   insipidus: the urine concentrates in one and stays dilute in the other.
3. **Two kinds of low sodium.** SIADH against primary polydipsia: what the urine does in each.
4. **The dexamethasone tests.** The overnight 1 mg and 8 mg tests in a healthy body, Cushing's
   disease and an adrenal tumour: which suppress cortisol and which do not.
5. **Addison's disease.** Cortisol falls while ACTH climbs, and why the loop does that.
6. **Stopping a steroid course.** A hydrocortisone course quiets the body's own axis; what happens
   to cortisol when the course stops.
7. **One artery, many structures** (Lesion). Block one arterial territory and see which structures
   it takes with it.
8. **Which side?** (Pathways) Follow the voluntary movement route and see where it crosses the
   midline, and what that means for the side of weakness after a lesion.

## Keeping it true

1. **Screenshots.** A script drives the real app, sets up each view and saves the image into
   `site/handbook/shots/`. The images are committed. It runs on the owner's desktop (or under a
   virtual display), not in the website build. It uses a shareable atlas, never the local build,
   so the pictures match what a downloader sees; it builds one into `build/` if needed.
2. **Experiment results.** Each Lab experiment's `.mnemolab` file sits beside its page. A test
   opens every file, runs the model and checks the result the page states. The Lesion and Pathways
   experiments get the same kind of test against the atlas.
3. **Shortcuts and names.** A test checks that every shortcut the app defines appears on a handbook
   page, and that every screenshot a page references exists.
4. **Writing.** Pages follow the project's writing rules: short sentences, no dashes as
   punctuation, tables only for real grids such as shortcut lists.

## Decided by the owner

1. Purpose and reader as described under Intent.
2. Every feature answers How, Why here and What you will see.
3. The page shape in the approved mockup (summary, three boxes, screenshot, sections, a Try it box
   with a folded answer).
4. The comparison is honest and grounded in research, and states Mnemosyn's limits.
5. From 2026-11-01: Start here, one page per workspace, about eight experiments, a trust page,
   screenshots by script, a test for every experiment result.

## Calls made in writing this (for the owner to check)

1. Compare with kinds of tool, never named products.
2. The experiment button downloads the file; opening from the file manager waits.
3. Quizzes get their own page, since they are a main way to use the app.
4. The Lab has a general page plus one page per system.
5. Screenshots are committed images made by a script on a desktop, from a shareable atlas.
6. The eight experiments listed above, subject to their tests.
7. `/guide/` stays as a pointer page.
8. The whole handbook goes live in one website update, after the owner has read it.

## Left to the builder

Page wording (drafts for the owner to read), file and script names, how the script sets up each
view, the order pages are written in, and the exact tests, within the rules above.

## Research sources

1. Tools and resources for neuroanatomy education, a systematic review:
   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5934868/
2. Virtual reality neuroanatomical training study: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10983822/
3. Harvard Library neuroanatomy guide: https://guides.library.harvard.edu/c.php?g=1231127&p=9009526
4. Complete Anatomy store (student pricing): https://store.3d4medical.com/
5. Sylvius 4 Online: https://campusstore.miamioh.edu/sylvius-4-online-interactive-atlas-visual/bk/9780878939695
6. Anki usage in first year medical students: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9045547/
7. Anki cohort study: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10403443/
8. PhysioEx 10.0: https://biblioteka.umb.edu.pl/ed/index.php/umb-has-purchased-access-to-physioex-10-0-an-application-for-learning-physiology/
9. SimulAdren: https://scicrunch.org/resolver/SCR_027314
10. Neuro Localizer: https://apps.apple.com/us/app/neuro-localizer/id590275694
