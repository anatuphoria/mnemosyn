import pytest
from PySide6.QtWidgets import QApplication

from cns_desktop.views.structure_tree import NameDelegate, StructureTree, relative_name


def test_the_tree_uses_the_name_delegate(qapp_window):
    tree = qapp_window.tree.tree
    assert isinstance(tree.itemDelegate(), NameDelegate)


@pytest.fixture
def qapp_window(tmp_path, toy_atlas):
    from cns_atlas import Atlas
    from cns_desktop.main_window import MainWindow

    QApplication.instance() or QApplication([])
    w = MainWindow(Atlas.open(toy_atlas), progress_path=tmp_path / "p.sqlite")
    yield w
    w.close()


def test_a_child_shows_only_what_differs_from_its_parent():
    assert relative_name("Precentral gyrus (left)", "Precentral gyrus") == "Left"
    assert relative_name("Inferior frontal gyrus, orbital part",
                         "Inferior frontal gyrus") == "Orbital part"
    assert relative_name("Inferior frontal gyrus, orbital part (right)",
                         "Inferior frontal gyrus, orbital part") == "Right"
    assert relative_name("Alpha gyrus, deep part (left)", "Alpha gyrus (left)") == (
        "Deep part (left)")


def test_a_name_that_does_not_repeat_its_parent_is_kept():
    assert relative_name("Thalamus", "Diencephalon") == "Thalamus"
    assert relative_name("Ponsette", "Pons") == "Ponsette"
    assert relative_name("Pons", None) == "Pons"
    assert relative_name("Pons", "Pons") == "Pons"


def test_the_tree_shows_relative_names_and_full_names_while_searching(qapp, toy_atlas, tmp_path):
    from cns_atlas import Atlas
    from cns_desktop.main_window import MainWindow

    window = MainWindow(Atlas.open(toy_atlas), progress_path=tmp_path / "progress.sqlite")
    try:
        item = window.tree.items[101]
        assert item.text(0) == "Left" and item.toolTip(0) == "Alpha gyrus (left)"
        window.tree.apply_filter("alpha")
        assert item.text(0) == "Alpha gyrus (left)"
        window.tree.apply_filter("")
        assert item.text(0) == "Left"
    finally:
        window.close()


def test_a_long_name_wraps_in_a_narrow_tree_and_fits_one_line_when_wide(qapp, toy_atlas):
    from cns_atlas import Atlas
    from cns_desktop.state import AppState

    panel = StructureTree(AppState(Atlas.open(toy_atlas)))
    panel.tree.expandAll()
    panel.resize(130, 500)
    panel.show()
    qapp.processEvents()
    tree = panel.tree
    long, short = panel.items[1], panel.items[2]
    assert tree.visualItemRect(long).height() > tree.visualItemRect(short).height()
    panel.resize(600, 500)
    qapp.processEvents()
    assert tree.visualItemRect(long).height() == tree.visualItemRect(short).height()
    panel.close()
