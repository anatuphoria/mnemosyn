# Contributing to Mnemosyn

Thank you for wanting to help. Please read this page first.

## Expect rough edges

So far Mnemosyn has been built by one person, Saeed. The people who have tested it are few, and
all of them received it from him directly; there has been no open group of volunteer testers yet.

So you may find problems, and you may find a lot of them: things that break, texts that are wrong
or unclear, and features that work on one computer but not on another. That is expected at this
stage. Telling us about them is the most useful thing you can do, and every report is read.

## Ways to help without writing code

1. **Report a problem.** In the app choose **Help, Report a problem**, or open an issue with the
   "Report a problem" template. Say what you did, what happened and what you expected. Add the
   version from **Help, About Mnemosyn** and your system (Windows, Mac or Linux). If something
   crashed, **Help, Open data folder** shows `errors.log` and `crashes.log`; attach them.
2. **Report a mistake in a text.** Every description in the app ends with **Report a mistake in
   this text**, which opens the "Report a mistake in a text" issue with the place filled in. Name a
   textbook or paper that supports the correction if you can.
3. **Review the atlas as a specialist.** If you work in neuroanatomy, neurology, neurosurgery,
   psychiatry or a related field, the [review page](https://mnemo.saeed.cool/review/) explains how
   to take part.
4. **Share an idea.** Use [Discussions](https://github.com/anatuphoria/mnemosyn/discussions) for
   ideas and questions, so issues stay for problems.
5. **Report a security problem privately.** Never in a public issue; see [SECURITY.md](SECURITY.md).

## Contributing code or content

1. **Talk first.** Open an issue or a discussion before a large change. Larger changes start as a
   short design that the owner approves; approved designs become numbered entries in
   [docs/decisions.md](docs/decisions.md), so read the ones near your change before you start.
2. **Set up.** Follow [Build from source](https://mnemo.saeed.cool/download/#build-from-source):
   ```bash
   python -m venv .venv
   .venv/bin/pip install -e ".[desktop,atlas-build,dev]"
   .venv/bin/python -m tools.build_atlas
   .venv/bin/mnemosyn
   ```
3. **Branch from `next`.** Work happens on `next`, and pull requests go to `next`. `main` holds
   what has been released; pushing to it also updates the website.
4. **Write the test first.** Every fix and feature comes with a test that fails before the change
   and passes after it. Run the fast suite with
   `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest`. It needs about 11 GB of memory, so run
   it on its own. The slow tests (`-m slow`) need the built atlas.
5. **Check the style** with `.venv/bin/ruff check`; the fast suite also fails on any finding.
6. **Keep the code free of comments.** Clear names and tests explain the code here; please do not
   add new comments.
7. **Write plainly.** Short sentences in plain words, in the app, the docs and commit messages.
   Do not use dashes as punctuation; use a comma, a colon, a full stop or brackets instead.
8. **Write commit messages as one plain sentence** that says what changed, for example
   "Let Alt+Left reach Back while a list has focus". No prefixes such as "fix:".
9. **Cite every anatomy or clinical claim.** Texts live in `atlas_src/knowledge/en/`, cite keys
   from `atlas_src/knowledge/references.toml` in square brackets, and stay marked as drafts until
   a specialist has reviewed them.
10. **Respect the data licences.** Only add atlas sources whose licence allows sharing. Sources
    that do not yet allow it stay out of the shareable build.
11. **License.** Mnemosyn is free software under the GNU General Public License 3.0, and your
    contribution is shared under the same licence.

## Not for diagnosis

Mnemosyn is a study project. It is not a medical device and must not be used for diagnosis or
treatment. Please keep it that way in anything you add.
