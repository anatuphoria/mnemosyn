from __future__ import annotations

from contextlib import nullcontext
from html import escape

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QLabel, QListWidgetItem, QPushButton,
                               QToolButton, QTreeWidgetItem, QWidget)

from cns_atlas import Crossing, Pathway, Relay, Station, Timeline
from cns_atlas.pathways import PathwayText, lights, side_of

from ..design import rich
from ..design.theme import set_role
from ..design.tokens import SIZE, color
from ..design.widgets import SegmentedControl, button_icon
from ..state import AppState
from .info_panel import references_html
from .pathway_pages import KEY_ROLE, STATE_ROLE, RoutesPage, StepsPage
from .step_panel import StepPanel

RELAY_COLOR = color("normal")
TICK_MS = 50
STEP_SECONDS = 3.0
PLAY_TIP = "Play  Space"
PAUSE_TIP = "Pause  Space"
SPEEDS = ((0.5, "½×"), (1.0, "1×"), (2.0, "2×"))


class PathwayPanel(QWidget):
    entered = Signal()
    left = Signal()
    lab_requested = Signal(str)
    centre_requested = Signal()
    timeline_changed = Signal(object)
    time_changed = Signal(float)
    playing_changed = Signal(bool)
    step_changed = Signal(str)
    edges_changed = Signal(bool, bool)
    route_opened = Signal()
    show_tab = Signal(str)
    step_drawn = Signal()

    def __init__(self, state: AppState, hold=nullcontext, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.hold = hold
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pathway: Pathway | None = None
        self.side = "left"
        self.index = 0
        self.lights: list[tuple[int, ...]] = []
        self.route: frozenset[int] = frozenset()
        self.text: PathwayText | None = None
        self._applying = False
        self.timeline: Timeline | None = None
        self.time = 0.0
        self._since = 0.0
        self.speed = 1.0

        self.routes_page = RoutesPage(state.atlas.pathways)
        self.choices = self.routes_page.choices
        self.empty = self.routes_page.empty
        self.steps_page = StepsPage()

        self.title = self.steps_page.title
        self.start = self.steps_page.start
        self.side_control = SegmentedControl([("left", "Left"), ("right", "Right")])
        self.side_control.changed.connect(self.set_side)
        self.side_buttons = {side: self.side_control.button(side) for side in ("left", "right")}
        self.side_control.hide()
        self.draft = self.steps_page.draft
        self._play_icon = button_icon("play")
        self._pause_icon = button_icon("pause")
        self.back_button = self._control(button_icon("skip-back"), "Back  Left", self.back)
        self.play_button = self._control(self._play_icon, PLAY_TIP, self.toggle_play)
        self.next_button = self._control(button_icon("skip-forward"), "Next  Right", self.next)
        self.speed_picker = QComboBox()
        for value, text in SPEEDS:
            self.speed_picker.addItem(text, value)
        self.speed_picker.setCurrentIndex(1)
        self.speed_picker.setToolTip("Speed")
        self.speed_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_picker.currentIndexChanged.connect(
            lambda i: self.set_speed(float(self.speed_picker.itemData(i))))
        self.speed_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.step_label = QLabel(self)
        self.step_label.setWordWrap(True)
        set_role(self.step_label, "label")
        self.playing_changed.connect(self._show_playing)
        self.edges_changed.connect(self._show_edges)
        self.step_changed.connect(self.step_label.setText)
        self.steps = self.steps_page.steps
        self.step_panel = StepPanel()
        self.details = self.step_panel.details
        self.step_panel.rendered.connect(self._mirror)
        self.lab_button = QPushButton("Open in the Lab")
        self.lab_button.hide()
        self.lab_routes = frozenset(m.route for m in state.atlas.models.values() if m.route)
        self.timer = QTimer(self, interval=TICK_MS, timeout=lambda: self.advance(TICK_MS / 1000))
        for widget in (*self.side_buttons.values(), self.steps, self.details):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        page = self.steps_page
        page.layout().addWidget(self.lab_button)

        self.choices.itemClicked.connect(self._on_choice)
        self.choices.itemActivated.connect(self._on_choice)
        self.steps.currentRowChanged.connect(self._on_row)
        self.steps.itemClicked.connect(self._on_step_clicked)
        page.close_button.clicked.connect(self.leave)
        self.set_controls_enabled(False)
        self.lab_button.clicked.connect(
            lambda: self.lab_requested.emit(self.pathway.key) if self.pathway else None)
        state.selection_changed.connect(self._on_selection)

    def _control(self, icon, tip: str, action) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
        button.setFixedSize(SIZE["control"], SIZE["control"])
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(action)
        return button

    def _show_playing(self, playing: bool) -> None:
        self.play_button.setIcon(self._pause_icon if playing else self._play_icon)
        self.play_button.setToolTip(PAUSE_TIP if playing else PLAY_TIP)

    def _show_edges(self, can_back: bool, can_next: bool) -> None:
        self.back_button.setEnabled(can_back)
        self.next_button.setEnabled(can_next)

    def _on_choice(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        key = item.data(0, KEY_ROLE)
        if key:
            self.open(key)

    def controls(self) -> list[QWidget]:
        return [self.back_button, self.play_button, self.next_button, self.speed_picker,
                self.side_control, self.lab_button]

    def set_controls_enabled(self, on: bool) -> None:
        for widget in (self.back_button, self.play_button, self.next_button, self.speed_picker,
                       self.side_control):
            widget.setEnabled(on)
        if not on:
            self.side_control.hide()
            self.lab_button.hide()

    def set_narrow(self, narrow: bool) -> None:
        self.steps_page.narrow_details.setVisible(narrow)
        if narrow:
            self._mirror(self.step_panel.html())

    def _mirror(self, html: str) -> None:
        if self.steps_page.narrow_details.isVisibleTo(self.steps_page):
            self.steps_page.narrow_details.setHtml(html)

    def item_for(self, key: str) -> QTreeWidgetItem:
        return self.routes_page.item_for(key)

    def badge_state(self, row: int) -> str:
        return self.steps.item(row).data(STATE_ROLE) or "later"

    def open(self, key: str, side: str = "left") -> None:
        self.pause()
        pathway = {p.key: p for p in self.state.atlas.pathways}[key]
        if self.pathway is None:
            self.entered.emit()
        self.set_controls_enabled(True)
        self.pathway, self.index = pathway, 0
        both = pathway.sides == "both"
        self.side_control.setVisible(not both)
        self.timeline = self.state.atlas.timelines.get(key)
        self.time = 0.0
        if self.timeline is not None:
            self.index = self.timeline.step_at(0.0)
        self.timeline_changed.emit(self.timeline)
        self.title.setText(escape(pathway.name))
        self.lab_button.setVisible(key in self.lab_routes)
        self.show_tab.emit("steps")
        with self.hold():
            self.set_side(side)
            self.route_opened.emit()
        self.time_changed.emit(self.time)
        self.setFocus()

    def set_side(self, side: str) -> None:
        self.pause()
        if self.pathway is None:
            return
        atlas = self.state.atlas
        self.side = side
        with QSignalBlocker(self.side_control):
            self.side_control.set_current(side)
        self.lights = lights(atlas, self.pathway, side)
        self.route = frozenset(i for ids in self.lights for i in ids)
        self.text = atlas.pathway_text(self.pathway.key, side)
        self.start.setText(f"Start: {side} {self.pathway.start}" if self.pathway.sides == "one"
                           else f"Start: {self.pathway.start}")
        self.draft.setVisible(self.text is not None and self.text.status == "draft")
        with QSignalBlocker(self.steps):
            self.steps.clear()
            for n, step in enumerate(self.pathway.steps, 1):
                item = QListWidgetItem(self.label(n, step))
                if isinstance(step, Relay):
                    item.setForeground(RELAY_COLOR)
                self.steps.addItem(item)
        with self.hold():
            self.state.set_focus(self.route)
            self.state.set_hidden([i for i in self.state.tract_ids if i not in self.route], True)
            self.state.set_hidden(self.route, False)
            self._go(self.index)

    def label(self, n: int, step) -> str:
        if isinstance(step, Crossing):
            return f"{n} ✕ {step.name}"
        name = step.name if isinstance(step, Relay) else " and ".join(
            self.state.atlas.get(i).name for i in step.structures)
        mark = "✕ " if isinstance(step, Station) and step.crossing else ""
        if self.pathway.sides == "both":
            return f"{n} {mark}{name}"
        return f"{n} {mark}{name} ({side_of(step.side, self.side)})"

    def go(self, index: int, chosen: int | None = None) -> None:
        self.pause()
        self._go(index, chosen)
        if self.timeline is not None and self.pathway is not None:
            time = self.timeline.time_of(self.index)
            if time is not None:
                self._set_time(time)

    def _go(self, index: int, chosen: int | None = None) -> None:
        if self.pathway is None:
            return
        self.index = max(0, min(index, len(self.pathway.steps) - 1))
        ids = self.lights[self.index]
        keep = chosen is not None and bool(set(self.state.geometry_in(chosen)) & set(ids))
        selected = chosen if keep else (ids[0] if ids else None)
        self._applying = True
        try:
            with self.hold():
                self.state.set_hidden(ids, False)
                self.state.select(selected, emphasis=ids)
                self.step_drawn.emit()
                if ids:
                    self.centre_requested.emit()
        finally:
            self._applying = False
        with QSignalBlocker(self.steps):
            self.steps.setCurrentRow(self.index)
            for row in range(self.steps.count()):
                state = "passed" if row < self.index else "current" if row == self.index else "later"
                item = self.steps.item(row)
                if item.data(STATE_ROLE) != state:
                    item.setData(STATE_ROLE, state)
        self.edges_changed.emit(self.index > 0, self.index < len(self.pathway.steps) - 1)
        step = self.pathway.steps[self.index]
        name = self.label(self.index + 1, step).split(" ", 1)[1]
        self.step_panel.show_step(self.index, len(self.pathway.steps), name, self._details_html())
        self.step_changed.emit(f"Step {self.index + 1} of {len(self.pathway.steps)}: {name}")

    def next(self) -> None:
        self.go(self.index + 1)

    def back(self) -> None:
        self.go(self.index - 1)

    def leave(self) -> None:
        self.pause()
        if self.pathway is None:
            return
        self.pathway, self.lights, self.route, self.text = None, [], frozenset(), None
        self.timeline = None
        self.timeline_changed.emit(None)
        self.step_panel.set_idle()
        self.set_controls_enabled(False)
        self.show_tab.emit("routes")
        self.left.emit()

    def _on_row(self, row: int) -> None:
        if row >= 0:
            self.go(row)

    def _on_step_clicked(self, item: QListWidgetItem) -> None:
        if self.steps.row(item) == self.index:
            self.go(self.index)

    def _on_selection(self, structure_id: int | None) -> None:
        if self._applying or self.pathway is None or structure_id is None:
            return
        inside = set(self.state.geometry_in(structure_id))
        found = [n for n, ids in enumerate(self.lights) if inside & set(ids)]
        if found:
            self.go(self.index if self.index in found else found[0], chosen=structure_id)
        else:
            self.pause()

    def _details_html(self) -> str:
        if self.text is None:
            return rich.secondary("No description yet.")
        step = self.text.steps[self.index]
        parts = [f"<p><b>Role</b>: {escape(step.role)}</p>"]
        if self.pathway.texts == "lesion":
            parts.append(f"<p><b>Lesion</b>: {escape(step.lesion)}</p>")
        else:
            parts.append(f"<p><b>Disorders</b>: {escape(step.disorders)}</p>")
            if step.drugs:
                parts.append(f"<p><b>Drugs</b>: {escape(step.drugs)}</p>")
        parts.append(f"{rich.heading('Overview')}<p>{escape(self.text.overview)}</p>")
        parts += references_html(self.text.references)
        return "".join(parts)

    @property
    def playing(self) -> bool:
        return self.timer.isActive()

    def toggle_play(self) -> None:
        self.pause() if self.playing else self.play()

    def play(self) -> None:
        if self.pathway is None:
            return
        last = len(self.pathway.steps) - 1
        if self.timeline is None and self.index == last:
            self._go(0)
        if self.timeline is not None and self.time >= self.timeline.duration:
            self._set_time(0.0)
            self._go(self.timeline.step_at(0.0))
        self._since = 0.0
        self.timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        was = self.timer.isActive()
        self.timer.stop()
        if was:
            self.playing_changed.emit(False)

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def advance(self, seconds: float) -> None:
        if self.pathway is None:
            return
        seconds *= self.speed
        last = len(self.pathway.steps) - 1
        if self.timeline is None:
            self._since += seconds
            if self._since >= STEP_SECONDS:
                self._since = 0.0
                self._go(min(self.index + 1, last))
                if self.index >= last:
                    self.pause()
            return
        timeline = self.timeline
        self._set_time(min(timeline.duration,
                           self.time + seconds * timeline.duration / timeline.play_seconds))
        step = timeline.step_at(self.time)
        if step != self.index:
            self._go(step)
        if self.time >= timeline.duration:
            self.pause()

    def seek(self, time: float) -> None:
        if self.timeline is None:
            return
        self.pause()
        self._set_time(max(0.0, min(time, self.timeline.duration)))
        step = self.timeline.step_at(self.time)
        if step != self.index:
            self._go(step)

    def _set_time(self, time: float) -> None:
        self.time = time
        self.time_changed.emit(time)
