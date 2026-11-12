import pytest
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

from cns_desktop.views.structure_tree import NameDelegate, shorten


@pytest.fixture(scope="module")
def metrics():
    QApplication.instance() or QApplication([])
    return QFontMetrics(QFont())


def room_for(metrics, text):
    return metrics.horizontalAdvance(text) + 2


def test_a_name_that_fits_is_left_alone(metrics):
    name = "Thalamus"
    assert shorten(name, metrics, room_for(metrics, name)) == name


def test_the_part_after_the_last_comma_survives(metrics):
    opercular = "Inferior frontal gyrus, opercular part"
    triangular = "Inferior frontal gyrus, triangular part"
    width = room_for(metrics, "Inferior f…, triangular part")
    a, b = shorten(opercular, metrics, width), shorten(triangular, metrics, width)
    assert a.endswith(", opercular part") and b.endswith(", triangular part")
    assert a != b
    assert metrics.horizontalAdvance(a) <= width and metrics.horizontalAdvance(b) <= width


def test_the_side_survives(metrics):
    width = room_for(metrics, "Precentral g… (left)")
    left = shorten("Precentral gyrus (left)", metrics, width)
    right = shorten("Precentral gyrus (right)", metrics, width)
    assert left.endswith(" (left)") and right.endswith(" (right)")
    assert left.startswith("Precentral")


def test_a_comma_and_a_side_both_survive(metrics):
    name = "Inferior frontal gyrus, opercular part (left)"
    width = room_for(metrics, "Inferior f…, opercular part (left)")
    assert shorten(name, metrics, width).endswith(", opercular part (left)")


def test_without_a_comma_or_side_the_middle_goes(metrics):
    name = "Superior temporal sulcus"
    short = shorten(name, metrics, room_for(metrics, "Superior …l sulcus"))
    assert short.startswith("Superior") and short.endswith("sulcus") and "…" in short


def test_when_even_the_tail_does_not_fit_its_start_is_kept(metrics):
    width = room_for(metrics, "Mediodorsal nucl")
    medial = shorten("Mediodorsal nucleus, medial magnocellular part", metrics, width)
    lateral = shorten("Mediodorsal nucleus, lateral parvocellular part", metrics, width)
    assert medial.startswith("… medial") and lateral.startswith("… lateral")
    assert metrics.horizontalAdvance(medial) <= width


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


def test_in_a_tight_spot_the_front_shrinks_to_an_ellipsis(metrics):
    width = room_for(metrics, "…, opercular part")
    assert shorten("Inferior frontal gyrus, opercular part", metrics, width) == "…, opercular part"


def test_a_long_tail_still_keeps_its_side(metrics):
    width = room_for(metrics, "Superior fron")
    left = shorten("Superior frontal gyrus, medial orbital part (left)", metrics, width)
    right = shorten("Superior frontal gyrus, medial orbital part (right)", metrics, width)
    assert left.endswith("(left)") and right.endswith("(right)")
    assert metrics.horizontalAdvance(left) <= width
