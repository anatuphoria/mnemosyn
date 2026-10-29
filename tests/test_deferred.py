import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from cns_atlas import Atlas
from cns_desktop.design import theme
from cns_desktop.design.theme import apply_theme
from cns_desktop.design.tokens import COLOURS
from cns_desktop.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def open_window(qapp, atlas, tmp_path, width=1400, height=900, settings=None):
    settings = settings or QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.show()
    for _ in range(3):
        w.resize(width, height)
        qapp.processEvents()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    w.close()


def test_an_unknown_icon_falls_back_to_its_group(window):
    from dataclasses import replace

    from cns_desktop.lab.experiments_panel import GROUP_ICONS, icon_for

    model = window.lab.document.model
    pill = model.experiment("pill")
    odd = replace(model, experiments=tuple(replace(e, icon="from-a-newer-atlas") if e is pill
                                           else e for e in model.experiments))
    assert icon_for(odd, "pill") == GROUP_ICONS["Drugs"]


def test_setting_the_same_tone_does_not_repolish(qapp, monkeypatch):
    label = QLabel("x")
    theme.set_tone(label, "raised")
    theme.set_role(label, "secondary")
    calls = []
    monkeypatch.setattr(theme, "_repolish", lambda widget: calls.append(widget))
    theme.set_tone(label, "raised")
    theme.set_role(label, "secondary")
    assert calls == []
    theme.set_tone(label, "lowered")
    assert calls == [label]


def test_open_in_the_lab_is_a_secondary_button(window):
    assert window.pathways.lab_button.property("variant") in (None, "")


def test_slice_letters_use_the_text_token(window):
    for letter in window.slices.letters:
        assert letter.textItem.defaultTextColor().name() == COLOURS["text"]


def test_panels_cannot_be_dragged_into_bottom_tabs(window):
    assert not window.dockOptions() & QMainWindow.DockOption.AllowTabbedDocks


def test_the_time_axis_stays_aligned_when_rows_scroll(qapp):
    import numpy as np
    from PySide6.QtCore import QPointF

    from cns_desktop.design.charts import Series, SmallMultiples

    widget = SmallMultiples("h")
    widget.set_series([Series(f"v{n}", f"V{n}", "u", "#6d98f2") for n in range(8)])
    xs = np.linspace(0, 24, 30)
    for n in range(8):
        widget.set_line(f"v{n}", "run", xs, np.sin(xs + n))
    widget.set_x_range(0, 24)
    widget.resize(700, 260)
    widget.show()
    for _ in range(3):
        qapp.processEvents()
    assert widget.scroll.verticalScrollBar().isVisible()
    row_box = widget.rows[0].plot.getPlotItem().vb
    axis_box = widget.axis.getPlotItem().vb
    row_global = widget.rows[0].plot.mapToGlobal(widget.rows[0].plot.mapFromScene(
        row_box.mapViewToScene(QPointF(12.0, 0.0)))).x()
    axis_global = widget.axis.mapToGlobal(widget.axis.mapFromScene(
        axis_box.mapViewToScene(QPointF(12.0, 0.0)))).x()
    assert abs(row_global - axis_global) <= 1


def test_closing_during_a_quiz_saves_the_normal_layout(qapp, toy_lab_atlas, tmp_path):
    import random

    from cns_study.session import QuizChoice

    w = open_window(qapp, toy_lab_atlas, tmp_path)
    w.start_quiz(QuizChoice("find", "structures", None, False), rng=random.Random(1))
    qapp.processEvents()
    assert w.quiz_active
    w.lab.document.undo.setClean()
    w.close()
    again = open_window(qapp, toy_lab_atlas, tmp_path, settings=w.settings)
    visible = {g.objectName() for g in again.workspace_docks() if g.isVisible()}
    assert visible == {"Structures", "Info"}
    assert again.info_group.keys() == ["info", "slices"]
    assert not again.quiz_group.isVisible()
    again.lab.document.undo.setClean()
    again.close()


def test_the_pyvistaqt_cleanup_call_still_exists(window):
    assert callable(getattr(window.view, "_forget_context", None))


def test_switching_workspaces_leaves_no_floating_or_headless_panel(window, qapp):
    from cns_desktop.design.panels import PanelGroup
    from cns_desktop.design.widgets import PanelHeader

    window.info_group.setFloating(True)
    window.info_group.close()
    window.info_group.toggleViewAction().trigger()
    for name in ("Slices", "Explore", "Pathways", "Lab", "Explore"):
        window.workspaces.switch(name)
        qapp.processEvents()
        groups = [g for g in window.findChildren(PanelGroup) if g.isVisible()]
        headers = [h for h in window.findChildren(PanelHeader) if h.isVisible()
                   and isinstance(h.parentWidget(), PanelGroup)]
        assert len(headers) == len(groups), name
        assert all(g.titleBarWidget() is g.header for g in groups)
        assert all(g.keys() for g in groups), name


@pytest.mark.parametrize("name", ["Explore", "Pathways", "Lab"])
def test_a_short_window_scrolls_its_panels(qapp, toy_lab_atlas, tmp_path, name):
    from PySide6.QtWidgets import QScrollArea

    w = open_window(qapp, toy_lab_atlas, tmp_path, 1400, 900)
    try:
        w.workspaces.switch(name)
        if name == "Pathways":
            w.pathways.open("mood")
        for _ in range(3):
            w.resize(1400, 380)
            qapp.processEvents()
        assert w.height() == 380, name
        holder = w.pathways.parentWidget().parentWidget()
        assert isinstance(holder, QScrollArea)
    finally:
        w.lab.document.undo.setClean()
        w.close()


def _focusable_chain(window, start):
    from PySide6.QtCore import Qt

    order, widget = [], start
    for _ in range(2000):
        widget = widget.nextInFocusChain()
        if widget is start:
            break
        if (widget.isVisible() and widget.isEnabled()
                and widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.window() is window):
            order.append(widget)
    return order


def test_tab_goes_through_the_top_bar_before_the_view(window, qapp):
    chain = _focusable_chain(window, window.view)
    in_bar = [window.topbar.isAncestorOf(w) for w in chain]
    assert any(in_bar)
    first = in_bar.index(True)
    assert all(in_bar[first:]), "the top bar tools should come last before the view again"


def test_focused_fields_show_a_ring_without_growing(window, qapp):
    import re

    from cns_desktop.design import stylesheet

    css = stylesheet.build()
    assert re.search(r"QLineEdit:focus[^{]*\{ border: 2px solid " + COLOURS["accent"], css)
    field = window.tree.filter_box
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus() and field.height() == 28


def test_focused_spin_and_combo_boxes_keep_their_height(qapp):
    from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QVBoxLayout, QWidget

    holder = QWidget()
    column = QVBoxLayout(holder)
    combo = QComboBox()
    combo.addItems(["1 day", "8 weeks"])
    spin = QDoubleSpinBox()
    column.addWidget(combo)
    column.addWidget(spin)
    holder.show()
    for widget in (combo, spin):
        widget.setFocus()
        qapp.processEvents()
        assert widget.hasFocus()
        assert widget.sizeHint().height() == 28, type(widget).__name__


def test_a_collapsed_3d_view_hands_focus_to_the_slice_view(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path, 850, 700)
    try:
        w.activateWindow()
        w.view.setFocus()
        w.workspaces.switch("Slices")
        qapp.processEvents()
        assert w.viewport.isHidden()
        assert QApplication.focusWidget() is w.slices.view
    finally:
        w.lab.document.undo.setClean()
        w.close()


def test_switching_workspaces_puts_focus_back_on_the_view(window, qapp):
    window.activateWindow()
    window.tree.filter_box.setFocus()
    for name in ("Lab", "Pathways", "Explore"):
        window.workspaces.switch(name)
        qapp.processEvents()
        assert QApplication.focusWidget() is window.view, name
