from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QPushButton, QStyle,
                               QStyledItemDelegate, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..design import icons, rich
from ..design.fonts import font
from ..design.theme import set_role
from ..design.tokens import GAP, SIZE, color
from ..design.widgets import SearchField

KEY_ROLE = Qt.ItemDataRole.UserRole
STATE_ROLE = Qt.ItemDataRole.UserRole + 1
GROUP_ICONS = {"Sensory and motor": "route", "Behaviour": "waypoints"}
ROUTE_ICONS = {"visual": "eye", "motor": "activity", "pain": "zap", "touch": "target",
               "papez": "brain", "memory": "brain", "decision": "brain", "basal-ganglia": "network",
               "cerebellar": "network", "stress": "zap", "body-clock": "clock-3",
               "thirst": "droplet", "fear": "heart-pulse", "dopamine": "heart-pulse"}
BADGE = {"passed": ("accent", "text"), "current": ("text", "s0"), "later": ("s3", "text2")}


class RoutesPage(QWidget):
    def __init__(self, pathways, parent=None) -> None:
        super().__init__(parent)
        self.search = SearchField("Find a route")
        self.search.textChanged.connect(self.filter)
        self.choices = QTreeWidget()
        self.choices.setHeaderHidden(True)
        self.choices.setIndentation(SIZE["indent"])
        self.choices.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.choices.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.choices.setIconSize(QSize(SIZE["icon"], SIZE["icon"]))
        self.empty = QLabel("This atlas has no pathways yet.")
        set_role(self.empty, "secondary")
        self.empty.setWordWrap(True)
        self.empty.setVisible(not pathways)
        groups: dict[str, QTreeWidgetItem] = {}
        for pathway in pathways:
            group = groups.get(pathway.group)
            if group is None:
                group = QTreeWidgetItem([pathway.group])
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                heading = font("data")
                heading.setCapitalization(QFont.Capitalization.AllUppercase)
                group.setFont(0, heading)
                group.setForeground(0, color("text2"))
                self.choices.addTopLevelItem(group)
                group.setExpanded(True)
                groups[pathway.group] = group
            item = QTreeWidgetItem([pathway.name])
            item.setData(0, KEY_ROLE, pathway.key)
            item.setToolTip(0, pathway.name)
            name = ROUTE_ICONS.get(pathway.key, GROUP_ICONS.get(pathway.group, "route"))
            item.setIcon(0, icons.icon(name, "text2", SIZE["icon"]))
            group.addChild(item)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, GAP["small"], 0, 0)
        layout.setSpacing(GAP["small"])
        row = QVBoxLayout()
        row.setContentsMargins(GAP["small"], 0, GAP["small"], 0)
        row.addWidget(self.search)
        row.addWidget(self.empty)
        layout.addLayout(row)
        layout.addWidget(self.choices, 1)

    def filter(self, text: str) -> None:
        words = text.strip().lower()
        for n in range(self.choices.topLevelItemCount()):
            group = self.choices.topLevelItem(n)
            shown = 0
            for m in range(group.childCount()):
                child = group.child(m)
                hit = not words or words in child.text(0).lower()
                child.setHidden(not hit)
                shown += hit
            group.setHidden(shown == 0)

    def item_for(self, key: str) -> QTreeWidgetItem:
        for n in range(self.choices.topLevelItemCount()):
            group = self.choices.topLevelItem(n)
            for m in range(group.childCount()):
                if group.child(m).data(0, KEY_ROLE) == key:
                    return group.child(m)
        raise KeyError(key)


class BadgeDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(hint.width() + SIZE["control"], max(hint.height(), SIZE["row"]))

    def paint(self, painter: QPainter, option, index) -> None:
        state = index.data(STATE_ROLE) or "later"
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        number, _, label = text.partition(" ")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if state == "current" or option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, color("s3"))
        size = SIZE["icon"] + GAP["tight"]
        left = option.rect.left() + GAP["small"]
        top = option.rect.top() + GAP["small"] // 2 + 1
        fill, ink = BADGE[state]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color(fill))
        circle = QRectF(left, top, size, size)
        painter.drawEllipse(circle)
        painter.setFont(font("data"))
        painter.setPen(color(ink))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, number)
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(foreground.color() if foreground is not None and state != "later"
                       else color("text3" if state == "later" else "text"))
        painter.setFont(font("body"))
        body = option.rect.adjusted(int(left + size + GAP["small"]) - option.rect.left(), 0,
                                    -GAP["small"], 0)
        painter.drawText(body, Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, label)
        painter.restore()


class StepsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel()
        self.title.setWordWrap(True)
        set_role(self.title, "heading")
        self.start = QLabel()
        self.start.setWordWrap(True)
        set_role(self.start, "secondary")
        self.draft = QLabel(f"{rich.chip('Draft', 'edited')} · not yet reviewed")
        set_role(self.draft, "secondary")
        self.close_button = QPushButton("Close route")
        self.close_button.setToolTip("Close route  Esc")
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.steps = QListWidget()
        self.steps.setWordWrap(True)
        self.steps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.steps.setItemDelegate(BadgeDelegate(self.steps))
        self.steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.narrow_details = QTextBrowser()
        self.narrow_details.setOpenExternalLinks(True)
        self.narrow_details.document().setDefaultStyleSheet(rich.document_css())
        self.narrow_details.hide()
        self.extra = QVBoxLayout()
        self.extra.setContentsMargins(0, 0, 0, 0)
        self.extra.setSpacing(GAP["small"])
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self.title, 1)
        head.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        pad = SIZE["panel_pad"]
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(GAP["small"])
        layout.addLayout(head)
        layout.addWidget(self.start)
        layout.addWidget(self.draft)
        layout.addLayout(self.extra)
        layout.addWidget(self.steps, 1)
        layout.addWidget(self.narrow_details, 1)
