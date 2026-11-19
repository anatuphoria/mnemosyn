import pytest
from PySide6.QtCore import QUrl

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("themed")


@pytest.fixture(scope="module")
def atlas(toy_atlas):
    return Atlas.open(toy_atlas)


@pytest.fixture
def window(qapp, atlas, tmp_path):
    w = MainWindow(atlas, progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def follow(browser, url):
    browser.anchorClicked.emit(QUrl(url))


def test_a_name_in_the_info_text_is_a_link(window):
    window.state.select(101)
    assert "structure:110" in window.info.toHtml()


def test_following_a_link_selects_the_part(window):
    window.state.select(101)
    follow(window.info, "structure:110")
    assert window.state.selected == 110


def test_back_returns_along_the_chain_of_links(window):
    window.state.select(101)
    follow(window.info, "structure:110")
    assert window.info.trail == [101]
    assert "← Back to Alpha gyrus (left)" in window.info.toPlainText()
    window.info.go_back()
    assert window.state.selected == 101 and window.info.trail == []


def test_a_selection_from_the_tree_clears_back(window):
    window.state.select(101)
    follow(window.info, "structure:110")
    window.state.select(120)
    assert window.info.trail == []
    assert "Back to" not in window.info.toPlainText()


def test_a_link_shows_a_hidden_part(window):
    parts = window.state.geometry_in(110)
    window.state.set_hidden(parts, True)
    window.follow_link(110)
    assert window.state.selected == 110
    assert not any(window.state.is_hidden(i) for i in parts)


def test_web_links_still_open_outside(window, monkeypatch):
    opened = []
    monkeypatch.setattr("cns_desktop.design.linked.QDesktopServices.openUrl", opened.append)
    follow(window.info, "https://example.org")
    assert [url.toString() for url in opened] == ["https://example.org"]


@pytest.fixture
def routes(qapp, toy_pathway_atlas, tmp_path):
    w = MainWindow(Atlas.open(toy_pathway_atlas), progress_path=tmp_path / "progress.sqlite")
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    qapp.processEvents()
    w.close()


def test_a_step_text_links_the_parts_it_names(routes, qapp):
    routes.workspaces.switch("Pathways")
    routes.pathways.open("loop", "left")
    routes.pathways.go(2)
    qapp.processEvents()
    html = routes.step_panel.details.toHtml()
    assert "structure:150" in html
    follow(routes.step_panel.details, "structure:150")
    assert routes.state.selected == 150


def test_a_link_in_deficits_does_not_change_the_lesion(routes, qapp):
    from cns_atlas.lesions import structure_lesion

    routes.workspaces.switch("Lesion")
    qapp.processEvents()
    lesion = routes.lesion
    lesion.place.set_tool("structure")
    lesion.document.set_lesion(structure_lesion(routes.state.atlas, 101), "Alpha")
    before = lesion.document.lesion
    follow(lesion.deficits, "structure:120")
    assert routes.state.selected == 120
    assert lesion.document.lesion is before


def deficit(step, sign, partly, side="left"):
    from cns_atlas.lesions import Deficit

    return Deficit("loop", "Toy loop", side, step, "Loss.", sign, partly, ((101, 0.9),))


def two_signs():
    from cns_atlas.lesions import Report

    return Report({}, (deficit(0, "Weakness [1]", False), deficit(2, "Weakness", True),
                       deficit(3, "Numbness", True)), ())


def test_signs_are_listed_once_and_partly_only_when_always_partly():
    from cns_desktop.lesion.results_panel import likely_signs

    found = [(sign, partly) for sign, partly, _d in likely_signs(two_signs())]
    assert found == [("Weakness", False), ("Numbness", True)]


def test_the_signs_block_opens_deficits(routes):
    routes.lesion.deficits.show_case(two_signs(), "Toy case")
    text = routes.lesion.deficits.toPlainText()
    assert "Likely signs" in text and "Show route" in text
    assert text.index("Likely signs") < text.index("Toy loop")


def test_no_signs_means_no_signs_block(routes):
    from cns_atlas.lesions import Report

    routes.lesion.deficits.show_case(Report({}, (deficit(0, "", False),), ()), "Toy case")
    assert "Likely signs" not in routes.lesion.deficits.toPlainText()


def test_show_route_opens_the_route_at_the_broken_step(routes, qapp):
    routes.workspaces.switch("Lesion")
    qapp.processEvents()
    follow(routes.lesion.deficits, "route:loop/right/2")
    qapp.processEvents()
    assert routes.workspaces.current == "Pathways"
    assert routes.pathways.pathway.key == "loop" and routes.pathways.index == 2
    assert routes.pathways.side == "right"


def test_a_tract_shown_by_a_link_hides_again_when_the_selection_moves_on(routes):
    tract = routes.state.geometry_in(150)
    assert all(routes.state.is_hidden(i) for i in tract)
    routes.follow_link(150)
    assert not any(routes.state.is_hidden(i) for i in tract)
    routes.state.select(120)
    assert all(routes.state.is_hidden(i) for i in tract)


def test_alt_left_is_left_to_the_back_shortcut_while_a_list_has_focus(window):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    def override(modifiers):
        event = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_Left, modifiers)
        return window.eventFilter(window.tree.tree, event)

    assert override(Qt.KeyboardModifier.NoModifier) is True
    assert override(Qt.KeyboardModifier.AltModifier) is False


def test_a_link_that_selects_nothing_leaves_no_back_behind(window):
    window.state.select(101)
    follow(window.info, "structure:999999")
    window.state.select(120)
    assert window.info.trail == []
    assert "Back to" not in window.info.toPlainText()
