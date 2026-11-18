import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.tokens import SIZE
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.model_panel import ModelPanel


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def drag(bar, to_fraction):
    track = bar.track_rect()
    y = track.center().y()
    start = QPoint(track.center().x(), y)
    moved = (to_fraction - bar.scale.fraction(bar.value)) * track.width()
    end = QPoint(round(start.x() + moved), y)
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(bar, end)
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)


def test_settings_appear_under_their_groups(doc):
    panel = ModelPanel(doc)
    assert panel.group_titles() == ["FEEDBACK", "CLEARING", "RHYTHM", "STRESS"]


def test_a_rate_slider_commits_once_on_release(doc):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    slider = panel.control("w")
    drag(slider, slider.scale.fraction(0.2))
    assert doc.experiment.value_map == {"w": pytest.approx(0.2, rel=0.03)}
    assert doc.undo.count() == 1
    assert panel.badge("w").text() == "2× normal"
    assert panel.note("w").text() == "X and Y clear faster."
    assert panel.spin("w").value() == pytest.approx(0.2, rel=0.03)


def test_a_drag_only_previews_until_release(doc):
    panel = ModelPanel(doc)
    slider = panel.control("w")
    slider.previewed.emit(0.3)
    assert doc.experiment.values == () and doc.undo.count() == 0
    assert panel.spin("w").value() == pytest.approx(0.3)
    assert panel.badge("w").text() == "3× normal"


def test_typing_still_sets_the_exact_value(doc):
    panel = ModelPanel(doc)
    panel.spin("w").setValue(0.123)
    panel.spin("w").editingFinished.emit()
    assert doc.experiment.value_map == {"w": 0.123}


def test_releasing_on_normal_removes_the_edit(doc):
    panel = ModelPanel(doc)
    doc.set_value("w", 0.3)
    panel.control("w").committed.emit(0.1)
    assert doc.experiment.values == () and not panel.is_marked("w")
    assert panel.badge("w").isHidden() and panel.note("w").isHidden()


def test_a_slider_snaps_to_normal_near_its_tick(doc):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    doc.set_value("w", 0.3)
    slider = panel.control("w")
    drag(slider, slider.scale.fraction(0.1) + 0.005)
    assert doc.experiment.values == ()


def test_a_switch_selects_its_stop_or_none(doc):
    panel = ModelPanel(doc)
    switch = panel.control("a")
    assert switch.current() == "normal"
    switch.choose("deep")
    assert doc.experiment.value_map == {"a": 0.9}
    doc.set_value("a", 0.5)
    assert switch.current() is None and panel.spin("a").value() == 0.5


def test_a_curve_handle_moves_the_halfway_point(doc):
    panel = ModelPanel(doc)
    graph = panel.control("k")
    assert graph.curve.key == "feedback"
    graph.committed.emit("k", 4.0)
    assert doc.experiment.value_map == {"k": 4.0}
    assert panel.spin("k").value() == 4.0 and panel.is_marked("k")
    assert graph.values()["k"] == 4.0


def test_undo_after_a_drag_restores_the_control(doc):
    panel = ModelPanel(doc)
    panel.control("w").committed.emit(0.3)
    doc.undo.undo()
    assert panel.control("w").value == pytest.approx(0.1) and panel.badge("w").isHidden()


def test_a_value_between_stops_from_a_file_shows_no_stop(doc):
    doc.load(doc.experiment.replace(values=(("a", 0.5),)), None)
    panel = ModelPanel(doc)
    assert panel.control("a").current() is None and panel.spin("a").value() == 0.5


def test_switching_systems_rebuilds_the_groups(qapp):
    from cns_desktop.app import DEFAULT_ATLAS

    doc = LabDocument(Atlas.open(DEFAULT_ATLAS), "stress", compute=False)
    panel = ModelPanel(doc)
    assert panel.group_titles()[0] == "REMOVAL AND TURNOVER"
    doc.set_model("water")
    assert panel.group_titles() == ["VASOPRESSIN", "KIDNEY", "WATER AND SALT", "THIRST AND DRINKING",
                                    "DRUGS"]
    assert all(panel.control(p.key) is not None for p in doc.model.parameters if p.panel)
    with pytest.raises(KeyError):
        panel.control("w1")


def test_a_clock_field_reads_the_time_of_day(qapp):
    from cns_desktop.app import DEFAULT_ATLAS

    panel = ModelPanel(LabDocument(Atlas.open(DEFAULT_ATLAS), "stress", compute=False))
    assert panel.spin("phase").text() == "8:20"
    panel.spin("phase").lineEdit().setText("9:30")
    panel.spin("phase").interpretText()
    assert panel.spin("phase").value() == 570.0


def test_the_model_tab_fits_the_narrowest_panel(doc, qapp):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_min"], 900)
    panel.show()
    qapp.processEvents()
    assert panel.minimumSizeHint().width() <= SIZE["panel_min"]
    for p in doc.model.parameters:
        if p.panel:
            for widget in (panel.control(p.key), panel.spin(p.key), panel.reset_button(p.key)):
                if not widget.isVisibleTo(panel):
                    continue
                right = widget.mapTo(panel, widget.rect().topRight()).x()
                assert widget.width() > 0 and right <= SIZE["panel_min"], (p.key, right)
    panel.close()


def wheel(widget, notches=1):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent

    centre = QPointF(widget.rect().center())
    event = QWheelEvent(centre, widget.mapToGlobal(centre), QPoint(0, 0), QPoint(0, 120 * notches),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    return event


def test_scrolling_over_a_curve_scrolls_the_tab_until_it_is_clicked(qapp):
    from cns_desktop.app import DEFAULT_ATLAS

    doc = LabDocument(Atlas.open(DEFAULT_ATLAS), "water", compute=False)
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    graph = panel.control("K_u")
    event = wheel(graph)
    assert not event.isAccepted() and "n_u" not in graph.values()
    centre = graph.rect().center()
    QTest.mousePress(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    QTest.mouseRelease(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    assert wheel(graph, -1).isAccepted() and graph.values()["n_u"] < 4.0
    panel.close()


def test_clicking_a_bar_without_moving_keeps_the_value_and_opens_its_field(doc, qapp):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    doc.set_value("w", 0.05)
    steps = doc.undo.count()
    bar = panel.control("w")
    here = bar.track_rect().center()
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, here)
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, here)
    qapp.processEvents()
    assert doc.experiment.value_map == {"w": 0.05} and doc.undo.count() == steps
    field = panel.spin("w").geometry()
    assert bar.editing() and field.width() == bar.width()
    assert abs((field.top() - bar.rect().top()) - (bar.rect().bottom() - field.bottom())) <= 1
    panel.close()


def test_typing_in_an_opened_bar_commits_and_escape_cancels(doc, qapp):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    bar = panel.control("w")
    bar.open_editor()
    spin = panel.spin("w")
    spin.lineEdit().setText("0.2")
    QTest.keyClick(spin, Qt.Key.Key_Return)
    qapp.processEvents()
    assert doc.experiment.value_map == {"w": pytest.approx(0.2)}
    steps = doc.undo.count()
    bar.open_editor()
    spin.lineEdit().setText("0.4")
    QTest.keyClick(spin.lineEdit(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not bar.editing() and doc.undo.count() == steps
    assert doc.experiment.value_map == {"w": pytest.approx(0.2)}
    panel.close()


def test_a_bar_leaves_the_wheel_to_the_panel_scroll(doc):
    panel = ModelPanel(doc)
    assert wheel(panel.control("w"), -1).isAccepted() is False
    assert doc.experiment.values == ()


def test_a_dragged_value_matches_its_field_so_leaving_the_field_adds_nothing(doc):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    slider = panel.control("w")
    drag(slider, 0.83)
    value = doc.experiment.value_map["w"]
    assert value == round(value, panel.spin("w").decimals())
    steps = doc.undo.count()
    panel.spin("w").editingFinished.emit()
    assert doc.undo.count() == steps
    panel.close()


def test_an_edited_rate_keeps_its_field_readable_at_the_narrowest_width(doc, qapp):
    doc.set_value("w", 0.5)
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_min"], 900)
    panel.show()
    qapp.processEvents()
    bar = panel.control("w")
    bar.open_editor()
    spin = panel.spin("w")
    edit = spin.lineEdit()
    assert edit.width() >= edit.fontMetrics().horizontalAdvance(spin.text())
    assert panel.badge("w").mapTo(panel, panel.badge("w").rect().topLeft()).y() > \
        bar.mapTo(panel, bar.rect().bottomLeft()).y()
    panel.close()


def test_dragging_a_curve_moves_its_halfway_point(doc):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    graph = panel.control("k")
    plot = graph._plot()
    y = int(plot.center().y())
    start = QPoint(int(graph._x_of(2.0, plot)), y)
    end = QPoint(int(graph._x_of(6.0, plot)), y)
    QTest.mousePress(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(graph, end)
    QTest.mouseRelease(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    assert doc.experiment.value_map["k"] == pytest.approx(6.0, abs=0.1)
    assert doc.undo.count() == 1 and panel.is_marked("k")
    panel.close()


def test_scrolling_a_clicked_curve_settles_into_one_step(qapp):
    from cns_desktop.app import DEFAULT_ATLAS

    doc = LabDocument(Atlas.open(DEFAULT_ATLAS), "water", compute=False)
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    graph = panel.control("K_u")
    centre = graph.rect().center()
    QTest.mousePress(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    QTest.mouseRelease(graph, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    steps = doc.undo.count()
    wheel(graph, -1)
    wheel(graph, -1)
    assert "n_u" not in doc.experiment.value_map
    QTest.qWait(600)
    assert doc.experiment.value_map["n_u"] < 4.0 and doc.undo.count() == steps + 1
    panel.close()


def test_building_setting_rows_never_opens_a_window_of_its_own(doc, qapp):
    from PySide6.QtCore import QEvent, QObject

    opened = []

    class Spy(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and obj.isWidgetType() and obj.isWindow():
                opened.append(type(obj).__name__)
            return False

    panel = ModelPanel(doc)
    panel.show()
    spy = Spy()
    qapp.installEventFilter(spy)
    try:
        for key in [p.key for p in doc.model.parameters if p.panel]:
            doc.set_value(key, doc.model.parameter(key).high)
        for value in doc.model.values:
            doc.select(("value", value.key))
        for part in doc.model.parts:
            doc.select(("part", part.key))
    finally:
        qapp.removeEventFilter(spy)
        panel.close()
    assert opened == []
