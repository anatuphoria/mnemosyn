import random

import pytest
from fsrs import State
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from cns_study.questions import LAB_MODE, OUTCOMES, ROUTE_MODE, lab_items, route_items
from cns_study.session import QuizChoice
from pathway_helpers import open_window

pytestmark = pytest.mark.usefixtures("themed")
KEYS = [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4]


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def start(window, level, practice=False, scope=None):
    mode = {"routes": ROUTE_MODE, "lab": LAB_MODE}[level]
    window.start_quiz(QuizChoice(mode, level, scope, practice), rng=random.Random(1))
    return window.quiz


def test_a_route_question_lights_its_station_and_then_the_next_one(window):
    assert route_items(window.state.atlas)
    quiz = start(window, "routes")
    item = quiz.item
    assert quiz.phase == "asking" and "what comes next?" in quiz.prompt.text()
    assert window.state.focus == (item.geometry or None)
    shown = [b for b in quiz.choice_buttons if b.isVisible()]
    assert len(shown) == len(quiz.texts) >= 3 and not quiz.answer_box.isVisible()
    QTest.keyClick(quiz, KEYS[quiz.texts.index(item.answer)])
    assert quiz.phase == "feedback" and "Correct" in quiz.feedback.text()
    assert item.answer in quiz.feedback.text() and not quiz.lab_button.isVisible()
    assert window.state.focus == ((item.geometry | item.reveal) or None)
    QTest.keyClick(quiz, Qt.Key.Key_Return)
    assert window.progress_store().card(item.id, ROUTE_MODE).state in (State.Learning,
                                                                        State.Review)
    quiz.stop()
    assert window.state.focus is None and not window.quiz_active


def test_a_route_question_shows_only_the_tracts_it_is_about(window):
    quiz = start(window, "routes", practice=True)
    state = window.state
    for _ in range(len(route_items(state.atlas))):
        item = quiz.item
        assert not [i for i in state.tract_ids if not state.is_hidden(i)
                    and i not in item.geometry]
        quiz.choose(quiz.texts.index(item.answer))
        assert all(not state.is_hidden(i) for i in (item.geometry | item.reveal)
                   if i in state.tract_ids)
        quiz.go_on()
        if quiz.phase != "asking":
            break
    quiz.stop()


def test_a_wrong_route_answer_names_the_choice_and_the_answer(window):
    quiz = start(window, "routes", practice=True)
    wrong = next(n for n, text in enumerate(quiz.texts) if text != quiz.item.answer)
    quiz.choice_buttons[wrong].click()
    text = quiz.feedback.text()
    assert "Wrong" in text and quiz.item.answer in text and quiz.texts[wrong] in text
    quiz.stop()


def test_clicking_a_structure_does_not_disturb_a_route_question(window, qapp):
    quiz = start(window, "routes", practice=True)
    item = quiz.item
    window.state.select(next(iter(window.state.geometry_ids)))
    qapp.processEvents()
    assert quiz.phase == "asking" and quiz.item is item
    quiz.stop()


def test_a_lab_question_offers_the_three_outcomes(window):
    assert lab_items(window.state.atlas)
    quiz = start(window, "lab", practice=True)
    assert quiz.texts == list(OUTCOMES)
    assert len([b for b in quiz.choice_buttons if b.isVisible()]) == 3
    QTest.keyClick(quiz, KEYS[quiz.texts.index(quiz.item.answer)])
    assert "Correct" in quiz.feedback.text() and "In the model" in quiz.feedback.text()
    assert quiz.lab_button.isVisible()
    quiz.stop()


def test_a_lab_question_opens_its_experiment_in_the_lab(window, qapp):
    quiz = start(window, "lab", practice=True)
    item = quiz.item
    QTest.keyClick(quiz, Qt.Key.Key_1)
    quiz.lab_button.click()
    qapp.processEvents()
    model, check, at = item.source
    assert not window.quiz_active and window.workspaces.current == "Lab"
    document = window.lab.document
    wanted = next(c for c in window.state.atlas.models[model].checks if c.key == check)
    assert document.model.key == model and document.experiment.length == wanted.length
    assert [b.experiment for b in document.experiment.blocks] == [r["experiment"] for r in wanted.blocks]
    assert document.playhead == at


def test_the_setup_window_offers_routes_and_lab(window):
    dialog = window.open_quiz_setup()
    levels = [dialog.level.itemData(n) for n in range(dialog.level.count())]
    assert levels == ["structures", "groups", "tracts", "routes", "lab"]
    dialog.level.setCurrentIndex(levels.index("routes"))
    assert not dialog.mode.isEnabled() and not dialog.answer_style.isEnabled()
    assert dialog.scope.itemText(0) == "All routes" and dialog.scope.count() > 1
    choice = dialog.choice()
    assert (choice.mode, choice.level, choice.scope) == (ROUTE_MODE, "routes", None)
    assert "new" in dialog.note.text()
    dialog.scope.setCurrentIndex(1)
    assert isinstance(dialog.choice().scope, str)
    dialog.level.setCurrentIndex(levels.index("lab"))
    assert dialog.scope.itemText(0) == "All systems" and dialog.choice().mode == LAB_MODE
    dialog.level.setCurrentIndex(0)
    assert dialog.mode.isEnabled() and dialog.scope.itemText(0) == "Whole atlas"
    dialog.reject()


def test_progress_counts_routes_and_lab(window):
    quiz = start(window, "lab")
    item = quiz.item
    QTest.keyClick(quiz, KEYS[quiz.texts.index(item.answer)])
    QTest.keyClick(quiz, Qt.Key.Key_Return)
    quiz.stop()
    dialog = window.show_progress()
    assert list(dialog.questions) == ["routes", "lab"]
    assert dialog.questions["lab"].name.text() == "Lab"
    known, learning, total = dialog.questions["lab"].bar.parts
    assert known + learning == 1 and total == len(lab_items(window.state.atlas))
    assert dialog.questions["lab"].isVisibleTo(dialog)
    dialog.reject()
