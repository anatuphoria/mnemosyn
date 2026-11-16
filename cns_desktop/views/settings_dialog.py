from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from .. import preferences
from ..design import tokens
from ..design.theme import set_role
from ..design.tokens import GAP
from .welcome import SEEN_KEY

WIDTH = 440
THEME_NAMES = (("dark", "Dark"), ("light", "Light"))
NEXT_START = "The theme changes the next time Mnemosyn starts."
TIMELINE_NAMES = (("compare", "Normal line behind each value"),
                  ("show_guides", "Guide lines where a change starts and ends"),
                  ("show_hover", "Values under the pointer"),
                  ("show_overview", "Whole run bar above the ruler"))
DISCLAIMER_KEY = "disclaimer_hidden"


class SettingsDialog(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.settings = window.settings
        self.setWindowTitle("Settings")
        self.setFixedWidth(WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["wide"], GAP["large"], GAP["wide"], GAP["large"])
        layout.setSpacing(GAP["small"])
        self._appearance(layout)
        self.timeline_boxes: dict[str, QCheckBox] = {}
        if window.lab is not None:
            self._timeline(layout)
        self._start(layout)
        self.close_button = QPushButton("Close")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.close_button)
        layout.addSpacing(GAP["medium"])
        layout.addLayout(row)

    def _heading(self, layout, text: str) -> None:
        if layout.count():
            layout.addSpacing(GAP["medium"])
        label = QLabel(text)
        set_role(label, "heading")
        layout.addWidget(label)

    def _appearance(self, layout) -> None:
        self._heading(layout, "Appearance")
        self.theme = QComboBox()
        for key, name in THEME_NAMES:
            self.theme.addItem(name, key)
        chosen = preferences.stored_theme(self.settings)
        self.theme.setCurrentIndex(self.theme.findData(chosen))
        row = QHBoxLayout()
        row.setSpacing(GAP["small"])
        row.addWidget(QLabel("Theme"))
        row.addWidget(self.theme, 1)
        layout.addLayout(row)
        self.theme_note = QLabel(NEXT_START)
        self.theme_note.setWordWrap(True)
        set_role(self.theme_note, "secondary")
        layout.addWidget(self.theme_note)
        self.theme.currentIndexChanged.connect(self._theme_chosen)
        self._sync_note()

    def _sync_note(self) -> None:
        self.theme_note.setVisible(self.theme.currentData() != tokens.theme())

    def _theme_chosen(self, _index: int) -> None:
        preferences.store_theme(self.settings, self.theme.currentData())
        self._sync_note()
        self.adjustSize()

    def _timeline(self, layout) -> None:
        self._heading(layout, "Lab timeline")
        timeline = self.window_.lab.timeline
        for name, text in TIMELINE_NAMES:
            box = QCheckBox(text)
            box.setChecked(bool(getattr(timeline, name)))
            box.toggled.connect(lambda on, n=name: self._timeline_set(n, on))
            layout.addWidget(box)
            self.timeline_boxes[name] = box

    def _timeline_set(self, name: str, on: bool) -> None:
        timeline = self.window_.lab.timeline
        setattr(timeline, name, on)
        timeline.update()
        preferences.save_timeline(self.settings, timeline)

    def _start(self, layout) -> None:
        self._heading(layout, "When Mnemosyn starts")
        self.disclaimer = QCheckBox("Show the notice about medical use")
        self.welcome = QCheckBox("Show the welcome tour the next time")
        stored = self.settings
        self.disclaimer.setChecked(stored is None
                                   or not stored.value(DISCLAIMER_KEY, False, type=bool))
        self.welcome.setChecked(stored is not None
                                and not stored.value(SEEN_KEY, False, type=bool))
        for box in (self.disclaimer, self.welcome):
            box.setEnabled(stored is not None)
            layout.addWidget(box)
        self.disclaimer.toggled.connect(lambda on: self._store(DISCLAIMER_KEY, not on))
        self.welcome.toggled.connect(lambda on: self._store(SEEN_KEY, not on))

    def _store(self, key: str, value: bool) -> None:
        if self.settings is not None:
            self.settings.setValue(key, value)
