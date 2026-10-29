from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

MIME = "application/x-mnemosyn-lab-experiment"
KEY = Qt.ItemDataRole.UserRole
TESTS = "Tests"


class ExperimentsPanel(QTreeWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        model, atlas = document.model, document.atlas
        groups: dict[str, QTreeWidgetItem] = {}

        def group(name: str) -> QTreeWidgetItem:
            if name not in groups:
                item = QTreeWidgetItem([name])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.addTopLevelItem(item)
                groups[name] = item
            return groups[name]

        self._items: dict[str, QTreeWidgetItem] = {}
        rows = [(e.group, e.key, e.name, f"experiment.{e.key}.description")
                for e in model.experiments]
        rows += [(TESTS, t.key, t.name, f"test.{t.key}.description") for t in model.tests]
        for group_name, key, name, text_key in rows:
            item = QTreeWidgetItem([name])
            item.setData(0, KEY, key)
            found = atlas.lab_text(model.key, text_key)
            if found:
                item.setToolTip(0, found[0])
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                          | Qt.ItemFlag.ItemIsDragEnabled)
            group(group_name).addChild(item)
            self._items[key] = item
        self.expandAll()
        self.itemDoubleClicked.connect(self._add)

    def item_for(self, key: str) -> QTreeWidgetItem:
        return self._items[key]

    def _add(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        key = item.data(0, KEY)
        if key:
            self.document.add_block(key, self.document.playhead)

    def mimeTypes(self) -> list[str]:
        return [MIME]

    def mimeData(self, items) -> QMimeData:
        data = QMimeData()
        keys = [item.data(0, KEY) for item in items if item.data(0, KEY)]
        if keys:
            data.setData(MIME, keys[0].encode("utf-8"))
        return data
