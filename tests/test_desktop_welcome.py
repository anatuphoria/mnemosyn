import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from cns_atlas import Atlas
from cns_desktop.app import offer_welcome
from cns_desktop.main_window import MainWindow
from cns_desktop.views.welcome import PAGES, SEEN_KEY

pytestmark = pytest.mark.usefixtures("themed")


def open_window(qapp, root, tmp_path, settings=None):
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite",
                        settings=settings)
    window.resize(1400, 900)
    window.show()
    qapp.processEvents()
    return window


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = open_window(qapp, toy_lab_atlas, tmp_path, settings)
    yield w
    w.lab.document.undo.setClean()
    w.close()


def test_the_tour_walks_the_workspaces_and_switches_them(window, qapp):
    tour = window.show_welcome()
    assert tour.isVisible() and not tour.isModal()
    assert [page[0] for page in tour.pages] == [None, "Explore", "Slices", "Pathways", "Lab",
                                                "Lesion", "Explore"]
    assert tour.counter.text() == "1 of 7" and not tour.back_button.isEnabled()
    seen = []
    for _ in range(6):
        tour.next_button.click()
        qapp.processEvents()
        seen.append(window.workspaces.current)
    assert seen == ["Explore", "Slices", "Pathways", "Lab", "Lesion", "Explore"]
    assert tour.next_button.text() == "Done" and not tour.skip_button.isVisible()
    tour.back_button.click()
    assert window.workspaces.current == "Lesion" and tour.next_button.text() == "Next"
    tour.next_button.click()
    tour.next_button.click()
    assert not tour.isVisible()


def test_the_tour_stays_inside_the_window_and_fits_its_text(window, qapp):
    tour = window.show_welcome()
    for index in range(len(tour.pages)):
        tour.go(index)
        qapp.processEvents()
        assert tour.text.height() >= tour.text.heightForWidth(tour.text.width())
        assert window.frameGeometry().contains(tour.frameGeometry().center())
    tour.reject()


def test_the_tour_opens_once_for_a_new_user_and_again_from_help(window):
    assert not window.settings.value(SEEN_KEY, False, type=bool)
    offer_welcome(window)
    first = window.welcome
    assert first.isVisible() and window.settings.value(SEEN_KEY, False, type=bool)
    first.reject()
    del window.welcome
    offer_welcome(window)
    assert not hasattr(window, "welcome")
    assert "Welcome tour" in [a.text() for a in window.help_menu.actions()]
    window.welcome_action.trigger()
    assert window.welcome.isVisible()
    window.welcome.reject()


def test_the_tour_waits_for_the_first_start_notice(window):
    box = QMessageBox(window)
    offer_welcome(window, box)
    assert not hasattr(window, "welcome")
    box.finished.emit(0)
    assert window.welcome.isVisible()
    window.welcome.reject()


def test_the_tour_is_not_offered_during_a_quiz_or_without_settings(qapp, toy_lab_atlas, tmp_path):
    window = open_window(qapp, toy_lab_atlas, tmp_path)
    offer_welcome(window)
    assert not hasattr(window, "welcome")
    window.quiz_active = True
    assert window.show_welcome() is None
    window.quiz_active = False
    window.lab.document.undo.setClean()
    window.close()


def test_an_atlas_without_extras_gets_a_shorter_tour(qapp, toy_atlas, tmp_path):
    window = open_window(qapp, toy_atlas, tmp_path)
    tour = window.show_welcome()
    names = [page[0] for page in tour.pages]
    assert "Lab" not in names and len(tour.pages) < len(PAGES)
    tour.reject()
    window.close()
