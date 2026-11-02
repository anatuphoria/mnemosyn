from datetime import UTC, datetime

import pytest
from fsrs import Card, Rating, Scheduler
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from atlas_package import tetra, tiny_structures, write_package
from cns_atlas import DISCLAIMER, Atlas, Source
from cns_desktop.design.brand import KeyMark
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import SIZE
from cns_desktop.design.widgets import SegmentedControl
from cns_desktop.views import about_dialog as about
from cns_desktop.views.about_dialog import AboutDialog, licence_tag
from cns_desktop.views.progress_dialog import MODE_LABELS, ProgressDialog
from cns_study.items import LEVELS, items
from cns_study.progress import MODES, ProgressStore
import itertools

LOCAL = Source("toylocal", "Local mask", "Doe J, Roe R", 2021, "2",
               "No licence stated; local use only until the authors allow sharing", False,
               doi="10.1/local", provides="Local part")
SHARED = Source("toyshared", "Shared atlas", "Test A", 2024, "1",
                "Creative Commons Attribution 4.0 International (CC BY 4.0)", True,
                url="https://example.org/shared", provides="Shared part")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def local_atlas(qapp, tmp_path):
    import json

    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()},
                         sources=[SHARED, LOCAL])
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["local_only"] = ["toylocal"]
    (root / "metadata.json").write_text(json.dumps(metadata))
    return Atlas.open(root)


@pytest.mark.parametrize(("licence", "tag"), [
    ("GNU General Public License (no version stated; GPL-3.0 text included)", "GPL"),
    ("Creative Commons Attribution 4.0 International (CC BY 4.0)", "CC BY 4.0"),
    ("CC0 1.0 Universal (public domain dedication)", "CC0"),
    ("Creative Commons Attribution (CC BY, version not stated)", "CC BY"),
    ("BSD 3-Clause License", "BSD 3 Clause"),
    ("Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)", "CC BY SA 4.0"),
    ("Permissive notice: copyright Louis Collins, McConnell Brain Imaging Centre", "Permissive"),
    ("Something nobody has seen", "Other"),
])
def test_licences_get_short_tags(licence, tag):
    source = Source("s", "S", "A B", 2020, "1", licence, True)
    assert licence_tag(source, local=False) == (tag, "text2")


def test_a_local_source_is_tagged_local_only_whatever_its_licence():
    assert licence_tag(SHARED, local=True) == ("Local only", "edited")


def test_the_about_tab_shows_the_mark_name_version_and_notes(local_atlas, monkeypatch):
    monkeypatch.setattr(about, "app_version", lambda: "0.4.0")
    dialog = AboutDialog(local_atlas)
    assert len(dialog.findChildren(KeyMark)) == 1
    assert dialog.name.text() == "Mnemosyn" and dialog.name.property("role") == "title"
    assert dialog.version.text() == "Version 0.4.0"
    assert dialog.test_tag is not None and dialog.test_tag.text() == "Test version"
    texts = [note.text() for note in dialog.notes]
    assert DISCLAIMER in texts[0]
    assert "Local build, not for sharing." in texts[1]
    assert "1 source that may not be shared yet" in texts[1]
    assert dialog.facts["Sources"] == "2"
    assert dialog.facts["Atlas package"].startswith(str(local_atlas.metadata["name"]))


def test_a_release_version_has_no_test_tag(local_atlas, monkeypatch):
    monkeypatch.setattr(about, "app_version", lambda: "1.2.0")
    assert AboutDialog(local_atlas).test_tag is None


def test_a_shareable_build_has_only_the_disclaimer_note(qapp, tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    dialog = AboutDialog(Atlas.open(root))
    assert len(dialog.notes) == 1


def test_local_ids_without_a_source_are_still_named(qapp, tmp_path):
    import json

    root = write_package(tmp_path / "ghost", tiny_structures())
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["local_only"] = ["ghost-source"]
    (root / "metadata.json").write_text(json.dumps(metadata))
    dialog = AboutDialog(Atlas.open(root))
    assert "ghost-source" in dialog.notes[1].text()


def test_data_sources_is_a_table_with_short_tags(local_atlas):
    dialog = AboutDialog(local_atlas)
    rows = [(r.provides.text(), r.authors.text(), r.tag.text()) for r in dialog.rows]
    assert rows == [("Shared part", "Test 2024", "CC BY 4.0"),
                    ("Local part", "Doe et al. 2021", "Local only")]
    assert dialog.rows[1].tag.property("tone") == "edited"
    assert dialog.summary.text() == "2 sources, 1 local only"


def test_clicking_a_source_opens_its_citation_in_place_and_again_closes_it(local_atlas, qapp):
    dialog = AboutDialog(local_atlas)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    qapp.processEvents()
    row = dialog.rows[1]
    assert not row.detail.isVisible()
    QTest.mouseClick(row, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert row.detail.isVisible() and row.property("open") == "true"
    text = row.detail.text()
    assert LOCAL.citation() in text and LOCAL.licence in text
    assert "https://doi.org/10.1/local" in text
    QTest.mouseClick(row, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert not row.detail.isVisible()
    dialog.close()


def test_a_source_opens_from_the_keyboard(local_atlas, qapp):
    dialog = AboutDialog(local_atlas)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    row = dialog.rows[0]
    row.setFocus()
    QTest.keyClick(row, Qt.Key.Key_Space)
    qapp.processEvents()
    assert row.detail.isVisible()
    dialog.close()


def test_source_rows_never_overlap_or_scroll_sideways_even_when_hovered(qapp):
    from cns_desktop.app import default_atlas

    path = default_atlas()
    if not (path / "metadata.json").exists():
        pytest.skip("no built atlas")
    dialog = AboutDialog(Atlas.open(path))
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    qapp.processEvents()
    assert dialog.scroll.horizontalScrollBar().maximum() == 0
    before = [r.geometry() for r in dialog.rows]
    target = dialog.rows[2]
    QApplication.sendEvent(target, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    qapp.processEvents()
    after = [r.geometry() for r in dialog.rows]
    assert before == after
    for upper, lower in itertools.pairwise(after):
        assert upper.bottom() < lower.top()
    row = dialog.rows[0]
    cells = (row.provides, row.authors, row.tag)
    for head, cell in zip(dialog.head_labels, cells, strict=True):
        assert head.mapTo(dialog, head.rect().topLeft()).x() == cell.mapTo(
            dialog, cell.rect().topLeft()).x()
    dialog.close()


def review(store, item, mode, rating, now):
    card, _log = Scheduler().review_card(Card(), rating, now)
    store.record(item, mode, card, rating, True, 1000, now)


@pytest.fixture
def progress(qapp, tmp_path):
    from atlas_fixtures import build_toy_atlas

    atlas = Atlas.open(build_toy_atlas(tmp_path / "toy"))
    store = ProgressStore(tmp_path / "progress.sqlite", "toy")
    pool = items(atlas, "structures")
    now = datetime.now(UTC)
    review(store, pool[0].id, "find", Rating.Good, now)
    review(store, pool[1].id, "find", Rating.Easy, now)
    review(store, pool[0].id, "name-typed", Rating.Easy, now)
    return atlas, store, pool


def test_progress_opens_on_the_mode_with_most_due_and_shows_totals(progress, qapp):
    atlas, store, pool = progress
    dialog = ProgressDialog(atlas, store)
    assert isinstance(dialog.modes, SegmentedControl)
    assert dialog.modes.keys() == list(MODES)
    assert dialog.modes.current() == "find"
    total = len(MODES) * sum(len(items(atlas, level)) for level in LEVELS)
    assert dialog.tiles["due_today"].text() == "1"
    assert dialog.tiles["known"].text() == "2"
    assert dialog.known_of.text() == f"of {total:,}"
    row = dialog.levels["structures"]
    assert (row.learning.text(), row.due.text()) == ("1", "1")
    assert row.bar.parts == (1, 1, len(pool))
    assert dialog.weak_heading.text() == "Weakest in Find it"
    assert {r.name.text() for r in dialog.weak_rows} == {pool[0].name, pool[1].name}


def test_switching_mode_redraws_the_levels_and_the_weakest(progress, qapp):
    atlas, store, pool = progress
    dialog = ProgressDialog(atlas, store)
    dialog.modes.set_current("name-typed")
    row = dialog.levels["structures"]
    assert (row.learning.text(), row.due.text()) == ("0", "0")
    assert row.bar.parts == (1, 0, len(pool))
    assert dialog.weak_heading.text() == f"Weakest in {MODE_LABELS['name-typed']}"
    assert [r.name.text() for r in dialog.weak_rows] == [pool[0].name]
    assert dialog.weak_rows[0].percent.text().endswith("%")
    dialog.modes.set_current("flashcard")
    assert dialog.weak_rows == [] and dialog.empty.isVisibleTo(dialog)


def test_progress_starts_on_the_first_mode_when_nothing_is_due(qapp, tmp_path):
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    dialog = ProgressDialog(Atlas.open(root), ProgressStore(tmp_path / "p.sqlite", "toy"))
    assert dialog.modes.current() == MODES[0]
    assert dialog.weak_rows == []


def test_progress_fits_its_mode_switch_and_text(progress, qapp):
    atlas, store, _pool = progress
    dialog = ProgressDialog(atlas, store)
    dialog.show()
    qapp.processEvents()
    assert (dialog.width(), dialog.height()) == (720, 560)
    assert dialog.modes.width() >= dialog.modes.sizeHint().width()
    for key in MODES:
        button = dialog.modes.button(key)
        assert button.width() >= button.sizeHint().width()
    assert dialog.minimumSizeHint().height() <= dialog.height()
    assert SIZE["dialog"][0] == dialog.width()
    dialog.close()
