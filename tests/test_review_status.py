from urllib.parse import parse_qs, urlparse

import pytest

from atlas_package import tetra, tiny_structures, write_package
from cns_atlas import Atlas
from cns_atlas.knowledge import (KnowledgeError, Reviewer, load_reviewers, parse_entry, resolve,
                                 review_problems)
from cns_desktop.report import LINK_TEXT, mistake_url, status_html
from cns_desktop.state import AppState
from cns_desktop.views.about_dialog import AboutDialog
from cns_desktop.views.info_panel import InfoPanel

pytestmark = pytest.mark.usefixtures("themed")
BODY = "## Function\nTest text.\n"
REVIEWERS = ('[doc]\nname = "Dr A. Name"\nspeciality = "neurology"\n\n'
             '[quiet]\nspeciality = "neuroanatomy"\n')


def text(status="draft", extra=""):
    return f'+++\nid = 100\nstatus = "{status}"\n{extra}+++\n{BODY}'


REVIEWED = text("reviewed", 'reviewed_by = ["doc", "quiet"]\nreviewed_on = 2026-11-20\n')


def test_a_reviewed_text_names_who_checked_it_and_when(tmp_path):
    (tmp_path / "reviewers.toml").write_text(REVIEWERS)
    reviewers = load_reviewers(tmp_path / "reviewers.toml")
    entry = resolve(parse_entry(REVIEWED, "x"), {}, reviewers)
    assert entry.reviewed_on == "2026-11-20" and entry.reviewed_by == ("doc", "quiet")
    assert entry.review_line() == ("by Dr A. Name, neurology and a specialist in neuroanatomy "
                                   "on 20 November 2026")
    assert parse_entry(text(), "x").review_line() == "not yet reviewed"
    assert Reviewer("k").label() == "a specialist"


@pytest.mark.parametrize(("extra", "message"), [
    ('reviewed_on = "soon"\n', "must be a date"),
    ('reviewed_by = "doc"\n', "list of reviewer keys"),
])
def test_bad_review_fields_are_refused(extra, message):
    with pytest.raises(KnowledgeError, match=message):
        parse_entry(text("reviewed", extra), "x")


def test_unknown_reviewer_fields_are_refused(tmp_path):
    (tmp_path / "reviewers.toml").write_text('[doc]\nemail = "a@b.c"\n')
    with pytest.raises(KnowledgeError, match="unknown fields"):
        load_reviewers(tmp_path / "reviewers.toml")


def test_the_build_checks_that_reviews_are_complete_and_honest():
    known = {"doc": Reviewer("doc", "Dr A. Name"), "quiet": Reviewer("quiet")}
    assert review_problems(parse_entry(REVIEWED, "x"), known, "x") == []
    assert review_problems(parse_entry(text(), "x"), known, "x") == []
    bare = review_problems(parse_entry(text("reviewed"), "x"), known, "x")
    assert bare == ["x: a reviewed text needs 'reviewed_by' and 'reviewed_on'"]
    stranger = review_problems(parse_entry(REVIEWED, "x"), {}, "x")
    assert stranger == ["x: unknown reviewer [doc]", "x: unknown reviewer [quiet]"]
    early = parse_entry(text("draft", 'reviewed_by = ["doc"]\n'), "x")
    assert review_problems(early, known, "x") == ["x: a draft cannot name a reviewer or a "
                                                  "review date"]


def atlas_with(tmp_path, entry):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()},
                         entries={"en": {100: entry}})
    (root / "knowledge" / "reviewers.toml").write_text(REVIEWERS)
    return Atlas.open(root)


def test_the_info_panel_shows_the_review_and_a_way_to_report_a_mistake(qapp, tmp_path):
    atlas = atlas_with(tmp_path, REVIEWED)
    html = InfoPanel(AppState(atlas)).html_for(101)
    assert "Reviewed" in html and "by Dr A. Name, neurology" in html and "Draft" not in html
    assert LINK_TEXT in html and "issues/new" in html
    assert atlas.review_counts() == (1, 1)
    assert AboutDialog(atlas).facts["Texts reviewed"] == "1 of 1"


def test_a_draft_still_says_so_and_can_be_reported(qapp, tmp_path):
    atlas = atlas_with(tmp_path, text())
    html = InfoPanel(AppState(atlas)).html_for(101)
    assert "Draft" in html and "not yet reviewed" in html and LINK_TEXT in html
    assert AboutDialog(atlas).facts["Texts reviewed"] == "0 of 1"


def test_a_structure_without_a_text_has_nothing_to_report(qapp, tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    html = InfoPanel(AppState(Atlas.open(root))).html_for(101)
    assert "No description yet." in html and LINK_TEXT not in html


def test_the_mistake_report_arrives_filled_in(tmp_path, monkeypatch):
    from cns_desktop import report

    monkeypatch.setattr(report, "app_version", lambda: "9.9.9")
    atlas = atlas_with(tmp_path, text())
    url = urlparse(mistake_url("Alpha (structure 101)", atlas, "draft"))
    query = parse_qs(url.query)
    assert url.netloc == "github.com" and url.path.endswith("/issues/new")
    assert query["template"] == ["mistake.md"]
    assert query["title"] == ["Mistake: Alpha (structure 101)"]
    body = query["body"][0]
    assert "Alpha (structure 101)" in body and "Mnemosyn 9.9.9" in body
    assert "This text is a draft." in body
    assert "reviewed" in mistake_url("x", atlas, "reviewed")
    assert status_html("reviewed", "by <b>") .endswith("by &lt;b&gt;")
