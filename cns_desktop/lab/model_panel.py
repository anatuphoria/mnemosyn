from __future__ import annotations

import math

from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QToolButton, QVBoxLayout, QWidget)

EDITED = "#d9a441"


def short_source(references) -> str:
    parts = []
    for ref in references:
        authors = [a.strip() for a in ref.authors.split(",") if a.strip()]
        first = authors[0] if authors else ref.title
        parts.append(f"{first}{' et al.' if len(authors) > 1 else ''} ({ref.year})")
    return "; ".join(parts)


def decimals_for(*numbers: float) -> int:
    smallest = min((abs(n) for n in numbers if n), default=1.0)
    return max(2, min(8, 3 - math.floor(math.log10(smallest))))


class ModelPanel(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Value", "Setting", ""])
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.reset_all = QPushButton("Reset all")
        self.reset_all.clicked.connect(document.reset_values)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.reset_all)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table, 1)
        layout.addLayout(row)
        document.changed.connect(self.refresh)
        document.model_changed.connect(self.populate)
        self.populate()

    def populate(self) -> None:
        document = self.document
        model, atlas = document.model, document.atlas
        self.table.setRowCount(0)
        self.table.setRowCount(len(model.parameters))
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._resets: dict[str, QToolButton] = {}
        self._labels: dict[str, QLabel] = {}
        self._texts: dict[str, tuple[str, str, str]] = {}
        references = atlas.references
        for row, parameter in enumerate(model.parameters):
            meaning = atlas.lab_text(model.key, f"parameter.{parameter.key}.meaning")
            source = short_source([references[k] for k in parameter.refs if k in references])
            self._texts[parameter.key] = (parameter.name, meaning[0] if meaning else "", source)
            label = QLabel(parameter.name)
            label.setToolTip("\n".join(t for t in self._texts[parameter.key][1:] if t))
            self.table.setCellWidget(row, 0, label)
            spin = QDoubleSpinBox()
            spin.setDecimals(decimals_for(parameter.value, parameter.low, parameter.high))
            spin.setRange(parameter.low, parameter.high)
            spin.setSingleStep((parameter.high - parameter.low) / 100 or 1.0)
            spin.setSuffix(f" {parameter.unit}")
            spin.setValue(parameter.value)
            spin.editingFinished.connect(lambda k=parameter.key: self._edited(k))
            self.table.setCellWidget(row, 1, spin)
            reset = QToolButton(text="Reset")
            reset.setToolTip(f"Back to the normal value, {parameter.value:g} {parameter.unit}")
            reset.clicked.connect(lambda _=False, k=parameter.key: document.reset_value(k))
            self.table.setCellWidget(row, 2, reset)
            self._spins[parameter.key] = spin
            self._resets[parameter.key] = reset
            self._labels[parameter.key] = label
        self.refresh()

    def spin(self, key: str) -> QDoubleSpinBox:
        return self._spins[key]

    def reset_button(self, key: str) -> QToolButton:
        return self._resets[key]

    def row_text(self, key: str) -> tuple[str, str, str]:
        return self._texts[key]

    def is_marked(self, key: str) -> bool:
        return key in self.document.experiment.value_map

    def _edited(self, key: str) -> None:
        value = self._spins[key].value()
        current = self.document.experiment.value_map.get(key,
                                                         self.document.model.parameter(key).value)
        if abs(value - current) > 1e-12:
            self.document.set_value(key, value)

    def refresh(self) -> None:
        edited = self.document.experiment.value_map
        for parameter in self.document.model.parameters:
            spin = self._spins[parameter.key]
            spin.blockSignals(True)
            spin.setValue(edited.get(parameter.key, parameter.value))
            spin.blockSignals(False)
            marked = parameter.key in edited
            style = f"color: {EDITED};" if marked else ""
            spin.setStyleSheet(style)
            self._labels[parameter.key].setStyleSheet(style)
            self._resets[parameter.key].setEnabled(marked)
        self.reset_all.setEnabled(bool(edited))
