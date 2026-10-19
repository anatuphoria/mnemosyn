from __future__ import annotations

from contextlib import nullcontext
from html import escape

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QStackedWidget, QStyle, QTextBrowser,
                               QToolButton, QVBoxLayout, QWidget)

from cns_atlas import DISCLAIMER, Crossing, Pathway, Relay, Station, Timeline
from cns_atlas.pathways import PathwayText, lights, side_of

from ..state import AppState
from .info_panel import references_html

NO_PATHWAYS = "This atlas has no pathways yet."
RELAY_COLOR = QColor("#8a8a99")
KEY_ROLE = Qt.ItemDataRole.UserRole
TICK_MS = 50
STEP_SECONDS = 3.0
PLAY_TIP = "Play (Space)"
PAUSE_TIP = "Pause (Space)"
SPEEDS = ((0.5, "½×"), (1.0, "1×"), (2.0, "2×"))


def _column(*widgets) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        if isinstance(widget, QHBoxLayout):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    return page


class PathwayPanel(QWidget):
    entered = Signal()
    left = Signal()
    centre_requested = Signal()
    timeline_changed = Signal(object)
    time_changed = Signal(float)
    playing_changed = Signal(bool)
    step_changed = Signal(str)
    edges_changed = Signal(bool, bool)

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

        self.choices = QListWidget()
        groups = list(dict.fromkeys(p.group for p in state.atlas.pathways))
        for group in groups:
            header = QListWidgetItem(group)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            self.choices.addItem(header)
            for pathway in (p for p in state.atlas.pathways if p.group == group):
                item = QListWidgetItem(pathway.name)
                item.setData(KEY_ROLE, pathway.key)
                self.choices.addItem(item)
        self.empty = QLabel(NO_PATHWAYS)
        self.empty.setVisible(not state.atlas.pathways)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.start = QLabel()
        sides = QHBoxLayout()
        group = QButtonGroup(self)
        self.side_buttons: dict[str, QPushButton] = {}
        for side in ("left", "right"):
            button = QPushButton(side.capitalize())
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, s=side: self.set_side(s))
            group.addButton(button)
            sides.addWidget(button)
            self.side_buttons[side] = button
        self.draft = QLabel("<b>Draft</b>: not yet reviewed.")
        icon = self.style().standardIcon
        self._play_icon = icon(QStyle.StandardPixmap.SP_MediaPlay)
        self._pause_icon = icon(QStyle.StandardPixmap.SP_MediaPause)
        self.back_button = self._control(icon(QStyle.StandardPixmap.SP_MediaSkipBackward),
                                         "Back (Left)", self.back)
        self.play_button = self._control(self._play_icon, PLAY_TIP, self.toggle_play)
        self.next_button = self._control(icon(QStyle.StandardPixmap.SP_MediaSkipForward),
                                         "Next (Right)", self.next)
        self.speed_picker = QComboBox()
        for value, text in SPEEDS:
            self.speed_picker.addItem(text, value)
        self.speed_picker.setCurrentIndex(1)
        self.speed_picker.setToolTip("Speed")
        self.speed_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_picker.currentIndexChanged.connect(
            lambda i: self.set_speed(float(self.speed_picker.itemData(i))))
        controls = QHBoxLayout()
        for widget in (self.back_button, self.play_button, self.next_button, self.speed_picker):
            controls.addWidget(widget)
        controls.addStretch(1)
        self.step_label = QLabel()
        self.step_label.setWordWrap(True)
        self.playing_changed.connect(self._show_playing)
        self.edges_changed.connect(self._show_edges)
        self.step_changed.connect(self.step_label.setText)
        self.steps = QListWidget()
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        self.leave_button = QPushButton("Leave pathway (Esc)")
        self.timer = QTimer(self, interval=TICK_MS, timeout=lambda: self.advance(TICK_MS / 1000))
        for widget in (*self.side_buttons.values(), self.steps, self.details, self.leave_button):
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.pages = QStackedWidget()
        self.pages.addWidget(_column(self.choices, self.empty))
        self.pages.addWidget(_column(self.title, self.start, sides, self.draft, controls,
                                     self.step_label, self.steps, self.details,
                                     self.leave_button))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pages)

        self.choices.itemClicked.connect(self._on_choice)
        self.choices.itemActivated.connect(self._on_choice)
        self.steps.currentRowChanged.connect(self._on_row)
        self.steps.itemClicked.connect(self._on_step_clicked)
        self.leave_button.clicked.connect(self.leave)
        state.selection_changed.connect(self._on_selection)

    def _control(self, icon, tip: str, action) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
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

    def _on_choice(self, item: QListWidgetItem) -> None:
        key = item.data(KEY_ROLE)
        if key:
            self.open(key)

    def open(self, key: str, side: str = "left") -> None:
        self.pause()
        pathway = {p.key: p for p in self.state.atlas.pathways}[key]
        if self.pathway is None:
            self.entered.emit()
        self.pathway, self.index = pathway, 0
        both = pathway.sides == "both"
        for button in self.side_buttons.values():
            button.setVisible(not both)
        self.timeline = self.state.atlas.timelines.get(key)
        self.time = 0.0
        if self.timeline is not None:
            self.index = self.timeline.step_at(0.0)
        self.timeline_changed.emit(self.timeline)
        self.title.setText(f"<b>{escape(pathway.name)}</b>")
        self.pages.setCurrentIndex(1)
        with self.hold():
            self.set_side(side)
        self.time_changed.emit(self.time)
        self.setFocus()

    def set_side(self, side: str) -> None:
        self.pause()
        if self.pathway is None:
            return
        atlas = self.state.atlas
        self.side = side
        self.side_buttons[side].setChecked(True)
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
                if ids:
                    self.centre_requested.emit()
        finally:
            self._applying = False
        with QSignalBlocker(self.steps):
            self.steps.setCurrentRow(self.index)
        self.edges_changed.emit(self.index > 0, self.index < len(self.pathway.steps) - 1)
        self.details.setHtml(self._details_html())
        step = self.pathway.steps[self.index]
        name = self.label(self.index + 1, step).split(" ", 1)[1]
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
        self.pages.setCurrentIndex(0)
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
        parts = [f"<h3>{escape(self.steps.item(self.index).text())}</h3>"]
        if self.text is None:
            parts.append("<p><i>No description yet.</i></p>")
        else:
            step = self.text.steps[self.index]
            parts.append(f"<p><b>Role</b>: {escape(step.role)}</p>")
            if self.pathway.texts == "lesion":
                parts.append(f"<p><b>Lesion</b>: {escape(step.lesion)}</p>")
            else:
                parts.append(f"<p><b>Disorders</b>: {escape(step.disorders)}</p>")
                if step.drugs:
                    parts.append(f"<p><b>Drugs</b>: {escape(step.drugs)}</p>")
            parts.append(f"<h4>Overview</h4><p>{escape(self.text.overview)}</p>")
            parts += references_html(self.text.references)
        parts.append(f"<p style='color:#c55'><small>{escape(DISCLAIMER)}</small></p>")
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

    def keyPressEvent(self, event) -> None:
        if self.pathway is not None and event.key() == Qt.Key.Key_Right:
            self.next()
        elif self.pathway is not None and event.key() == Qt.Key.Key_Left:
            self.back()
        elif self.pathway is not None and event.key() == Qt.Key.Key_Space:
            self.toggle_play()
        else:
            super().keyPressEvent(event)
