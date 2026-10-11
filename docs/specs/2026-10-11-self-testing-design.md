# Self-Testing Design (sub-project B, part 3: B3)

Date: 2026-10-11
Status: approved in discussion, awaiting review of this document
Builds on: `docs/specs/2026-10-11-atlas-foundation-design.md` (A) and
`docs/specs/2026-10-11-viewer-slices-design.md` (B1 + B2)

## 1. Context

B3 adds self-testing to the desktop app: quizzes and flashcards with spaced repetition. It is
for the owner's own study first and for any student using the free app.

Decisions made in discussion:

- Three modes: Name it (typed or multiple choice), Find it, Flashcards.
- Answer style for Name it is chosen at the start of each quiz: typing or 4 choices.
- Scheduling: spaced repetition with FSRS, through the `fsrs` library (MIT, version 6.3.2
  checked; only dependency `typing-extensions`).
- Quiz mode lives in the main window: the tree and info docks are replaced by a quiz panel and
  every place that shows a structure name on hover is silenced. 3D and slices stay.
- Left and right are asked as one item: both sides light up, the answer is the name without
  a side.
- Two levels chosen per quiz: Groups (lobes, thalamus, brainstem parts) and Structures (single
  gyri and nuclei). Each keeps its own schedule.
- Flashcards show only descriptions with `status = "reviewed"`; until one exists the mode is
  disabled. Descriptions and the hierarchy are under review by the owner with a doctor and
  are not changed by this work.

## 2. Quiz items (`cns_study/items.py`)

- `Item`: `id` (structure id), `level` (`"structures"` or `"groups"`), `name`, `answers`
  (name, acronym, synonyms), `geometry` (structure ids with meshes that light up), `parent`
  (nearest ancestor id, for choosing distractors).
- Structures level: every structure that is not a group, is not a sided child (`concept` is
  None) and has at least one mesh in its subtree. A concept with left and right children is
  one item; a midline structure is one item.
- Groups level: every structure of kind `group` whose subtree holds at least 2 structure-level
  items, except groups whose geometry is every mesh in the atlas (CNS, Brain), and except a
  group whose item set equals that of a descendant group (the deeper, more specific group is
  kept).
- `items(atlas, level, scope=None) -> list[Item]`: in atlas depth-first order, limited to the
  subtree of `scope` when given.
- `item_for(atlas, level, structure_id) -> Item | None`: the item whose geometry contains a
  clicked structure (used by Find it).

## 3. Answer checking (`cns_study/answers.py`)

- `normalize(text) -> str`: Unicode NFKD with accents removed, case folded, punctuation turned
  into spaces, spaces collapsed, a leading "the" dropped, the words "left", "right" and
  "bilateral" dropped.
- A typed answer matches an accepted answer when, after normalizing:
  1. it is equal, or
  2. it has the same set of words (word order free, for example "opercular part of inferior
     frontal gyrus"; the word "of" is ignored for this comparison), or
  3. it is within the typo allowance of an accepted answer: no typos for 4 characters or
     fewer (acronyms are exact), Damerau-Levenshtein distance 1 for 5 to 8 characters,
     2 for 9 or more.
- A typo match (rule 3) is rejected when the typed text is equal to, or strictly closer to,
  an accepted answer of any other item at either level.
- `check(typed, item, all_items) -> Verdict` with `correct: bool`, `exact: bool` (false when
  accepted through a typo) and `closest: str` (the accepted answer it matched).
- Budget: under 1 ms per check on the real atlas.

## 4. Multiple choice (`cns_study/choices.py`)

- `choices(item, pool, rng) -> list[Item]`: the item plus 3 distractors from the same level,
  preferring items with the same parent, then the same grandparent, then further up the
  tree; ties broken by `rng`. Distractors never share an accepted answer with the item.
  Order shuffled by `rng`. Fewer than 4 items in the level: as many as exist.

## 5. Scheduling and sessions

### 5.1 FSRS

- `fsrs.Scheduler` with library defaults (desired retention 0.9, learning steps 1 and 10
  minutes, relearning step 10 minutes, fuzzing on; tests turn fuzzing off).
- Ratings: wrong answer is Again. A correct answer is Good by default; after a correct
  answer the person may press H (Hard) or E (Easy) before moving on. Flashcards are rated by
  the person with keys 1 to 4 (Again, Hard, Good, Easy).
- Modes with separate schedules: `name-typed`, `name-choice`, `find`, `flashcard`.

### 5.2 Session (`cns_study/session.py`)

- `Session(items, mode, store, practice, now, rng)`; `now` is a callable returning an aware
  UTC datetime so tests use a fake clock.
- Due now: the queue holds cards due now, oldest due first, then new items (in item order)
  until 20 new items of this mode (both levels together) were first reviewed today (local
  calendar day, counted from the review log). A card that comes due again within 20 minutes (learning and
  relearning steps) goes back into the queue and is asked when due, or earlier when nothing
  else is left (learn-ahead limit 20 minutes, as in Anki).
- Practice: the chosen items shuffled; answers are judged and shown but nothing is written to
  the store.
- `next() -> Item | None`, `answer(rating, correct, answer_ms)`, `summary() -> Summary`
  (answered, correct, percent, up to 5 most missed, number due tomorrow).

## 6. Progress store (`cns_study/progress.py`)

- SQLite file `progress.sqlite` in `QStandardPaths.GenericDataLocation / "cns-atlas"`
  (`~/.local/share/cns-atlas/` on Linux); the path is a parameter so tests use a temporary
  file. WAL journal, `PRAGMA user_version = 1`.
- Tables:
  - `cards(atlas TEXT, item INTEGER, mode TEXT, card TEXT, due TEXT,
    PRIMARY KEY (atlas, item, mode))`: `card` is `fsrs.Card.to_json()`, `due` is ISO UTC.
  - `reviews(id INTEGER PRIMARY KEY, atlas TEXT, item INTEGER, mode TEXT, rating INTEGER,
    correct INTEGER, answer_ms INTEGER, reviewed_at TEXT)`.
- `atlas` is the package name from `metadata.json`. Structure ids are stable (A), so renames
  and new structures keep history. Rows for ids no longer in the atlas are kept and ignored.
- Each answer is written in its own transaction before the next question is shown.
- Opening fails (not a database, wrong schema, unreadable): the file is renamed to
  `progress.sqlite.broken-<YYYYMMDD-HHMMSS>`, a new one is created, and the app shows a
  message with the old file's path. Nothing is deleted.
- Queries for the progress window: per mode and level, counts of new, learning (FSRS states
  Learning and Relearning) and known (state Review); due today; due within 7 days; the 10
  seen items with the lowest current retrievability.

## 7. Desktop

### 7.1 Starting

- Menu Study with "Start quiz" (key Q) and "Progress".
- Setup dialog (`views/quiz_setup.py`): mode, answer style (Name it only), level, scope (whole
  atlas or a group chosen from a list of groups), session (Due now or Practice). The dialog
  shows how many items are due and new for the current choice. With nothing to ask it says
  so and offers Practice. Flashcards are disabled with the note "No reviewed descriptions
  yet" when no item in scope has a reviewed entry.

### 7.2 Quiz mode

- Entering saves: dock visibility and layout, hidden structures, selection, slice axis and
  position. It then shows all structures, hides the tree and info docks, shows the quiz dock
  (`views/quiz_panel.py`) and turns off structure names on hover and in the status bar.
- Leaving (Esc, the last question, or closing the panel) restores all of it exactly.
- Name it: the item is selected, so the existing 3D highlight and slice outline show it on
  both sides; the slice moves through its centre (as "Centre on selection"). Typed: a text
  box, Enter submits. Multiple choice: 4 buttons, keys 1 to 4.
- Find it: the panel shows "Find: <name>" with no selection. A click on a structure in 3D or
  in the slice answers; the clicked structure's item (via `item_for`) is compared with the
  target. A click on background or unlabelled tissue does nothing.
- Feedback: right or wrong; the correct name, acronym and synonyms; for a typo match "you
  typed <text>"; for Find it the clicked structure stays selected and the target is shown.
  Enter goes on; H or E change a correct answer's rating before going on.
- Flashcards: front shows the highlighted item and its name; Space shows the back (the
  reviewed description with its references); keys 1 to 4 rate.
- End: summary from `Session.summary()`, then quiz mode is left on Enter.

### 7.3 Progress window

- `views/progress_dialog.py`: a table of mode by level with new, learning, known, due today
  and due this week; below it the 10 weakest items with their retrievability.

### 7.4 Budgets

| Measure | Budget | How |
|---|---|---|
| Start quiz to first question shown, real atlas | under 100 ms | in-process, offscreen |
| Answer to next question shown, including the store write | under 50 ms median | in-process, offscreen |
| Answer check, real atlas | under 1 ms | pure function |

## 8. Dependencies

- `fsrs>=6.3,<7` added to the `desktop` optional dependencies.

## 9. Errors

- Damaged progress file: set aside and replaced, message shown (section 6).
- Nothing to ask: the setup dialog says so and offers Practice.
- No reviewed descriptions: Flashcards disabled with a note.
- History for structures no longer in the atlas: kept, ignored.

## 10. Testing

- `cns_study` without Qt:
  - answers: equal, synonyms, acronyms exact, word order, typo allowance by length, typo
    rejected when closer to another item, side words ignored;
  - items: both levels on the toy atlas, the group rules of section 2, `item_for`;
  - choices: same-parent preference, no shared answers, determinism with a seeded `rng`;
  - session with a fake clock: due before new, daily new limit, wrong answers return within
    the session, learn-ahead, Practice writes nothing, summary numbers;
  - store: survives reopening, damaged file set aside, schema version.
- Desktop on the toy atlas: entering quiz mode hides the tree, info and hover names and
  leaving restores docks, hidden structures, selection and slice; a typed and a multiple
  choice Name it round; Find it by clicking in 3D and in the slice; Flashcards disabled
  without reviewed entries and working with one; summary.
- Budgets of section 7.4, real-atlas ones marked slow.

## 11. Scope

In scope: sections 2 to 9.

Out of scope: tuning FSRS parameters to the person's history (needs the optimiser and
PyTorch; later, after a few hundred reviews), questions about functions and pathways (with B4
and more reviewed descriptions), syncing progress between computers, the terminal app.

## 12. Amendments made during planning (2026-10-11)

1. Answer checking is `AnswerIndex(pool)`, built once, with `check(typed, item) -> Verdict(correct,
   exact, matched)`; `matched` is the accepted answer a typo matched, otherwise the item's name.
2. `item_for(pool, structure_id)` takes the level's item list and returns the most specific
   (deepest) item containing the structure. Find it judges a click correct when the clicked
   structure is part of the target's geometry, so a click anywhere inside a group counts for it.
3. Find it feedback selects the target (3D highlight and slice outline) and names what was
   clicked in the text. In Find it the slice does not move to the target before the answer.
4. Slice centring uses a per-label centre table built in 16-slice chunks. Measured on the real
   atlas: scanning the volume costs 35 ms per call; the table costs 52 ms once and about 6 MB,
   then each centre is a lookup. It is built when the quiz setup opens, and "Centre on
   selection" uses it too.
5. The quiz dock cannot be closed; "End quiz (Esc)" or Esc leaves quiz mode. During a quiz the
   Hide, Isolate, Show all and Start quiz actions are disabled, so H and E rate answers and
   nothing can be hidden.
6. `QuizChoice` and `due_and_new` live in `cns_study/session.py`; `with_reviewed_entries` in
   `cns_study/items.py`; `mode_stats`, `weakest` and `day_start` in `cns_study/progress.py`.
7. SQLite runs with `synchronous = NORMAL` in WAL mode: an app crash loses nothing; a power cut
   may lose the last answer.
8. `MainWindow(atlas, progress_path=None)` opens the progress store on first use, so tests and
   plain browsing never create the file.
9. Practice does not repeat wrong answers within the round.
10. During a quiz the status bar shows "quiz in progress" instead of the selected structure's
    name.
11. The project is named Mnemosyn (2026-10-11). The progress file lives in
    `~/.local/share/mnemosyn/progress.sqlite`; a file in the old `cns-atlas` folder is moved
    there once, on the first normal start, never over an existing file.
