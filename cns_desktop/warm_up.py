from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal


class WarmUp(QObject):
    finished = Signal()

    def __init__(self, jobs: list[Callable[[], None]], parent: QObject) -> None:
        super().__init__(parent)
        self._jobs = list(jobs)
        self.done = False

    def start(self) -> None:
        QTimer.singleShot(0, self, self._next)

    def stop(self) -> None:
        self._jobs.clear()

    def _next(self) -> None:
        if not self._jobs:
            if not self.done and not self._stopped():
                self.done = True
                self.finished.emit()
            return
        self._jobs.pop(0)()
        QTimer.singleShot(0, self, self._next)

    def _stopped(self) -> bool:
        parent = self.parent()
        return parent is None or not parent.isVisible()
