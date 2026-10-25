from __future__ import annotations

import math
from itertools import pairwise
import re
from html import escape

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPainterPathStroker,
                           QPen, QPolygonF, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QGraphicsEllipseItem, QGraphicsItem,
                               QGraphicsPathItem, QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView, QHBoxLayout, QLabel, QStyle, QTextBrowser,
                               QToolButton, QVBoxLayout, QWidget)

from cns_atlas.cells import CellText, CellView, Reconstruction

from ..cell_layout import normal_at, place_cells, point_along
from ..state import AppState
from .pathway_panel import SPEEDS

BACKGROUND = "#141a22"
CELL_COLOURS = {"basic": QColor("#dbe6f2"), "full": QColor("#a9d2ff")}
FLOW_COLOURS = {"excitatory": QColor("#ffb648"), "inhibitory": QColor("#6fa8ff")}
BOX_FILL, BOX_EDGE, BOX_TEXT = QColor("#1e2732"), QColor("#5b6b7d"), QColor("#c6d0db")
REGION_TEXT, LAYER_TEXT, FLOW_TEXT = QColor("#8fb6e0"), QColor("#6f8399"), QColor("#ffcf85")
FADED = 0.28
ZOOM_RANGE = (0.5, 12.0)
FIT_MARGIN = 24.0
HIT_WIDTH = 0.05
SOMA_RADIUS = 0.035
KEY, ANCHOR = 0, 1
LAYER_ANCHOR = 0.02
Z_LAYER, Z_LABEL, Z_CELL, Z_FLOW, Z_BOX = 0, 1, 2, 3, 4
CITED = re.compile(r"\[(\d+)\]")
NEUROMORPHO_NOTE = ("Shapes from NeuroMorpho.Org (RRID:SCR_002145); Tecuatl C, Ljungquist B, "
                    "Ascoli GA (2024). Accelerating the continuous community sharing of digital "
                    "neuromorphology data. FASEB BioAdvances 6: 207-221.")
HINT = "Click a cell, layer or box to learn it."
TRAVEL_SECONDS = 1.6
HOLD_SECONDS = 0.8
STEP_SECONDS = TRAVEL_SECONDS + HOLD_SECONDS
TICK_MS = 16
PULSE_RADIUS = 10.0
READY = "Press Play to follow the signal"
DONE = "Done. Press Play to run it again"
LEVEL_NAMES = (("basic", "Basic"), ("full", "Full"))


def smooth_path(points) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for (ax, ay), (bx, by) in pairwise(points[1:]):
        path.quadTo(QPointF(ax, ay), QPointF((ax + bx) / 2, (ay + by) / 2))
    path.lineTo(QPointF(*points[-1]))
    return path


def end_mark(points, kind: str) -> QPainterPath:
    (ax, ay), (bx, by) = points[-2], points[-1]
    length = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / length, (by - ay) / length
    mark = QPainterPath()
    if kind == "inhibitory":
        mark.moveTo(bx - uy * 9, by + ux * 9)
        mark.lineTo(bx + uy * 9, by - ux * 9)
    else:
        mark.addPolygon(QPolygonF([QPointF(bx, by),
                                   QPointF(bx - ux * 14 - uy * 7, by - uy * 14 + ux * 7),
                                   QPointF(bx - ux * 14 + uy * 7, by - uy * 14 - ux * 7)]))
        mark.closeSubpath()
    return mark


class CellItem(QGraphicsPathItem):
    def __init__(self, path: QPainterPath, hit: QPainterPath) -> None:
        super().__init__(path)
        self._hit = hit

    def shape(self) -> QPainterPath:
        return self._hit


class CellGraphicsView(QGraphicsView):
    clicked = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor(BACKGROUND)))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.fit_scale = 1.0
        self.user_zoomed = False
        self._pan_from: QPointF | None = None

    def key_at(self, pos) -> str | None:
        for item in self.items(pos):
            while item is not None:
                key = item.data(KEY)
                if key:
                    return key
                item = item.parentItem()
        return None

    def zoom_at(self, pos: QPointF, delta: int) -> None:
        self.zoom_by_factor(pos, 1.15 ** (delta / 120))

    def zoom_by_factor(self, pos: QPointF, factor: float) -> None:
        low, high = (self.fit_scale * limit for limit in ZOOM_RANGE)
        factor = min(max(self.transform().m11() * factor, low), high) / self.transform().m11()
        point = pos.toPoint()
        before = self.mapToScene(point)
        centre = self.mapToScene(self.viewport().rect().center())
        self.scale(factor, factor)
        after = self.mapToScene(point)
        self.centerOn(centre - (after - before))
        self.user_zoomed = True

    def wheelEvent(self, event) -> None:
        self.zoom_at(event.position(), event.angleDelta().y())
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._pan_from = event.position()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key_at(event.position().toPoint()))
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._pan_from is not None:
            delta = event.position() - self._pan_from
            self._pan_from = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.user_zoomed = True
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._pan_from = None
        event.accept()


class CellPanel(QWidget):
    playing_changed = Signal(bool)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.cell_view: CellView | None = None
        self.cell_text: CellText | None = None
        self.level = "basic"
        self.side = "left"
        self.selected: str | None = None
        self.placed = ()
        self.flow_paths: dict[str, QPainterPath] = {}
        self._items: dict[str, list[QGraphicsItem]] = {}
        self._content = QRectF()
        self._shapes: dict[tuple[str, int], tuple[QPainterPath, QPainterPath]] = {}
        self.scene = QGraphicsScene(self)
        self.view = CellGraphicsView()
        self.view.setScene(self.scene)
        self.view.clicked.connect(self._on_clicked)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setMinimumHeight(140)
        self.text.setMaximumHeight(220)
        self.index = 0
        self.speed = 1.0
        self._time = 0.0
        self._running = False
        self._pulses: list[QGraphicsEllipseItem] = []
        self.timer = QTimer(self, interval=TICK_MS, timeout=lambda: self.advance(TICK_MS / 1000))
        levels = QHBoxLayout()
        group = QButtonGroup(self)
        self.level_buttons = {}
        for level, name in LEVEL_NAMES:
            button = QToolButton()
            button.setText(name)
            button.setCheckable(True)
            button.setChecked(level == self.level)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _=False, chosen=level: self.set_level(chosen))
            group.addButton(button)
            levels.addWidget(button)
            self.level_buttons[level] = button
        levels.addStretch(1)
        icon = self.style().standardIcon
        self._play_icon = icon(QStyle.StandardPixmap.SP_MediaPlay)
        self._pause_icon = icon(QStyle.StandardPixmap.SP_MediaPause)
        self.restart_button = self._control(icon(QStyle.StandardPixmap.SP_MediaSkipBackward),
                                            "Back to the start", self.restart)
        self.play_button = self._control(self._play_icon, "Play (Space)", self.toggle_play)
        self.speed_picker = QComboBox()
        for value, label in SPEEDS:
            self.speed_picker.addItem(label, value)
        self.speed_picker.setCurrentIndex(1)
        self.speed_picker.setToolTip("Speed")
        self.speed_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_picker.currentIndexChanged.connect(
            lambda i: self.set_speed(float(self.speed_picker.itemData(i))))
        self.caption = QLabel(READY)
        self.caption.setWordWrap(True)
        controls = QHBoxLayout()
        for widget in (self.restart_button, self.play_button, self.speed_picker):
            controls.addWidget(widget)
        controls.addWidget(self.caption, 1)
        self.playing_changed.connect(self._show_playing)
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(4)
        self.layout_box.addLayout(levels)
        self.layout_box.addWidget(self.view, 1)
        self.layout_box.addLayout(controls)
        self.layout_box.addWidget(self.text)

    def _control(self, icon, tip: str, action) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(action)
        return button

    def _show_playing(self, playing: bool) -> None:
        self.play_button.setIcon(self._pause_icon if playing else self._play_icon)
        self.play_button.setToolTip("Pause (Space)" if playing else "Play (Space)")

    def show_view(self, key: str) -> None:
        self.cell_view = next(v for v in self.state.atlas.cell_views() if v.key == key)
        self.cell_text = self.state.atlas.cell_text(key)
        self.selected = None
        self.redraw()
        self.fit()

    def set_level(self, level: str) -> None:
        self.level_buttons[level].setChecked(True)
        if level == self.level:
            return
        self.restart()
        self.level = level
        self.redraw()

    def set_side(self, side: str) -> None:
        if side == self.side:
            return
        self.side = side
        self.redraw()

    def items(self, key: str) -> list[QGraphicsItem]:
        return list(self._items.get(key, ()))

    def content_rect(self) -> QRectF:
        return QRectF(self._content)

    def fit(self) -> None:
        if self._content.isEmpty():
            return
        self.view.resetTransform()
        margin = FIT_MARGIN
        self.view.fitInView(self._content.adjusted(-margin, -margin, margin, margin),
                            Qt.AspectRatioMode.KeepAspectRatio)
        self.view.fit_scale = self.view.transform().m11()
        self.view.user_zoomed = False

    def zoom_by(self, factor: float) -> None:
        self.view.zoom_by_factor(QPointF(self.view.viewport().rect().center()), factor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.view.user_zoomed:
            self.fit()

    def _mirror(self, x: float, y: float) -> QPointF:
        if self.side == "right":
            return QPointF(self.cell_view.frame[0] - x, y)
        return QPointF(x, y)

    def _points(self, points) -> list[tuple[float, float]]:
        return [(p.x(), p.y()) for p in (self._mirror(x, y) for x, y in points)]

    def _keep(self, key: str, item: QGraphicsItem, anchor: QPointF, z: int) -> None:
        item.setData(KEY, key)
        item.setData(ANCHOR, anchor)
        item.setZValue(z)
        self.scene.addItem(item)
        self._items.setdefault(key, []).append(item)

    def _label(self, text: str, centre: QPointF, colour: QColor, size: float,
               italic: bool = False) -> QGraphicsSimpleTextItem:
        item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPointSizeF(size)
        font.setItalic(italic)
        item.setFont(font)
        item.setBrush(colour)
        box = item.boundingRect()
        item.setPos(centre - QPointF(box.width() / 2, box.height() / 2))
        item.setZValue(Z_LABEL)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene.addItem(item)
        self._items.setdefault("label", []).append(item)
        return item

    def _shape(self, cell: str, index: int, reconstruction: Reconstruction):
        key = (cell, index)
        if key not in self._shapes:
            path = QPainterPath()
            for line in reconstruction.lines:
                path.moveTo(line.points[0][0], -line.points[0][1])
                for x, y, _ in line.points[1:]:
                    path.lineTo(x, -y)
            soma = QPainterPath()
            soma.addEllipse(QPointF(0, 0), SOMA_RADIUS, SOMA_RADIUS)
            stroker = QPainterPathStroker()
            stroker.setWidth(HIT_WIDTH)
            hit = stroker.createStroke(path)
            hit.addPath(soma)
            self._shapes[key] = (path, soma, hit)
        return self._shapes[key]

    def _draw_layers(self) -> None:
        view = self.cell_view
        xs = [x for layer in view.layers for x, _ in layer.points]
        ys = [y for layer in view.layers for _, y in layer.points]
        centre = (sum(xs) / len(xs), sum(ys) / len(ys))
        labelled = set()
        for layer in view.layers:
            colour = QColor(*layer.colour)
            colour.setAlphaF(0.55 if layer.width <= 22 else 0.35)
            pen = QPen(colour, layer.width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            item = QGraphicsPathItem(smooth_path(self._points(layer.points)))
            item.setPen(pen)
            self._keep(f"layer:{layer.key}", item,
                       self._mirror(*point_along(layer.points, LAYER_ANCHOR)), Z_LAYER)
            mx, my = point_along(layer.points, 0.5)
            nx, ny = normal_at(layer.points, 0.5)
            if (mx + nx - centre[0]) ** 2 + (my + ny - centre[1]) ** 2 < (
                    mx - centre[0]) ** 2 + (my - centre[1]) ** 2:
                nx, ny = -nx, -ny
            if layer.region and layer.region not in labelled:
                labelled.add(layer.region)
                offset = layer.width / 2 + 26
                self._label(layer.region.upper(), self._mirror(mx + nx * offset, my + ny * offset),
                            REGION_TEXT, 13)
            lx, ly = point_along(layer.points, 0.12)
            self._label(layer.name, self._mirror(lx, ly), LAYER_TEXT, 7.5, italic=True)

    def _draw_cells(self) -> None:
        cells = {cell.key: cell for cell in self.cell_view.cells}
        for placed in self.placed:
            cell = cells[placed.cell]
            path, soma, hit = self._shape(cell.key, placed.reconstruction,
                                          cell.reconstructions[placed.reconstruction])
            item = CellItem(path, hit)
            pen = QPen(CELL_COLOURS[cell.level], 0.9)
            pen.setCosmetic(True)
            item.setPen(pen)
            body = QGraphicsPathItem(soma, item)
            body.setPen(QPen(Qt.PenStyle.NoPen))
            body.setBrush(QBrush(CELL_COLOURS[cell.level]))
            transform = (QTransform().scale(1 if placed.mirrored else -1, 1)
                         * QTransform().scale(placed.scale, placed.scale)
                         * QTransform().rotate(placed.angle + 90.0)
                         * QTransform().translate(placed.x, placed.y))
            if self.side == "right":
                transform = transform * QTransform(-1, 0, 0, 1, self.cell_view.frame[0], 0)
            item.setTransform(transform)
            self._keep(f"cell:{cell.key}", item, QPointF(0, 0), Z_CELL)

    def _draw_flows(self) -> None:
        self.flow_paths = {}
        used = {key for step in self.cell_view.levels[self.level] for key in step.flows}
        for flow in (f for f in self.cell_view.flows if f.key in used):
            points = self._points(flow.points)
            path = smooth_path(points)
            self.flow_paths[flow.key] = path
            colour = FLOW_COLOURS[flow.kind]
            pen = QPen(colour, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            line = QGraphicsPathItem(path)
            line.setPen(pen)
            line.setZValue(Z_FLOW)
            line.setOpacity(0.7)
            line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(line)
            mark = QGraphicsPathItem(end_mark(points, flow.kind), line)
            mark.setPen(QPen(colour, 2.4))
            if flow.kind == "excitatory":
                mark.setBrush(QBrush(colour))
            self._items.setdefault(f"flow:{flow.key}", []).append(line)
            if flow.label:
                middle = path.pointAtPercent(0.5)
                self._label(flow.label, middle + QPointF(0, -12), FLOW_TEXT, 8.5)

    def _draw_boxes(self) -> None:
        for box in self.cell_view.boxes:
            centre = self._mirror(*box.centre)
            width, height = box.size
            path = QPainterPath()
            path.addRoundedRect(QRectF(centre.x() - width / 2, centre.y() - height / 2, width,
                                       height), 6, 6)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(BOX_EDGE, 1.2))
            item.setBrush(QBrush(BOX_FILL))
            self._keep(f"box:{box.key}", item, centre, Z_BOX)
            label = self._label(box.name, centre, BOX_TEXT, 9)
            label.setZValue(Z_BOX + 0.5)

    def redraw(self) -> None:
        self.scene.clear()
        self._items = {}
        self._pulses = []
        if self.cell_view is None:
            return
        self.placed = place_cells(self.cell_view, self.level)
        self._draw_layers()
        self._draw_cells()
        self._draw_flows()
        self._draw_boxes()
        self._content = self.scene.itemsBoundingRect()
        self.scene.setSceneRect(self._content.adjusted(-self._content.width(),
                                                       -self._content.height(),
                                                       self._content.width(),
                                                       self._content.height()))
        if self.selected is not None and not self._items.get(self.selected):
            self.selected = None
        self.select(self.selected)

    def _on_clicked(self, key: str | None) -> None:
        if self._running:
            self.pause()
            self._running = False
            self._show_run()
        self.select(key)

    def select(self, key: str | None) -> None:
        self.selected = key
        self._apply_look()
        self.text.setHtml(self.html_for(key))

    def _apply_look(self) -> None:
        if self._running:
            lit = self._lit()
            for name, items in self._items.items():
                if name.startswith("cell:"):
                    for item in items:
                        item.setOpacity(1.0 if name.partition(":")[2] in lit else FADED)
            return
        fade = self.selected is not None and self.selected.startswith("cell:")
        for name, items in self._items.items():
            if name.startswith("cell:"):
                for item in items:
                    item.setOpacity(FADED if fade and name != self.selected else 1.0)

    @property
    def steps(self):
        return self.cell_view.levels[self.level] if self.cell_view is not None else ()

    @property
    def playing(self) -> bool:
        return self.timer.isActive()

    @property
    def progress(self) -> float:
        return self._time / STEP_SECONDS

    def pulses(self) -> list[QGraphicsEllipseItem]:
        return list(self._pulses)

    def _lit(self) -> set[str]:
        steps = self.steps
        done = steps[:self.index] if self._time < TRAVEL_SECONDS else steps[:self.index + 1]
        return {key for step in done for key in step.lit}

    def _step_caption(self) -> str:
        if self.cell_text is None:
            return f"Step {self.index + 1}"
        captions = self.cell_text.steps.get(self.level, ())
        return captions[self.index] if self.index < len(captions) else f"Step {self.index + 1}"

    def _pulse(self) -> QGraphicsEllipseItem:
        gradient = QRadialGradient(QPointF(0, 0), PULSE_RADIUS)
        gradient.setColorAt(0.0, QColor("#fff3d6"))
        gradient.setColorAt(0.4, QColor("#ffc35a"))
        gradient.setColorAt(1.0, QColor(255, 182, 72, 0))
        item = QGraphicsEllipseItem(-PULSE_RADIUS, -PULSE_RADIUS, 2 * PULSE_RADIUS,
                                    2 * PULSE_RADIUS)
        item.setBrush(QBrush(gradient))
        item.setPen(QPen(Qt.PenStyle.NoPen))
        item.setZValue(Z_BOX + 1)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene.addItem(item)
        return item

    def _show_run(self) -> None:
        live = set(self.steps[self.index].flows) if self._running and self.steps else set()
        travelling = self._running and self._time < TRAVEL_SECONDS
        for name, items in self._items.items():
            if name.startswith("flow:"):
                for item in items:
                    item.setOpacity(1.0 if name.partition(":")[2] in live else 0.7)
        keys = [key for key in self.steps[self.index].flows if key in self.flow_paths] \
            if travelling else []
        while len(self._pulses) < len(keys):
            self._pulses.append(self._pulse())
        for n, item in enumerate(self._pulses):
            item.setVisible(n < len(keys))
            if n < len(keys):
                item.setPos(self.flow_paths[keys[n]].pointAtPercent(
                    self._time / TRAVEL_SECONDS))
        self._apply_look()

    def toggle_play(self) -> None:
        self.pause() if self.playing else self.play()

    def play(self) -> None:
        if not self.steps:
            return
        if not self._running:
            self.index, self._time = 0, 0.0
            self._running = True
            self.caption.setText(self._step_caption())
        self.timer.start()
        self.playing_changed.emit(True)
        self._show_run()

    def pause(self) -> None:
        was = self.timer.isActive()
        self.timer.stop()
        if was:
            self.playing_changed.emit(False)

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def advance(self, seconds: float) -> None:
        if not self.playing:
            return
        self._time += seconds * self.speed
        while self._time >= STEP_SECONDS:
            self._time -= STEP_SECONDS
            self.index += 1
            if self.index >= len(self.steps):
                self._finish()
                return
            self.caption.setText(self._step_caption())
        self._show_run()

    def _finish(self) -> None:
        self.pause()
        self._running = False
        self.index, self._time = 0, 0.0
        self.caption.setText(DONE)
        self._show_run()

    def _jump(self, index: int) -> None:
        self.pause()
        self._running = True
        self.index, self._time = index, 0.0
        self.caption.setText(self._step_caption())
        self._show_run()

    def next(self) -> None:
        if self.steps:
            self._jump(min(self.index + 1, len(self.steps) - 1))

    def back(self) -> None:
        if self.steps:
            self._jump(max(self.index - 1, 0))

    def restart(self) -> None:
        self.pause()
        self._running = False
        self.index, self._time = 0, 0.0
        self.caption.setText(READY)
        self._show_run()

    def _cited(self, texts) -> str:
        if self.cell_text is None:
            return ""
        numbers = sorted({int(n) for text in texts for n in CITED.findall(text)})
        rows = []
        for n in numbers:
            if 0 < n <= len(self.cell_text.references):
                ref = self.cell_text.references[n - 1]
                link = f" <a href='{escape(ref.link)}'>link</a>" if ref.link else ""
                rows.append(f"<p><small>[{n}] {escape(ref.citation())}{link}</small></p>")
        return "".join(rows)

    def _heading(self, name: str) -> str:
        draft = (self.cell_text is None or self.cell_text.status == "draft")
        tag = " <small style='color:#c9a15a'>draft for review</small>" if draft else ""
        return f"<h3>{escape(name)}{tag}</h3>"

    def html_for(self, key: str | None) -> str:
        view, text = self.cell_view, self.cell_text
        if view is None:
            return ""
        items = text.items if text is not None else {}
        if key is None:
            overview = text.overview if text is not None else ""
            return (f"{self._heading(view.name)}<p>{escape(overview)}</p>"
                    f"<p><i>{HINT}</i></p>{self._cited([overview])}")
        kind, _, name = key.partition(":")
        body = items.get(key, "")
        if kind == "cell":
            cell = next(c for c in view.cells if c.key == name)
            layers = {layer.key: layer.name for layer in view.layers}
            where = ", ".join(dict.fromkeys(layers[p.layer] for p in cell.placements))
            shapes = "".join(
                f"<p><small>Shape: {escape(r.species)}, NeuroMorpho {r.neuromorpho_id}, "
                f"{escape(r.archive)} archive; drawn scaled to its layer. "
                f"{escape(r.citation)}.</small></p>" for r in cell.reconstructions)
            return (f"{self._heading(cell.name)}<p style='color:#8fa3b8'>{escape(where)}</p>"
                    f"<p>{escape(body)}</p>{shapes}<p><small>{escape(NEUROMORPHO_NOTE)}"
                    f"</small></p>{self._cited([body])}")
        group = view.layers if kind == "layer" else view.boxes
        title = next(item.name for item in group if item.key == name)
        return f"{self._heading(title)}<p>{escape(body)}</p>{self._cited([body])}"
