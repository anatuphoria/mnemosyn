from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..state import AppState

ID_ROLE = Qt.ItemDataRole.UserRole


class StructureTree(QWidget):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.filter_box = QLineEdit(placeholderText="Filter structures…  (Ctrl+F)")
        self.filter_box.setClearButtonEnabled(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_box)
        layout.addWidget(self.tree)

        self.items: dict[int, QTreeWidgetItem] = {}
        self._add(self.tree.invisibleRootItem(), state.atlas.structures[0].id)
        self.tree.expandToDepth(3)

        self.tree.currentItemChanged.connect(self._on_current_item)
        self.tree.itemChanged.connect(self._on_item_checked)
        self.filter_box.textChanged.connect(self.apply_filter)
        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(lambda _ids: self._sync_checks())

    def _add(self, parent: QTreeWidgetItem, structure_id: int) -> None:
        item = QTreeWidgetItem(parent, [self.state.atlas.get(structure_id).name])
        item.setData(0, ID_ROLE, structure_id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)
        self.items[structure_id] = item
        for child in self.state.atlas.children(structure_id):
            self._add(item, child)

    def _on_current_item(self, item: QTreeWidgetItem | None, _previous) -> None:
        if item is not None:
            self.state.select(item.data(0, ID_ROLE))

    def _on_item_checked(self, item: QTreeWidgetItem, _column: int) -> None:
        structure_id = item.data(0, ID_ROLE)
        hidden = item.checkState(0) != Qt.CheckState.Checked
        if not self.state.set_hidden(self.state.geometry_in(structure_id), hidden):
            self._sync_checks()

    def _sync_checks(self) -> None:
        with QSignalBlocker(self.tree):
            for structure_id, item in self.items.items():
                ids = self.state.geometry_in(structure_id)
                shown = sum(not self.state.is_hidden(i) for i in ids)
                if shown == len(ids):
                    mark = Qt.CheckState.Checked
                elif shown == 0:
                    mark = Qt.CheckState.Unchecked
                else:
                    mark = Qt.CheckState.PartiallyChecked
                item.setCheckState(0, mark)

    def apply_filter(self, text: str) -> None:
        atlas = self.state.atlas
        if not text.strip():
            for item in self.items.values():
                item.setHidden(False)
            return
        visible: set[int] = set()
        for structure_id in atlas.search(text, limit=None):
            visible.update(atlas.ancestors(structure_id))
            visible.update(s.id for s in atlas.structures[atlas.subtree(structure_id)])
        for structure_id, item in self.items.items():
            item.setHidden(structure_id not in visible)
        self.tree.expandAll()

    def _on_selection_changed(self, structure_id: int | None) -> None:
        item = self.items.get(structure_id) if structure_id is not None else None
        with QSignalBlocker(self.tree):
            self.tree.setCurrentItem(item)
        if item is not None:
            self.tree.scrollToItem(item)
