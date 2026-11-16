from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from .experiments_panel import MIME
from .timeline_metrics import EDGE, FINE_STEPS, GRAB, LABEL_WIDTH, LANE_HEIGHT, SWIPE


class TimelineInput:
    def _press_overview(self, pos: QPointF) -> None:
        window = self.overview_window()
        inside = window.left() <= pos.x() <= window.right()
        if inside and window.width() <= 4 * GRAB:
            kind = "window"
        elif abs(pos.x() - window.right()) <= GRAB:
            kind = "window_right"
        elif abs(pos.x() - window.left()) <= GRAB:
            kind = "window_left"
        else:
            kind = "window"
            if not window.contains(QPointF(pos.x(), window.center().y())) and pos.x() >= LABEL_WIDTH:
                width = self.span[1] - self.span[0]
                middle = self._overview_t(pos.x())
                self._set_span(middle - width / 2, middle + width / 2)
        self._press = {"kind": kind, "x": pos.x(), "span": self.span}

    def _drag_overview(self, press: dict, x: float) -> None:
        minutes = (x - press["x"]) / self._plot_width() * self.document.experiment.length
        start, end = press["span"]
        length = self.document.experiment.length
        if press["kind"] == "window":
            self._set_span(start + minutes, end + minutes)
        elif press["kind"] == "window_left":
            self._set_span(min(max(start + minutes, 0.0), end - self.document.scale.min_span), end)
        else:
            end = max(min(end + minutes, length), start + self.document.scale.min_span)
            self.span = (start, end)
            self.update()

    def _set_hover(self, pos: QPointF | None) -> None:
        if pos != self._hover_pos:
            self._hover_pos = pos
            self.update()

    def leaveEvent(self, event) -> None:
        self._set_hover(None)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._set_hover(None)
        self.setFocus()
        if pos.y() < self.ruler_rect().top():
            self._press_overview(pos)
            return
        if self.ruler_rect().contains(pos) or self._on_playhead(pos):
            self._press = {"kind": "scrub"}
            self.document.set_playhead(self.t_of(pos.x()))
            return
        index = self._block_at(pos)
        if index is not None:
            block = self.document.experiment.blocks[index]
            self.document.select(("block", index))
            if block.present:
                self._press = None
                return
            rect = self.block_rect(index)
            stretch = block.length is not None and pos.x() >= rect.right() - EDGE
            self._press = {"kind": "stretch" if stretch else "move", "block": index,
                           "x": pos.x(), "start": block.start, "length": block.length}
            return
        self._press = {"kind": "pan", "x": pos.x()}

    def _on_playhead(self, pos: QPointF) -> bool:
        return pos.x() >= LABEL_WIDTH and pos.y() >= self.ruler_rect().top() and abs(pos.x() - self.x_of(self.document.playhead)) <= GRAB

    def _limits(self, start: float, length: float | None) -> tuple[float, float | None]:
        run = self.document.experiment.length
        least = self.document.scale.least
        start = min(max(start, 0.0), run - least)
        if length is not None:
            length = min(max(length, least), run - start)
        return start, length

    def mouseMoveEvent(self, event) -> None:
        press = self._press
        if not press or not (event.buttons() & Qt.MouseButton.LeftButton):
            self._show_cursor(event.position())
            self._set_hover(QPointF(event.position()))
            return super().mouseMoveEvent(event)
        x = event.position().x()
        if press["kind"].startswith("window"):
            self._drag_overview(press, x)
            return
        if press["kind"] == "scrub":
            self.document.set_playhead(self.t_of(x))
            return
        minutes = (x - press["x"]) / self._plot_width() * (self.span[1] - self.span[0])
        if press["kind"] == "pan":
            self._pan(-minutes)
            press["x"] = x
            return
        if press["kind"] == "move":
            start, length = self._limits(self._snap(press["start"] + minutes), press["length"])
            if length is not None and start + length > self.document.experiment.length:
                start = self.document.experiment.length - length
        else:
            start, length = self._limits(press["start"],
                                         self._snap(press["length"] + minutes))
        press["preview"] = (start, length)
        self.update()

    def _show_cursor(self, pos: QPointF) -> None:
        index = self._block_at(pos)
        window = self.overview_window()
        if pos.y() < self.ruler_rect().top():
            edge = min(abs(pos.x() - window.left()), abs(pos.x() - window.right())) <= GRAB
            inside = window.left() <= pos.x() <= window.right()
            shape = (Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.OpenHandCursor
                     if inside else Qt.CursorShape.PointingHandCursor)
        elif self._on_playhead(pos) or self.ruler_rect().contains(pos):
            shape = Qt.CursorShape.SizeHorCursor
        elif index is not None and not self.document.experiment.blocks[index].present:
            block = self.document.experiment.blocks[index]
            edge = block.length is not None and pos.x() >= self.block_rect(index).right() - EDGE
            shape = Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.OpenHandCursor
        else:
            shape = Qt.CursorShape.ArrowCursor
        self.setCursor(shape)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.position().y() < self.body_top():
            self.show_whole_run()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        press, self._press = self._press, None
        if not press or "preview" not in press:
            self.update()
            return
        start, length = press["preview"]
        index = press["block"]
        if press["kind"] == "move" and start != press["start"]:
            self.document.move_block(index, start)
        elif press["kind"] == "stretch" and length != press["length"]:
            self.document.stretch_block(index, length)
        self.update()

    def wheelEvent(self, event) -> None:
        sideways, steps = event.angleDelta().x() / 120, event.angleDelta().y() / 120
        if event.position().x() < LABEL_WIDTH and not sideways and steps:
            self.scroll.setValue(self.scroll.value() - round(steps * LANE_HEIGHT))
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and not sideways:
            sideways, steps = steps, 0.0
        if sideways:
            self._pan(-sideways * SWIPE * (self.span[1] - self.span[0]))
        elif steps:
            self.zoom(0.8 ** steps, self.t_of(event.position().x()))
        else:
            return
        event.accept()

    def keyPressEvent(self, event) -> None:
        doc = self.document
        width = self.span[1] - self.span[0]
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = width / FINE_STEPS if shift else width / self._plot_width()
        moves = {Qt.Key.Key_Right: doc.playhead + step, Qt.Key.Key_Left: doc.playhead - step,
                 Qt.Key.Key_Home: 0.0, Qt.Key.Key_End: doc.experiment.length}
        if event.key() in moves:
            doc.set_playhead(moves[event.key()])
            self._follow(doc.playhead)
            return
        selection = self.document.selection
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and selection and (
                selection[0] == "block"):
            self.document.delete_block(selection[1])
            return
        super().keyPressEvent(event)

    def _follow(self, t: float) -> None:
        start, end = self.span
        if t < start:
            self._set_span(t, t + end - start)
        elif t > end:
            self._set_span(t - (end - start), t)

    def _set_guides(self, on: bool) -> None:
        self.show_guides = bool(on)
        self.update()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        data = event.mimeData()
        if not data.hasFormat(MIME):
            return
        key = bytes(data.data(MIME)).decode("utf-8")
        self.document.add_block(key, self._snap(self.t_of(event.position().x())))
        event.acceptProposedAction()

    def contextMenuEvent(self, event) -> None:
        pos = QPointF(event.pos())
        menu = QMenu(self)
        index = self._block_at(pos)
        if index is not None:
            self.document.select(("block", index))
            menu.addAction(QAction("Edit", menu, triggered=lambda: self.edit_requested.emit(index)))
            menu.addAction(QAction("Duplicate", menu,
                                   triggered=lambda: self.document.duplicate_block(index)))
            menu.addAction(QAction("Delete", menu,
                                   triggered=lambda: self.document.delete_block(index)))
        else:
            lane = next((k for k in self.lane_keys() if self.lane_rect(k).contains(pos)), None)
            if lane is not None:
                menu.addAction(QAction("Hide lane", menu, triggered=lambda: self.hide_lane(lane)))
            if self.hidden:
                menu.addAction(QAction("Show every lane", menu, triggered=self.show_lanes))
            if self.span != (0.0, self.document.experiment.length):
                menu.addAction(QAction("Show the whole run", menu, triggered=self.show_whole_run))
            toggle = QAction("Show normal line", menu, checkable=True, checked=self.compare_on)
            toggle.toggled.connect(lambda on: setattr(self, "compare", on))
            menu.addAction(toggle)
            guides = QAction("Show change guides", menu, checkable=True, checked=self.show_guides)
            guides.toggled.connect(self._set_guides)
            menu.addAction(guides)
        menu.exec(event.globalPos())
