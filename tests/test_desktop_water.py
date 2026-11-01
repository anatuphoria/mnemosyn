from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from cns_atlas import Atlas
from cns_desktop.main_window import MainWindow

REAL_ATLAS = Path(__file__).resolve().parent.parent / "atlases" / "cns"
WATER_LANES = ["sodium", "avp", "uosm", "thirst"]

pytestmark = pytest.mark.slow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    if not (REAL_ATLAS / "structures.json").exists():
        pytest.skip("real atlas not built; run python -m tools.build_atlas")
    w = MainWindow(Atlas.open(REAL_ATLAS), progress_path=tmp_path / "progress.sqlite")
    w.ask = lambda *args: QMessageBox.StandardButton.Discard
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    yield w
    w.lab.document.undo.setClean()
    w.close()


def switch_to(window, key):
    lab = window.lab
    window.workspaces.switch("Lab")
    lab.choose_system(key)
    return lab


def test_the_picker_offers_water_balance_and_switches_both_ways(window, qapp):
    lab = switch_to(window, "water")
    assert lab.system_box.findData("water") >= 0 and lab.document.model.key == "water"
    assert lab.timeline.lane_keys() == WATER_LANES
    names = {e.key for e in lab.document.model.experiments}
    assert {"water_load", "central_di"} <= names and "dexamethasone" not in names
    lab.document.add_block("water_load", 120.0)
    lab.choose_system("stress")
    qapp.processEvents()
    assert lab.document.model.key == "stress" and "sodium" not in lab.timeline.lane_keys()
    assert lab.document.experiment.blocks == ()


def test_a_saved_water_experiment_reopens_as_water(window, tmp_path):
    lab = switch_to(window, "water")
    lab.document.add_block("central_di", 0.0)
    path = tmp_path / "di.mnemolab"
    assert lab._write(path)
    lab.choose_system("stress")
    lab.open(path)
    assert lab.document.model.key == "water"
    assert [b.experiment for b in lab.document.experiment.blocks] == ["central_di"]


def test_open_in_the_lab_from_the_thirst_route(window, qapp):
    window.pathways.open("thirst")
    assert window.pathways.lab_button.isVisibleTo(window.pathways)
    window.pathways.lab_button.click()
    qapp.processEvents()
    assert window.workspaces.current == "Lab" and window.lab.document.model.key == "water"


def test_the_deprivation_test_reads_in_the_inspector(window):
    lab = switch_to(window, "water")
    lab.document.add_block("central_di", 0.0)
    lab.document.add_block("water_deprivation_test", 60.0)
    lab.document.select(("block", 1))
    text = lab.inspector.text()
    assert "Water deprivation test" in text and "Abnormal" in text


def test_the_why_panel_names_small_sodium_changes(window):
    lab = switch_to(window, "water")
    lab.document.add_block("stop_drinking", 60.0)
    lab.document.set_playhead(60.0 + 360.0)
    lab.why.refresh()
    text = lab.why.toPlainText()
    assert "Plasma sodium is unchanged" not in text and "Plasma sodium rises" in text


def test_the_desmopressin_test_shows_both_readings(window):
    lab = switch_to(window, "water")
    lab.document.add_block("nephrogenic_di", 0.0)
    lab.document.add_block("desmopressin_test", 60.0)
    lab.document.select(("block", 1))
    text = lab.inspector.text()
    assert "after 8 h" in text and "after 10 h" in text
    assert "stayed dilute" in text and "nephrogenic" in text and "e+" not in text


def test_large_readings_are_written_as_whole_numbers(window):
    lab = switch_to(window, "water")
    lab.document.add_block("central_di", 0.0)
    lab.document.add_block("desmopressin_test", 60.0)
    lab.document.select(("block", 1))
    text = lab.inspector.text()
    assert "e+" not in text and "mOsm/kg after 10 h" in text


def test_every_water_lane_shows_without_scrolling(window, qapp):
    lab = switch_to(window, "water")
    qapp.processEvents()
    timeline = lab.timeline
    assert timeline.height() >= timeline.wanted_height()
    last = timeline.lane_rect(timeline.lane_keys()[-1])
    assert last.bottom() <= timeline.height()


def test_the_first_lab_opens_with_every_lane_shown(window, qapp):
    window.workspaces.switch("Lab")
    qapp.processEvents()
    qapp.processEvents()
    timeline = window.lab.timeline
    assert timeline.height() >= timeline.wanted_height()
