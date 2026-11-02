import pytest
from PySide6.QtWidgets import QApplication

from cns_desktop.design.tokens import SIZE
from pathway_helpers import open_window


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    w.workspaces.switch("Pathways")
    qapp.processEvents()
    yield w
    w.close()


def visible_children(tree):
    names = []
    for n in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(n)
        names += [group.child(m).text(0) for m in range(group.childCount())
                  if not group.child(m).isHidden()]
    return names


def test_routes_are_grouped_with_search(window):
    page = window.pathways.routes_page
    tree = page.choices
    groups = [tree.topLevelItem(n).text(0) for n in range(tree.topLevelItemCount())]
    assert groups == list(dict.fromkeys(p.group for p in window.state.atlas.pathways))
    assert window.routes_group.keys() == ["routes", "steps"]
    first = window.state.atlas.pathways[0].name
    page.search.setText(first[:4])
    shown = visible_children(tree)
    assert shown and all(first[:4].lower() in name.lower() for name in shown)
    assert all(not tree.topLevelItem(0).child(m).icon(0).isNull()
               for m in range(tree.topLevelItem(0).childCount()))


def test_opening_a_route_shows_the_steps_tab(window):
    window.pathways.open("loop")
    assert window.routes_group.current() == "steps"
    window.pathways.leave()
    assert window.routes_group.current() == "routes"


def test_a_click_on_a_route_opens_it(window):
    item = window.pathways.item_for("loop")
    window.pathways.choices.itemClicked.emit(item, 0)
    assert window.pathways.pathway.key == "loop"


def test_badges_mark_passed_current_and_later(window):
    panel = window.pathways
    panel.open("loop")
    panel.go(1)
    assert [panel.badge_state(r) for r in range(3)] == ["passed", "current", "later"]


def test_close_route_button_and_esc_close_it(window):
    panel = window.pathways
    panel.open("loop")
    assert panel.steps_page.close_button.text() == "Close route"
    panel.steps_page.close_button.click()
    assert panel.pathway is None and not window.pathway_active
    panel.open("loop")
    window.shortcuts["Close route"].trigger()
    assert panel.pathway is None
    assert not hasattr(panel, "leave_button")


def test_the_status_bar_says_esc_closes(window):
    window.pathways.open("loop")
    assert ("Esc", "close") in window._shown_keys


def test_nothing_clips_at_the_narrowest_width(window, qapp):
    window.pathways.open("loop")
    page = window.pathways.steps_page
    page.resize(SIZE["panel_min"], 700)
    page.show()
    qapp.processEvents()
    assert page.close_button.width() >= page.close_button.minimumSizeHint().width()
    assert page.steps.horizontalScrollBar().maximum() == 0
