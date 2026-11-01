from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QFontMetricsF, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QMenu)

from cns_desktop.design.fonts import font
from cns_desktop.design.tokens import color

from .labels import plain, ratio_text, removed_parts

CELL_X, CELL_Y = 230.0, 120.0
BOX_W, BOX_H = 200.0, 64.0
INK = color("text")
HOLD = color("lowered")
REMOVED = color("edited")
BOX_FILL = color("s2")
BORDER = color("control")
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
    show_on_timeline = Signal(str)

    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(color("s0")))
        self.setRenderHint(self.renderHints().Antialiasing)
        document.model_changed.connect(self.populate)
        self.populate()
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(lambda _t: self.refresh())
        self.refresh()

    def populate(self) -> None:
        self.scene().clear()
        self.part_items: dict[str, QGraphicsRectItem] = {}
        self.part_texts: dict[str, QGraphicsSimpleTextItem] = {}
        self.arrow_items: dict[str, QGraphicsLineItem] = {}
        self._segments: dict[str, list[QGraphicsLineItem]] = {}
        model = self.document.model
        for part in model.parts:
            rect = QGraphicsRectItem(QRectF(part.x * CELL_X, part.y * CELL_Y, BOX_W, BOX_H))
            rect.setBrush(QBrush(BOX_FILL))
            rect.setData(0, ("part", part.key))
            text = QGraphicsSimpleTextItem(rect)
            text.setBrush(QBrush(INK))
            text.setFont(font("label"))
            text.setPos(part.x * CELL_X + 12, part.y * CELL_Y + 10)
            self.scene().addItem(rect)
            self.part_items[part.key] = rect
            self.part_texts[part.key] = text
        for factor in (*model.effects, *model.terms):
            if factor.arrow is None or factor.arrow[0] == factor.arrow[1]:
                continue
            centre = {k: self.part_items[k].rect().center() for k in (*factor.arrow, *factor.via)}
            first, last = factor.arrow
            pairs = ([(first, part) for part in factor.via] + [(part, last) for part in factor.via]
                     if factor.via else [(first, last)])
            lines = []
            for start, end in pairs:
                line = _Arrow(QLineF(centre[start], centre[end]))
                line.setData(0, ("link", factor.key))
                line.setZValue(-1)
                self.scene().addItem(line)
                lines.append(line)
            self.arrow_items[factor.key] = lines[0]
            self._segments[factor.key] = lines
        self._kinds = {f.key: f.kind for f in (*model.effects, *model.terms)}
        self.refresh()
        self.setSceneRect(self.scene().itemsBoundingRect())
        self.resizeEvent(None)

    def _ratio(self, key: str, factors=None) -> float:
        doc = self.document
        if doc.run is None or doc.normal is None:
            return 1.0
        if factors is None:
            factors = doc.run.factors(doc.playhead), doc.normal.factors(doc.playhead)
        mine, theirs = factors[0][key], factors[1][key]
        if abs(theirs) < ZERO:
            return 1.0 if abs(mine) < ZERO else 4.0
        return mine / theirs

    def _removed(self) -> set[str]:
        return removed_parts(self.document)

    def _value_text(self, key: str) -> tuple[str, str]:
        doc = self.document
        value = doc.simulator.values[key]
        if doc.run is None:
            return value.name, ""
        if value.relative:
            ratio = doc.run.at(key, doc.playhead) / max(doc.normal.at(key, doc.playhead), ZERO)
            return value.name, ratio_text(ratio)
        return value.name, f"{plain(doc.run.display(key, doc.playhead), 3)} {value.display_unit}"

    def _fit(self, *lines: str) -> str:
        metrics = QFontMetricsF(font("label"))
        room = BOX_W - 24
        return "\n".join(metrics.elidedText(line, Qt.TextElideMode.ElideRight, room)
                         for line in lines)

    def _label(self, part, removed: set[str]) -> str:
        if part.key in removed:
            return self._fit(part.name, "removed")
        if not part.values:
            return self._fit(part.name)
        name, reading = self._value_text(part.values[0])
        whole = f"{name} {reading}".strip()
        if QFontMetricsF(font("label")).horizontalAdvance(whole) <= BOX_W - 24:
            return self._fit(part.name, whole)
        return self._fit(part.name, name, reading)

    def part_label(self, key: str) -> str:
        return self.part_texts[key].text()

    def segments(self, key: str) -> list[QGraphicsLineItem]:
        return list(self._segments[key])

    def arrow_width(self, key: str) -> float:
        return self.arrow_items[key].pen().widthF()

    def is_dashed(self, key: str) -> bool:
        item = self.part_items.get(key) or self.arrow_items[key]
        return item.pen().style() == Qt.PenStyle.DashLine

    def refresh(self) -> None:
        removed = self._removed()
        for part in self.document.model.parts:
            self.part_texts[part.key].setText(self._label(part, removed))
            gone = part.key in removed
            pen = QPen(REMOVED if gone else BORDER, 2 if gone else 1)
            if gone:
                pen.setStyle(Qt.PenStyle.DashLine)
            self.part_items[part.key].setPen(pen)
        doc = self.document
        factors = None
        if doc.run is not None and doc.normal is not None:
            factors = doc.run.factors(doc.playhead), doc.normal.factors(doc.playhead)
        for key, lines in self._segments.items():
            ratio = self._ratio(key, factors)
            width = 1 + 5 * min(max(ratio, 0.2), 4.0) / 4
            colour = HOLD if self._kinds[key] == "holds back" else INK
            pen = QPen(colour, width)
            start, end = self._ends(key)
            if abs(ratio) < ZERO or start in removed or end in removed:
                pen.setStyle(Qt.PenStyle.DashLine)
            for line in lines:
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
        menu.addAction(QAction("Show on the timeline", menu,
                               triggered=lambda: self.show_on_timeline.emit(key)))
        menu.exec(event.globalPos())

    def resizeEvent(self, event) -> None:
        if event is not None:
            super().resizeEvent(event)
        bounds = self.scene().itemsBoundingRect().adjusted(-20, -20, 20, 20)
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def scene_point(self, key: str) -> QPointF:
        return self.part_items[key].sceneBoundingRect().center()
