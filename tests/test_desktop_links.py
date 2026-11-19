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
