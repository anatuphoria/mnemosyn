# Roadmap

Where Mnemosyn stands, what is unfinished, and what may come next. Unlike `decisions.md`, nothing
here is decided: an idea becomes a decision only when the owner approves its design. Last reviewed
2026-10-31, after version 0.3.0.

## Vision

Mnemosyn is for people who study neuroscience and want to understand it deeply, not only name its
parts. Paid anatomy apps teach what a structure is called and where it sits. Mnemosyn teaches why
the nervous system behaves as it does: why a lesion here causes that sign, why a hormone rises
after this and not that. It is built on published atlases, cites every claim, and computes its
results from models instead of drawing them.

It stays focused on the nervous system and the systems it controls. Going wide (the whole body)
would make it a weaker copy of the paid apps; going deep is where it can be the best.

## Where it stands

Version 0.3.0 is a free test release for Windows and Linux. It has the 3D atlas, slices, pathways
and behaviour circuits, the Simulation Lab with the stress axis, and spaced repetition quizzes.
It runs on Windows (checked by the owner on 2026-10-30). The first public forum post went out on
2026-10-30; there are no outside users or feedback yet.

## Unfinished

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

1. More Lab systems: blood pressure, sleep, thirst, hunger. Each needs a model file, not new engine
   or screen code.
2. Quiz questions on the Lab and on routes.
3. Opening `.mnemolab` files from the file manager.
4. Translating the texts, which are already prepared for it.
5. A light theme, which the design system leaves room for.
6. Code signing of the Windows installer, for example through the SignPath Foundation programme.
7. macOS, automatic updates, and package managers (winget, Flathub).

## Ideas

Ranked by how much they would add to the vision. None of them has a design yet.

1. Lesion mode. Place a lesion (a cord hemisection, a small infarct in the medulla) and see which
   tracts and nuclei it hits and the deficits it causes, side by side. The reverse is a quiz: a
   case is described and the student places the lesion, then compares what that lesion would cause
   with the case. This teaches localization, the core skill of clinical neuroanatomy.
2. Blood supply. Arteries and their territories, which make lesion mode realistic since strokes
   follow them. An open arterial territory atlas in MNI space has to be found and its licence
   checked first.
3. Visible trust. A review status on each structure (checked by a named specialist, or not yet) and
   a way to report a mistake from inside the app.
4. Lessons. A teacher saves a set of views, a route, a Lab experiment and questions as one file and
   shares it with a class.
5. Reach. A macOS build first; a browser version much later, only once the content is clearly
   ahead.

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
