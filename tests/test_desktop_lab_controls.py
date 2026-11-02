import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cns_atlas import Atlas
from cns_desktop.design.tokens import SIZE
from cns_desktop.lab.document import LabDocument
from cns_desktop.lab.model_panel import ModelPanel


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def doc(qapp, toy_lab_atlas):
    return LabDocument(Atlas.open(toy_lab_atlas), "toy")


def drag(slider, to_fraction):
    track = slider.track_rect()
    y = track.center().y()
    start = QPoint(int(track.left() + slider.scale.fraction(slider.value) * track.width()), y)
    end = QPoint(int(track.left() + to_fraction * track.width()), y)
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(slider, end)
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)


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


def test_clicking_a_handle_without_moving_keeps_the_exact_value(doc):
    panel = ModelPanel(doc)
    panel.resize(SIZE["panel_left"], 900)
    panel.show()
    doc.set_value("w", 0.05)
    steps = doc.undo.count()
    slider = panel.control("w")
    track = slider.track_rect()
    here = QPoint(int(track.left() + slider.scale.fraction(0.05) * track.width()) + 2,
                  track.center().y())
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, here)
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, here)
    assert doc.experiment.value_map == {"w": 0.05} and doc.undo.count() == steps
    panel.close()


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
    spin = panel.spin("w")
    edit = spin.lineEdit()
    assert edit.width() >= edit.fontMetrics().horizontalAdvance(spin.text())
    assert panel.badge("w").mapTo(panel, panel.badge("w").rect().topLeft()).y() > \
        spin.mapTo(panel, spin.rect().bottomLeft()).y()
    panel.close()


def test_slider_labels_never_overlap(qapp):
    from cns_desktop.lab.controls import ScaleSlider
    from cns_desktop.lab.scales import LinearScale, LogScale

    for scale, normal in ((LinearScale(1.5, 10.0, 2.0), 2.0), (LinearScale(5.0, 500.0, 35.0), 35.0),
                          (LogScale(0.0005, 0.005, 0.00167), 0.00167)):
        slider = ScaleSlider(scale, normal, normal)
        slider.resize(SIZE["panel_min"] - 2 * SIZE["panel_pad"], SIZE["slider"])
        rects = [rect for rect, _label in slider.label_rects()]
        assert "normal" in [label for _rect, label in slider.label_rects()]
        assert all(not a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1:])
