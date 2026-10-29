from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import SIZE, color
from cns_desktop.design.widgets import SearchField, button_icon

from .labels import plain

MIME = "application/x-mnemosyn-lab-experiment"
KEY = Qt.ItemDataRole.UserRole
TESTS = "Tests"
META_WIDTH = 84
META_FROM = SIZE["panel_right"]
GROUP_ICONS = {"Remove or cut": "scissors", "Drugs": "pill", "Conditions": "heart-pulse",
               "Stressors": "zap", TESTS: "test-tube"}


class ExperimentsPanel(QTreeWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setMaximumSectionSize(META_WIDTH)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setIndentation(12)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.itemDoubleClicked.connect(self._add)
        document.model_changed.connect(self.populate)
        self.populate()

    def populate(self) -> None:
        self.clear()
        document = self.document
        model, atlas = document.model, document.atlas
        groups: dict[str, QTreeWidgetItem] = {}

        def group(name: str) -> QTreeWidgetItem:
            if name not in groups:
                item = QTreeWidgetItem([name])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                heading = font("data")
                heading.setCapitalization(QFont.Capitalization.AllUppercase)
                item.setFont(0, heading)
                item.setForeground(0, color("text2"))
                self.addTopLevelItem(item)
                item.setFirstColumnSpanned(True)
                groups[name] = item
            return groups[name]

        self._items: dict[str, QTreeWidgetItem] = {}
        rows = [(e.group, e.key, e.name, f"experiment.{e.key}.description", e.icon,
                 _meta(e)) for e in model.experiments]
        rows += [(TESTS, t.key, t.name, f"test.{t.key}.description", t.icon, "")
                 for t in model.tests]
        for group_name, key, name, text_key, icon, meta in rows:
            item = QTreeWidgetItem([name, meta])
            item.setData(0, KEY, key)
            item.setIcon(0, button_icon(icon_for(model, key)))
            item.setForeground(1, color("text2"))
            item.setFont(1, font("secondary"))
            found = atlas.lab_text(model.key, text_key)
            item.setToolTip(0, f"{name}\n{found[0]}" if found else name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                          | Qt.ItemFlag.ItemIsDragEnabled)
            group(group_name).addChild(item)
            self._items[key] = item
        self.expandAll()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.setColumnHidden(1, event.size().width() < META_FROM)

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


def icon_for(model, key: str) -> str:
    found = next((e for e in model.experiments if e.key == key), None)
    if found is not None:
        return found.icon or GROUP_ICONS.get(found.group, "flask-conical")
    test = next((t for t in model.tests if t.key == key), None)
    return (test.icon if test is not None and test.icon else GROUP_ICONS[TESTS])


def _meta(experiment) -> str:
    if not experiment.options:
        return ""
    option = experiment.options[0]
    return f"{plain(option.default, 3)} {option.unit}".strip()


class ExperimentsPage(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.panel = ExperimentsPanel(document)
        self.search = SearchField("Find an experiment")
        self.search.textChanged.connect(self.filter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        row = QVBoxLayout()
        row.setContentsMargins(8, 0, 8, 0)
        row.addWidget(self.search)
        layout.addLayout(row)
        layout.addWidget(self.panel, 1)
        document.model_changed.connect(lambda: self.filter(self.search.text()))

    def filter(self, text: str) -> None:
        words = text.strip().lower()
        panel = self.panel
        for n in range(panel.topLevelItemCount()):
            group = panel.topLevelItem(n)
            shown = 0
            for m in range(group.childCount()):
                child = group.child(m)
                hit = not words or words in child.text(0).lower()
                child.setHidden(not hit)
                shown += hit
            group.setHidden(shown == 0)
