from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from cns_lab.checks import read_test
from cns_lab.experiment import FROM_A_TIME, PRESENT
from cns_lab.why import phrase

from .model_panel import short_source
from .why_panel import DRAFT

RULE_WORDS = {"below": "below", "at least": "at least", "suppressed by": "suppressed by at least"}
MODES = (("Present from the start", PRESENT), ("From a time", FROM_A_TIME))


class _NoteBox(QPlainTextEdit):
    left = Signal()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.left.emit()


class Inspector(QWidget):
    show_in_atlas = Signal(str)

    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.body)
        layout.addStretch(1)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._start: QDoubleSpinBox | None = None
        self._mode: QComboBox | None = None
        self._labels: list[QLabel] = []
        self._title: QLineEdit | None = None
        self._note_box: QPlainTextEdit | None = None
        document.selection_changed.connect(lambda _s: self.rebuild())
        document.changed.connect(self.rebuild)
        document.playhead_moved.connect(
            lambda _t: self.rebuild() if document.selection is not None else None)
        self.rebuild()

    def option_spin(self, key: str) -> QDoubleSpinBox:
        return self._spins[key]

    def start_spin(self) -> QDoubleSpinBox:
        return self._start

    def mode_box(self) -> QComboBox:
        return self._mode

    def title_box(self) -> QLineEdit:
        return self._title

    def note_box(self) -> QPlainTextEdit:
        return self._note_box

    def text(self) -> str:
        return "\n".join(label.text() for label in self._labels)

    def _clear(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self._spins, self._start, self._mode, self._labels = {}, None, None, []
        self._title, self._note_box = None, None

    def _note(self, text: str, bold: bool = False) -> QLabel:
        label = QLabel(f"<b>{escape(text)}</b>" if bold else escape(text))
        label.setWordWrap(True)
        self.form.addRow(label)
        self._labels.append(label)
        return label

    def _sources(self, keys) -> None:
        references = self.document.atlas.references
        found = [references[k] for k in keys if k in references]
        if found:
            self._note(f"Sources: {short_source(found)}")

    def _text(self, key: str) -> str:
        found = self.document.atlas.lab_text(self.document.model.key, key)
        return found[0] if found else ""

    def rebuild(self) -> None:
        self._clear()
        selection = self.document.selection
        if selection is None:
            self._experiment()
            return
        kind, key = selection
        if kind == "block" and key < len(self.document.experiment.blocks):
            self._block(key)
        elif kind == "part":
            self._part(key)
        elif kind == "link":
            self._link(key)
        elif kind == "value":
            self._value(key)
        self._note(DRAFT)

    def _experiment(self) -> None:
        doc = self.document
        self._note("This experiment", bold=True)
        title = QLineEdit(doc.experiment.title)
        title.setPlaceholderText("A title for this experiment")
        title.editingFinished.connect(lambda: doc.set_title(title.text())
                                      if title.text() != doc.experiment.title else None)
        self.form.addRow("Title", title)
        note = _NoteBox(doc.experiment.note)
        note.setPlaceholderText("Notes for yourself or a student")
        note.setMaximumHeight(90)
        note.left.connect(lambda: doc.set_note(note.toPlainText())
                          if note.toPlainText() != doc.experiment.note else None)
        self.form.addRow("Note", note)
        self._title, self._note_box = title, note
        self._note("Select a change, a part, a link or a value to see it here.")

    def _hours(self, minutes: float, low: float, high: float, slot) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setRange(low / 60.0, high / 60.0)
        spin.setSuffix(" h")
        spin.setValue(minutes / 60.0)
        spin.editingFinished.connect(lambda: slot(spin.value() * 60.0))
        return spin

    def _block(self, index: int) -> None:
        doc = self.document
        block = doc.experiment.blocks[index]
        experiment = next((e for e in doc.model.experiments if e.key == block.experiment), None)
        self._note(doc.name_of(block.experiment), bold=True)
        prefix = "experiment" if experiment else "test"
        self._note(self._text(f"{prefix}.{block.experiment}.description"))
        if experiment and experiment.mode == PRESENT:
            box = QComboBox()
            for label, _mode in MODES:
                box.addItem(label)
            box.setCurrentIndex(0 if block.present else 1)
            box.currentIndexChanged.connect(lambda i: doc.set_mode(index, MODES[i][1]))
            self.form.addRow("Starts", box)
            self._mode = box
        if not block.present:
            self._start = self._hours(block.start, 0.0, doc.experiment.length - 1,
                                      lambda m: doc.move_block(index, m))
            self.form.addRow("Starts at", self._start)
            if block.length is not None:
                self.form.addRow("Lasts", self._hours(block.length, 1.0, doc.experiment.length,
                                                      lambda m: doc.stretch_block(index, m)))
        if experiment:
            for option in experiment.options:
                spin = QDoubleSpinBox()
                spin.setDecimals(3)
                spin.setRange(option.low, option.high)
                spin.setSuffix(f" {option.unit}")
                spin.setValue(block.option_map.get(option.key, option.default))
                spin.editingFinished.connect(
                    lambda k=option.key, s=spin: self._option(index, k, s.value()))
                self.form.addRow(option.name, spin)
                self._spins[option.key] = spin
        else:
            self._test_result(block)

    def _option(self, index: int, key: str, value: float) -> None:
        block = self.document.experiment.blocks[index]
        if abs(block.option_map.get(key, value) - value) > 1e-12:
            self.document.set_option(index, key, value)

    def _test_result(self, block) -> None:
        doc = self.document
        if doc.run is None:
            return
        if block.start + max(r.after for r in next(
                t for t in doc.model.tests if t.key == block.experiment).readings) > (
                doc.experiment.length):
            self._note("The run ends before the test is read.")
            return
        result = read_test(doc.simulator, doc.run, block)
        word = "Normal" if result.normal else "Abnormal"
        rule = next(t.rule for t in doc.model.tests if t.key == block.experiment)
        if result.unit == "fraction":
            text = (f"{word}: suppressed by {result.value:.0%}, "
                    f"{RULE_WORDS[rule]} {result.cutoff:.0%}")
        else:
            text = (f"{word}: {result.value:.3g} {result.unit}, {RULE_WORDS[rule]} "
                    f"{result.cutoff:g} {result.unit}")
        self._note(text, bold=True)
        self._note(self._text(f"test.{block.experiment}.{'normal' if result.normal else 'abnormal'}"))

    def _value_line(self, key: str) -> None:
        doc = self.document
        value = doc.simulator.values[key]
        if doc.run is None:
            return
        shown = doc.run.display(key, doc.playhead)
        line = f"{value.name}: {shown:.3g} {value.display_unit}"
        if value.other_unit:
            line += f" ({shown * value.other_scale:.3g} {value.other_unit})"
        if value.normal:
            line += f", normal {value.normal[0]:g} to {value.normal[1]:g}"
        self._note(line)
        if value.relative:
            self._note(self._text(f"value.{key}.note"))
        self._sources(value.refs)

    def _part(self, key: str) -> None:
        part = self.document.model.part(key)
        self._note(part.name, bold=True)
        for value in part.values:
            self._value_line(value)
        if part.structure is not None and part.structure in self.document.atlas:
            button = QPushButton("Show in the atlas")
            button.clicked.connect(lambda: self.show_in_atlas.emit(key))
            self.form.addRow(button)

    def _link(self, key: str) -> None:
        doc = self.document
        prefix = "effect" if any(e.key == key for e in doc.model.effects) else "term"
        self._note(self._text(f"{prefix}.{key}"), bold=True)
        if doc.run is not None and doc.normal is not None:
            mine = doc.run.factor(key, doc.playhead)
            theirs = doc.normal.factor(key, doc.playhead)
            ratio = mine / theirs if abs(theirs) > 1e-12 else (1.0 if abs(mine) < 1e-12 else
                                                               float("inf"))
            self._note(f"Right now it is {ratio:.3g} times normal: its strength "
                       f"{phrase(None, ratio)}.")

    def _value(self, key: str) -> None:
        self._note(self.document.simulator.values[key].name, bold=True)
        self._value_line(key)
