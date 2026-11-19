from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QRect, QSignalBlocker, QSize, Qt
from PySide6.QtWidgets import (QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..design.tokens import GAP, SIZE
from ..design.widgets import SearchField
from ..state import AppState

ID_ROLE = Qt.ItemDataRole.UserRole
SHORT_ROLE = Qt.ItemDataRole.UserRole + 1
SIDE = re.compile(r" \((?:left|right)\)$")
MEASURE_LIMIT = 1 << 16


def relative_name(name: str, parent: str | None) -> str:
    if not parent:
        return name
    base = SIDE.sub("", parent)
    if not name.startswith(base) or name[len(base):len(base) + 1] not in (" ", ","):
        return name
    rest = name[len(base):].lstrip(", ")
    if rest.startswith("(") and rest.endswith(")") and rest.count("(") == 1:
        rest = rest[1:-1]
    return rest[:1].upper() + rest[1:] if rest else name


class NameDelegate(QStyledItemDelegate):
    def _text_width(self, option, index) -> int:
        view = self.parent()
        depth, parent = 0, index.parent()
        while parent.isValid():
            depth, parent = depth + 1, parent.parent()
        left = view.indentation() * (depth + (1 if view.rootIsDecorated() else 0))
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        item.rect = QRect(0, 0, max(view.viewport().width() - left, 1),
                          max(item.rect.height(), item.fontMetrics.height()))
        style = view.style()
        text = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, item, view)
        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, item, view)
        return max(text.width() - 2 * margin - 2, 1)

    def sizeHint(self, option, index) -> QSize:
        hint = super().sizeHint(option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        metrics = option.fontMetrics
        box = QRect(0, 0, self._text_width(option, index), MEASURE_LIMIT)
        lines = metrics.boundingRect(box, Qt.TextFlag.TextWordWrap, text).height()
        return QSize(hint.width(), hint.height() + max(0, lines - metrics.height()))

    def paint(self, painter, option, index) -> None:
        view = QStyleOptionViewItem(option)
        self.initStyleOption(view, index)
        view.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        widget = option.widget
        style = widget.style() if widget is not None else None
        if style is None:
            super().paint(painter, option, index)
            return
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, view, painter, widget)


class StructureTree(QWidget):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.filter_box = SearchField("Find a structure  Ctrl+F")
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(SIZE["indent"])
        self.tree.setItemDelegate(NameDelegate(self.tree))
        self.tree.setWordWrap(True)
        self._width = 0
        self.tree.viewport().installEventFilter(self)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, GAP["small"], 0, 0)
        layout.setSpacing(GAP["small"])
        search = QVBoxLayout()
        search.setContentsMargins(GAP["small"], 0, GAP["small"], 0)
        search.addWidget(self.filter_box)
        layout.addLayout(search)
        layout.addWidget(self.tree)

        self.items: dict[int, QTreeWidgetItem] = {}
        self._geometry: dict[int, frozenset[int]] = {}
        self._add(self.tree.invisibleRootItem(), state.atlas.structures[0].id)
        self.tree.expandToDepth(3)
        self._sync_checks()

        self.tree.currentItemChanged.connect(self._on_current_item)
        self.tree.itemChanged.connect(self._on_item_checked)
        self.filter_box.textChanged.connect(self.apply_filter)
        state.selection_changed.connect(self._on_selection_changed)
        state.visibility_changed.connect(lambda ids: self._sync_checks(ids))

    def _add(self, parent: QTreeWidgetItem, structure_id: int) -> None:
        name = self.state.atlas.get(structure_id).name
        above = parent.data(0, Qt.ItemDataRole.ToolTipRole) if parent is not None else None
        short = relative_name(name, above)
        item = QTreeWidgetItem(parent, [short])
        item.setToolTip(0, name)
        item.setData(0, SHORT_ROLE, short)
        item.setData(0, ID_ROLE, structure_id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)
        self.items[structure_id] = item
        for child in self.state.atlas.children(structure_id):
            if not self._territories_only(child):
                self._add(item, child)

    def _territories_only(self, structure_id: int) -> bool:
        atlas = self.state.atlas
        below = atlas.structures[atlas.subtree(structure_id)]
        leaves = [s for s in below if not atlas.children(s.id)]
        return bool(leaves) and all(s.kind == "territory" for s in leaves)

    def _on_current_item(self, item: QTreeWidgetItem | None, _previous) -> None:
        if item is not None:
            self.state.select(item.data(0, ID_ROLE))

    def _on_item_checked(self, item: QTreeWidgetItem, _column: int) -> None:
        structure_id = item.data(0, ID_ROLE)
        ids = self._geometry_of(structure_id)
        hidden_now = len(ids & self.state.hidden_ids)
        was_partial = 0 < hidden_now < len(ids)
        hidden = was_partial or item.checkState(0) != Qt.CheckState.Checked
        if not self.state.set_hidden(ids, hidden):
            self._sync_checks()

    def _geometry_of(self, structure_id: int) -> frozenset[int]:
        if structure_id not in self._geometry:
            self._geometry[structure_id] = frozenset(self.state.geometry_in(structure_id))
        return self._geometry[structure_id]

    def _sync_checks(self, changed=None) -> None:
        if changed is None:
            targets = list(self.items)
        else:
            atlas = self.state.atlas
            targets = {a for i in changed for a in (*atlas.ancestors(i), i) if a in self.items}
        with QSignalBlocker(self.tree):
            hidden = self.state.hidden_ids
            for structure_id in targets:
                item = self.items[structure_id]
                ids = self._geometry_of(structure_id)
                shown = len(ids) - len(ids & hidden)
                if shown == len(ids):
                    mark = Qt.CheckState.Checked
                elif shown == 0:
                    mark = Qt.CheckState.Unchecked
                else:
                    mark = Qt.CheckState.PartiallyChecked
                item.setCheckState(0, mark)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.tree.viewport() and event.type() == QEvent.Type.Resize:
            width = event.size().width()
            if width != self._width:
                self._width = width
                self.tree.doItemsLayout()
        return super().eventFilter(watched, event)

    def apply_filter(self, text: str) -> None:
        atlas = self.state.atlas
        searching = bool(text.strip())
        for item in self.items.values():
            item.setText(0, item.toolTip(0) if searching else item.data(0, SHORT_ROLE))
        if not searching:
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
