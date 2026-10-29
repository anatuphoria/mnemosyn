from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from cns_atlas import Atlas
from cns_lab.engine import Run, SettleError, Simulator
from cns_lab.experiment import FROM_A_TIME, PRESENT, Block, Experiment
from cns_lab.solver import SolverError

DAY = 1440.0
WEEKS = 4 * 7 * DAY
MIN_LENGTH = 1.0


class _Change(QUndoCommand):
    def __init__(self, document: LabDocument, before: Experiment, after: Experiment,
                 text: str) -> None:
        super().__init__(text)
        self.document, self.before, self.after = document, before, after

    def redo(self) -> None:
        self.document._set(self.after)

    def undo(self) -> None:
        self.document._set(self.before)


class LabDocument(QObject):
    changed = Signal()
    playhead_moved = Signal(float)
    selection_changed = Signal(object)
    wants_longer = Signal(float)

    def __init__(self, atlas: Atlas, model_key: str, length: float = DAY) -> None:
        super().__init__()
        self.atlas = atlas
        self.model = atlas.models[model_key]
        self.simulator = Simulator(self.model)
        self.undo = QUndoStack(self)
        self.experiment = self._blank(length)
        self.run: Run | None = None
        self.normal: Run | None = None
        self.snapshot: Run | None = None
        self.error = ""
        self.playhead = 0.0
        self.selection = None
        self.path: Path | None = None
        self._experiments = {e.key: e for e in self.model.experiments}
        self._tests = {t.key: t for t in self.model.tests}
        self._recompute()

    def _blank(self, length: float) -> Experiment:
        return Experiment(self.model.key, self.model.version, length, self.model.start_clock)

    def name_of(self, key: str) -> str:
        found = self._experiments.get(key) or self._tests.get(key)
        return found.name if found else key

    def _recompute(self) -> None:
        try:
            self.run = self.simulator.run(self.experiment)
            self.normal = self.simulator.normal(self.experiment.length,
                                                self.experiment.start_clock)
            self.error = ""
        except (SettleError, SolverError) as exc:
            self.run = None
            self.error = str(exc)

    def _set(self, experiment: Experiment) -> None:
        self.experiment = experiment
        if self.selection and self.selection[0] == "block" and (
                self.selection[1] >= len(experiment.blocks)):
            self.selection = None
            self.selection_changed.emit(None)
        self._recompute()
        if self.playhead > experiment.length:
            self.set_playhead(experiment.length)
        self.changed.emit()

    def apply(self, experiment: Experiment, text: str) -> None:
        if experiment != self.experiment:
            self.undo.push(_Change(self, self.experiment, experiment, text))

    def _fit(self, block: Block, length: float) -> Block:
        start = min(max(block.start, 0.0), length - 1)
        size = block.length
        if size is not None:
            size = min(max(size, MIN_LENGTH), length - start)
        return Block(block.experiment, start, size, block.options, block.mode)

    def _blocks(self, blocks) -> tuple[Block, ...]:
        return tuple(self._fit(b, self.experiment.length) for b in blocks)

    def add_block(self, key: str, start: float) -> int:
        experiment = self._experiments.get(key)
        if experiment is None and key not in self._tests:
            raise KeyError(key)
        options = tuple((o.key, o.default) for o in experiment.options) if experiment else ()
        mode = experiment.mode if experiment else FROM_A_TIME
        block = Block(key, 0.0 if mode == PRESENT else start,
                      experiment.length if experiment else None, options, mode)
        blocks = (*self.experiment.blocks, block)
        self.apply(self.experiment.replace(blocks=self._blocks(blocks)),
                   f"Add {self.name_of(key)}")
        if experiment is not None and experiment.weeks and self.experiment.length < WEEKS:
            self.wants_longer.emit(WEEKS)
        return len(self.experiment.blocks) - 1

    def _edit_block(self, index: int, text: str, **changes) -> None:
        blocks = list(self.experiment.blocks)
        old = blocks[index]
        values = {"experiment": old.experiment, "start": old.start, "length": old.length,
                  "options": old.options, "mode": old.mode, **changes}
        blocks[index] = Block(**values)
        self.apply(self.experiment.replace(blocks=self._blocks(blocks)), text)

    def move_block(self, index: int, start: float) -> None:
        block = self.experiment.blocks[index]
        self._edit_block(index, f"Move {self.name_of(block.experiment)}", start=float(start))

    def stretch_block(self, index: int, length: float) -> None:
        block = self.experiment.blocks[index]
        if block.length is None:
            return
        self._edit_block(index, f"Stretch {self.name_of(block.experiment)}",
                         length=float(length))

    def set_option(self, index: int, key: str, value: float) -> None:
        block = self.experiment.blocks[index]
        option = next(o for o in self._experiments[block.experiment].options if o.key == key)
        value = min(max(float(value), option.low), option.high)
        options = tuple((k, value if k == key else v) for k, v in block.options)
        self._edit_block(index, f"Change {option.name.lower()} of "
                                f"{self.name_of(block.experiment)}", options=options)

    def set_mode(self, index: int, mode: str) -> None:
        block = self.experiment.blocks[index]
        experiment = self._experiments.get(block.experiment)
        if mode not in (PRESENT, FROM_A_TIME) or (mode == PRESENT and not (
                experiment and experiment.mode == PRESENT)):
            return
        self._edit_block(index, f"Change when {self.name_of(block.experiment)} starts",
                         mode=mode)

    def delete_block(self, index: int) -> None:
        blocks = list(self.experiment.blocks)
        block = blocks.pop(index)
        if self.selection == ("block", index):
            self.selection = None
            self.selection_changed.emit(None)
        self.apply(self.experiment.replace(blocks=tuple(blocks)),
                   f"Delete {self.name_of(block.experiment)}")

    def set_value(self, key: str, value: float) -> None:
        parameter = self.model.parameter(key)
        value = min(max(float(value), parameter.low), parameter.high)
        values = dict(self.experiment.values)
        if value == parameter.value:
            values.pop(key, None)
        else:
            values[key] = value
        self.apply(self.experiment.replace(values=tuple(values.items())),
                   f"Change {parameter.name.lower()}")

    def reset_value(self, key: str) -> None:
        values = tuple((k, v) for k, v in self.experiment.values if k != key)
        self.apply(self.experiment.replace(values=values),
                   f"Reset {self.model.parameter(key).name.lower()}")

    def reset_values(self) -> None:
        self.apply(self.experiment.replace(values=()), "Reset every value")

    def set_length(self, minutes: float) -> None:
        minutes = max(float(minutes), 60.0)
        experiment = self.experiment.replace(length=minutes)
        blocks = tuple(self._fit(b, minutes) for b in experiment.blocks)
        self.apply(experiment.replace(blocks=blocks), "Change the run length")

    def set_playhead(self, t: float) -> None:
        t = min(max(float(t), 0.0), self.experiment.length)
        if t != self.playhead:
            self.playhead = t
            self.playhead_moved.emit(t)

    def select(self, selection) -> None:
        if selection != self.selection:
            self.selection = selection
            self.selection_changed.emit(selection)

    def take_snapshot(self) -> None:
        self.snapshot = self.run
        self.changed.emit()

    def clear_snapshot(self) -> None:
        self.snapshot = None
        self.changed.emit()

    def load(self, experiment: Experiment, path: Path | None) -> None:
        self.undo.clear()
        self.path = path
        self.snapshot = None
        self.selection = None
        self._set(experiment)
        self.undo.setClean()

    def new(self) -> None:
        self.load(self._blank(DAY), None)

    def is_modified(self) -> bool:
        return not self.undo.isClean()
