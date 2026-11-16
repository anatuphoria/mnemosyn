import pytest

from cns_desktop.lab.timescale import HOURS, MINUTES, coarse_text, fine_text, scale_of
from cns_study.questions import LAB_MODE, lab_items
from cns_study.session import QuizChoice
from pathway_helpers import open_window

pytestmark = pytest.mark.usefixtures("themed")
SHARED = "build/atlas-shareable"


def test_times_read_in_seconds_on_the_fine_scale_only():
    assert [fine_text(m) for m in (0, 0.25, 1, 2.5, 59.99, 60, 75)] == [
        "0 min", "15 s", "1 min", "2 min 30 s", "59 min 59 s", "1 h", "1 h 15 min"]
    assert [coarse_text(m) for m in (0, 30, 60, 90, 1440, 1500)] == [
        "0 h", "0 h 30 min", "1 h", "1 h 30 min", "1 d", "1 d 1 h"]
    assert MINUTES.text(0.5) == "30 s" and HOURS.text(30) == "0 h 30 min"


def test_snapping_follows_the_scale_and_the_zoom():
    assert HOURS.snap(61.4, 600) == 61 and HOURS.snap(61.4, 5000) == 60
    assert MINUTES.snap(2.51, 5) == pytest.approx(2.5167, abs=1e-3)
    assert MINUTES.snap(2.6, 60) == 2.5


def test_a_model_without_a_scale_uses_hours():
    assert scale_of(object()) is HOURS


@pytest.fixture
def window(qapp, tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / SHARED
    if not (root / "models.json").exists():
        pytest.skip("no shareable atlas built")
    w = open_window(qapp, root, tmp_path)
    if "pressure" not in w.state.atlas.models:
        w.close()
        pytest.skip("the built atlas is older than the blood pressure reflex")
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def lengths(lab):
    return [lab.length_box.itemText(i) for i in range(lab.length_box.count())]


@pytest.mark.slow
def test_switching_system_switches_the_run_lengths_and_back(window, qapp):
    lab = window.lab
    window.workspaces.switch("Lab")
    assert lab.document.model.key == "stress" and lab.document.experiment.length == 1440.0
    assert lengths(lab) == [label for label, _ in HOURS.lengths]
    lab.choose_system("pressure")
    qapp.processEvents()
    document = lab.document
    assert document.scale is MINUTES and document.experiment.length == 10.0
    assert lengths(lab) == [label for label, _ in MINUTES.lengths]
    assert lab.length_box.currentText() == "10 min"
    assert [a.text() for a in lab.length_menu.actions()] != []
    lab.length_action("2 min").trigger()
    assert document.experiment.length == 2.0
    document.set_length(0.2)
    assert document.experiment.length == 1.0
    document.undo.setClean()
    lab.choose_system("stress")
    qapp.processEvents()
    assert lab.document.experiment.length == 1440.0 and lengths(lab)[0] == "6 h"


@pytest.mark.slow
def test_a_short_change_keeps_its_length_and_the_timeline_zooms_to_seconds(window, qapp):
    lab = window.lab
    window.workspaces.switch("Lab")
    lab.choose_system("pressure")
    document = lab.document
    index = document.add_block("carotid_massage", 2.0)
    assert document.experiment.blocks[index].length == 0.25
    document.stretch_block(index, 0.001)
    assert document.experiment.blocks[index].length == MINUTES.least
    lab.timeline.zoom(0.0001, 2.0)
    start, end = lab.timeline.span
    assert end - start == pytest.approx(MINUTES.min_span)
    document.set_playhead(2.5)
    qapp.processEvents()
    from cns_desktop.lab.why_panel import time_heading

    assert time_heading(document, 2.5) == "At 2 min 30 s, 30 s after Press on the carotid sinus"
    assert document.error == ""


@pytest.mark.slow
def test_lab_quiz_questions_on_the_reflex_count_time_in_minutes(window):
    asked = [q for q in lab_items(window.state.atlas) if q.scope == "pressure"]
    assert len(asked) >= 30
    prompts = " ".join(q.prompt for q in asked)
    assert "minutes" in prompts and "On day" not in prompts
    window.start_quiz(QuizChoice(LAB_MODE, "lab", "pressure", True))
    assert "Blood pressure reflex" in window.quiz.prompt.text()
    window.quiz.stop()
