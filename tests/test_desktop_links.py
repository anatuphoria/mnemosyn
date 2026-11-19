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
