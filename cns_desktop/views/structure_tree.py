from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker
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

        self.items: dict[str, QTreeWidgetItem] = {}
        for system, structures in state.atlas.by_system().items():
            group = QTreeWidgetItem(self.tree, [f"{system}  ({len(structures)})"])
            for s in structures:
                item = QTreeWidgetItem(group, [s.name])
                item.setData(0, ID_ROLE, s.id)
                item.setCheckState(0, Qt.CheckState.Checked)
                self.items[s.id] = item
        self.tree.expandAll()

        self.tree.currentItemChanged.connect(self._on_current_item)
        self.tree.itemChanged.connect(self._on_item_checked)
        self.filter_box.textChanged.connect(self.apply_filter)
        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(self._on_visibility_changed)

    def _on_current_item(self, item: QTreeWidgetItem | None, _prev) -> None:
        sid = item.data(0, ID_ROLE) if item else None
        if sid:
            self.state.select(sid)

    def _on_item_checked(self, item: QTreeWidgetItem, _column: int) -> None:
        sid = item.data(0, ID_ROLE)
        if sid:
            hidden = item.checkState(0) != Qt.CheckState.Checked
            self.state.set_hidden([sid], hidden)

    def apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            group_match = needle in group.text(0).lower()
            any_visible = False
            for j in range(group.childCount()):
                child = group.child(j)
                show = not needle or group_match or needle in child.text(0).lower()
                child.setHidden(not show)
                any_visible |= show
            group.setHidden(not any_visible)

    def _on_selection_changed(self, sid: str | None) -> None:
        item = self.items.get(sid) if sid else None
        with QSignalBlocker(self.tree):
            self.tree.setCurrentItem(item)
        if item is not None:
            self.tree.scrollToItem(item)

    def _on_visibility_changed(self, ids: frozenset[str]) -> None:
        with QSignalBlocker(self.tree):
            for sid in ids:
                hidden = self.state.is_hidden(sid)
                self.items[sid].setCheckState(
                    0, Qt.CheckState.Unchecked if hidden else Qt.CheckState.Checked)
