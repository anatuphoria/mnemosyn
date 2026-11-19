from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QTextBrowser

STRUCTURE = "structure"
BACK = "back"


class LinkedText(QTextBrowser):
    structure_linked = Signal(int)
    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._on_anchor)

    def claim(self, url: QUrl) -> bool:
        return False

    def _on_anchor(self, url: QUrl) -> None:
        scheme = url.scheme()
        if scheme == STRUCTURE:
            try:
                structure_id = int(url.path())
            except ValueError:
                return
            self.structure_linked.emit(structure_id)
        elif scheme == BACK:
            self.back_requested.emit()
        elif not self.claim(url):
            QDesktopServices.openUrl(url)
