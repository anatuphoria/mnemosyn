from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QMenu)

CELL_X, CELL_Y = 180.0, 110.0
BOX_W, BOX_H = 150.0, 56.0
INK = QColor("#d8d8e0")
HOLD = QColor("#6fa0ff")
REMOVED = QColor("#d9a441")
BOX_FILL = QColor("#1a1a23")
BORDER = QColor("#3a3a48")
ZERO = 1e-9


class _Arrow(QGraphicsLineItem):
    def shape(self) -> QPainterPath:
        path = QPainterPath(self.line().p1())
        path.lineTo(self.line().p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(14)
        return stroker.createStroke(path)


class CircuitView(QGraphicsView):
    show_in_atlas = Signal(str)
    show_chart = Signal(str)

    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor("#101016")))
        self.setRenderHint(self.renderHints().Antialiasing)
        self.part_items: dict[str, QGraphicsRectItem] = {}
        self.part_texts: dict[str, QGraphicsSimpleTextItem] = {}
        self.arrow_items: dict[str, QGraphicsLineItem] = {}
        model = document.model
        for part in model.parts:
            rect = QGraphicsRectItem(QRectF(part.x * CELL_X, part.y * CELL_Y, BOX_W, BOX_H))
            rect.setBrush(QBrush(BOX_FILL))
            rect.setData(0, ("part", part.key))
            text = QGraphicsSimpleTextItem(rect)
            text.setBrush(QBrush(INK))
            text.setPos(part.x * CELL_X + 10, part.y * CELL_Y + 8)
            self.scene().addItem(rect)
            self.part_items[part.key] = rect
            self.part_texts[part.key] = text
        for factor in (*model.effects, *model.terms):
            if factor.arrow is None or factor.arrow[0] == factor.arrow[1]:
                continue
            start = self.part_items[factor.arrow[0]].rect().center()
            end = self.part_items[factor.arrow[1]].rect().center()
            line = _Arrow(QLineF(start, end))
            line.setData(0, ("link", factor.key))
            line.setZValue(-1)
            self.scene().addItem(line)
            self.arrow_items[factor.key] = line
        self._kinds = {f.key: f.kind for f in (*model.effects, *model.terms)}
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(lambda _t: self.refresh())
        self.refresh()

    def _ratio(self, key: str) -> float:
        doc = self.document
        if doc.run is None or doc.normal is None:
            return 1.0
        mine, theirs = doc.run.factor(key, doc.playhead), doc.normal.factor(key, doc.playhead)
        if abs(theirs) < ZERO:
            return 1.0 if abs(mine) < ZERO else 4.0
        return mine / theirs

    def _removed(self) -> set[str]:
        doc = self.document
        params = doc.simulator.parameters_at(doc.experiment, doc.playhead)
        clamps = doc.simulator.clamps_at(doc.experiment, doc.playhead, params)
        zero = {doc.simulator.keys[i] for i, level in clamps.items() if abs(level) < ZERO}
        return {p.key for p in doc.model.parts if p.values and set(p.values) & zero}

    def _value_text(self, key: str) -> str:
        doc = self.document
        value = doc.simulator.values[key]
        if doc.run is None:
            return value.name
        if value.relative:
            ratio = doc.run.at(key, doc.playhead) / max(doc.normal.at(key, doc.playhead), ZERO)
            arrow = "↑" if ratio > 1.02 else "↓" if ratio < 0.98 else "="
            return f"{value.name} {arrow} {ratio:.2g}×"
        return f"{value.name} {doc.run.display(key, doc.playhead):.3g} {value.display_unit}"

    def part_label(self, key: str) -> str:
        return self.part_texts[key].text()

    def arrow_width(self, key: str) -> float:
        return self.arrow_items[key].pen().widthF()

    def is_dashed(self, key: str) -> bool:
        item = self.part_items.get(key) or self.arrow_items[key]
        return item.pen().style() == Qt.PenStyle.DashLine

    def refresh(self) -> None:
        removed = self._removed()
        for part in self.document.model.parts:
            label = part.name
            if part.values:
                label += "\n" + self._value_text(part.values[0])
            self.part_texts[part.key].setText(label)
            gone = part.key in removed
            pen = QPen(REMOVED if gone else BORDER, 2 if gone else 1)
            if gone:
                pen.setStyle(Qt.PenStyle.DashLine)
            self.part_items[part.key].setPen(pen)
        for key, line in self.arrow_items.items():
            ratio = self._ratio(key)
            width = 1 + 5 * min(max(ratio, 0.2), 4.0) / 4
            colour = HOLD if self._kinds[key] == "holds back" else INK
            pen = QPen(colour, width)
            start, end = self._ends(key)
            if abs(ratio) < ZERO or start in removed or end in removed:
                pen.setStyle(Qt.PenStyle.DashLine)
            line.setPen(pen)

    def _ends(self, key: str) -> tuple[str, str]:
        factor = next(f for f in (*self.document.model.effects, *self.document.model.terms)
                      if f.key == key)
        return factor.arrow

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None and item.data(0) is None:
                item = item.parentItem()
            if item is not None:
                self.document.select(item.data(0))
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        while item is not None and item.data(0) is None:
            item = item.parentItem()
        if item is None or item.data(0)[0] != "part":
            return
        key = item.data(0)[1]
        menu = QMenu(self)
        menu.addAction(QAction("Show in the atlas", menu,
                               triggered=lambda: self.show_in_atlas.emit(key)))
        menu.addAction(QAction("Show its chart", menu, triggered=lambda: self.show_chart.emit(key)))
        menu.exec(event.globalPos())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        bounds = self.scene().itemsBoundingRect().adjusted(-20, -20, 20, 20)
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def scene_point(self, key: str) -> QPointF:
        return self.part_items[key].sceneBoundingRect().center()
