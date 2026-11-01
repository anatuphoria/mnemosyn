from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from cns_atlas.lesions import Lesion, report


class _Change(QUndoCommand):
    def __init__(self, document, before: Lesion, after: Lesion, text: str) -> None:
        super().__init__(text)
        self.document, self.before, self.after = document, before, after

    def redo(self) -> None:
        self.document._apply(self.after)

    def undo(self) -> None:
        self.document._apply(self.before)


class LesionDocument(QObject):
    changed = Signal()

    def __init__(self, atlas, parent=None) -> None:
        super().__init__(parent)
        self.atlas = atlas
        self.lesion = Lesion.empty(atlas)
        self.report = report(atlas, self.lesion)
        self.undo = QUndoStack(self)

    def set_lesion(self, lesion: Lesion, text: str) -> None:
        self.undo.push(_Change(self, self.lesion, lesion, text))

    def clear(self) -> None:
        if not self.lesion.is_empty:
            self.set_lesion(Lesion.empty(self.atlas), "Clear")

    def _apply(self, lesion: Lesion) -> None:
        self.lesion = lesion
        self.report = report(self.atlas, lesion)
        self.changed.emit()
