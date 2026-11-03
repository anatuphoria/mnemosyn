# Roadmap

Where Mnemosyn stands, what is unfinished, and what may come next. Unlike `decisions.md`, nothing
here is decided: an idea becomes a decision only when the owner approves its design. Last reviewed
2026-11-03, after version 0.5.0 and the handbook.

## Vision

Mnemosyn is for people who study neuroscience and want to understand it deeply, not only name its
parts. Paid anatomy apps teach what a structure is called and where it sits. Mnemosyn teaches why
the nervous system behaves as it does: why a lesion here causes that sign, why a hormone rises
after this and not that. It is built on published atlases, cites every claim, and computes its
results from models instead of drawing them.

It stays focused on the nervous system and the systems it controls. Going wide (the whole body)
would make it a weaker copy of the paid apps; going deep is where it can be the best.

## Where it stands

Version 0.5.0 (2026-11-02) is a free test release for Windows and Linux. It has the 3D atlas,
slices, pathways and behaviour circuits, lesion mode with the arterial territories, the Simulation
Lab with the stress axis and water balance on one Lab timeline (decision 75), and spaced repetition
quizzes. Over 0.4.0 it adds the Lab pass (decisions 81 and 82: floating cards over a larger brain
and a control for each kind of setting), the Pathways pass (decisions 83 and 84: Pathways on the
same frame as the rest of the app), and About and Progress windows rebuilt on the design system.
Version 0.3.1 was checked on Windows by the owner on 2026-10-30; 0.5.0 still waits for that check
(`docs/windows-check.md`). Since 2026-11-03 the website has a handbook in place of the single guide
page (see below). The first public forum post went out on 2026-10-30; there are no outside users or
feedback yet.

## Unfinished

The main features are built: lesion mode (decision 76) with the arterial territories, which 0.4.0
carries in the public download (decision 77), and water balance, the second Lab system
(decision 78). The stabilization pass is merged and released in 0.4.0, and the handbook is
live, so all later work is enhancements and fixes. Cord lesions work only in local builds until PAM50 allows
sharing, and medullary syndromes need cranial nerve nuclei the atlas does not have.


1. The cells view (neuron scale) is on hold on the `cells` branch. The approach needs a new design
   before any further work; the old plan is not to be continued as it is.
2. The specialist review: the review pages and booklet are live; the request form link waits for
   the owner's check, and the second edition email to the existing reviewers is not sent.
3. Permission to share PAM50, the Brainstem Navigator, the Iglesias bodies and the pituitary and
   pineal masks. Until the authors agree they stay in local builds only. The PAM50 email is open.

## Speed

The first frame takes about 1.8 s, under the 2 s limit of decision 13 but closer to it than
before: about 1.55 s in 0.2.0, and the design system added about 0.25 s spread over its stylesheet,
top bar and charts. The owner accepted this on 2026-11-01. The simplest way to win time back is to
build the Lab only when it is first opened; its code and charts take about 0.2 s at start.

## Planned later

These were left out of earlier designs on purpose and are expected to come back.

1. More Lab systems: blood pressure, sleep, hunger. Each needs a model file, not new engine or
   screen code. Linking systems (for example cortisol raising blood pressure) is a later design.
2. Quiz questions on the Lab and on routes.
3. Opening `.mnemolab` files from the file manager.
4. Translating the texts, which are already prepared for it.
5. A light theme, which the design system leaves room for.
6. Code signing of the Windows installer, for example through the SignPath Foundation programme.
7. macOS, automatic updates, and package managers (winget, Flathub).

## Handbook (done)

Live at mnemo.saeed.cool/handbook/ since 2026-11-03 (design: `docs/specs/2026-11-03-handbook-design.md`).
Agreed with the owner on 2026-11-01, to start once the main features are finished, so that all
later work is enhancements and fixes. First a stabilization pass (one polish pass per workspace and a full
Windows check; the deferred minors are done), then a handbook on the website in place of the single guide page:

1. Start here: install and a ten minute tour of each workspace.
2. One page per workspace (Explore, Slices, Pathways, Lab, Lesion): every panel, button and
   shortcut.
3. Experiments to try, about eight to start, each with a question, a prediction, a button that
   opens it in Mnemosyn (a ready `.mnemolab` file for the Lab), what you will see and why, with
   sources.
4. Why you can trust it: sources, models, decisions and the specialist review.

Screenshots are taken from the real app by a script, and each experiment's stated result has a test,
so a change to the model can never leave a page wrong without a failing test.

## Ideas

Ranked by how much they would add to the vision. None of them has a design yet.

1. Visible trust. A review status on each structure (checked by a named specialist, or not yet) and
   a way to report a mistake from inside the app.
2. Lessons. A teacher saves a set of views, a route, a Lab experiment and questions as one file and
   shares it with a class.
3. Reach. A macOS build first; a browser version much later, only once the content is clearly
   ahead.
4. A Settings window. The owner asked to keep one in mind. The Lab timeline already names its
   display options (`compare_on`, `show_guides`, `show_hover`, `show_overview`) so a window can
   offer them; nothing is stored yet.

Set aside: fitting the Lab model to one real person, accounts of any kind, and new features for the
terminal viewer.

## Measuring usefulness

Before building more, find out whether Mnemosyn is useful to the people it is for. Progress stays
on the user's computer and nothing is tracked, so this is done by watching and asking.

1. Unprompted signals: downloads per release, forum replies, stars, issues, error reports, and
   above all someone recommending it or a teacher using it in class.
2. Five to ten conversations with neuroscience students about their last study session: what they
   tried to understand, what they used, where they got stuck. Then watch one of them use Mnemosyn
   on a real topic from their course.
3. After a week of use, ask "How would you feel if you could no longer use Mnemosyn?" If about 40%
   answer "very disappointed", it meets a real need.
4. A small learning test: a few students answer reasoning questions (localize a lesion, predict
   what dexamethasone does to ACTH), spend 30 minutes with Mnemosyn, then answer a fresh set of the
   same kind; compare with students who spent the 30 minutes on a textbook chapter.

The next weeks are for listening: what people say decides which idea comes first.
