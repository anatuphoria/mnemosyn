from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence

from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.tokens import SIZE

from cns_atlas.lesions import report

from .document import LesionDocument
from .cases_panel import CasesPanel
from .place_panel import PlacePanel
from .results_panel import DeficitsPanel, HitPanel


def lesion_mesh(atlas, lesion):
    pieces = []
    for volume in atlas.volumes:
        mask = lesion.masks.get(volume.name)
        if mask is None or not mask.any():
            continue
        grid = pv.ImageData(dimensions=mask.shape)
        grid.point_data["lesion"] = mask.ravel(order="F").astype(np.uint8)
        surface = grid.contour([0.5], scalars="lesion")
        if surface.n_points:
            pieces.append(surface.transform(np.asarray(volume.affine, dtype=float),
                                            inplace=False))
    if not pieces:
        return None
    return pieces[0] if len(pieces) == 1 else pieces[0].merge(pieces[1:])


class LesionWorkspace:
    def __init__(self, window) -> None:
        self.window = window
        self.document = LesionDocument(window.state.atlas, window)
        self.place = PlacePanel(self.document, window)
        self.cases = CasesPanel(self.document, self)
        self.deficits = DeficitsPanel(self.document)
        self.hit = HitPanel(self.document, window.state, self.place.select_quietly)
        self.tools_group = self._group("Lesion tools", [("place", "Place", self.place),
                                                        ("cases", "Cases", self.cases)],
                                       Qt.DockWidgetArea.LeftDockWidgetArea)
        self.results_group = self._group("Lesion results", [("deficits", "Deficits", self.deficits),
                                                            ("hit", "Hit", self.hit)],
                                         Qt.DockWidgetArea.RightDockWidgetArea)
        self.docks = [self.tools_group, self.results_group]
        for dock in self.docks:
            window.window_menu.insertAction(window.window_separator, dock.toggleViewAction())
        self._saved = None
        self.active = False
        self.undo_action = self._key("Undo lesion", "Ctrl+Z", self.document.undo.undo)
        self.redo_action = self._key("Redo lesion", "Ctrl+Shift+Z", self.document.undo.redo)
        self.document.changed.connect(self._show)
        self.place.tool_changed.connect(lambda _tool: self._show())
        window.workspaces.register("Lesion", self.docks, self.enter, self.leave, self._arrange,
                                   narrow=[("Lesion tools", "Lesion results")],
                                   shared=[window.slices_group])

    def _key(self, name: str, key: str, slot) -> QAction:
        action = QAction(name, self.window, shortcut=QKeySequence(key), triggered=slot)
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.setEnabled(False)
        self.window.addAction(action)
        return action

    def explain_case(self, case) -> None:
        self.deficits.show_case(report(self.document.atlas, case.target), case.label)
        self.results_group.reveal("deficits")

    def _group(self, name: str, pages, area) -> PanelGroup:
        group = PanelGroup(name, pages, self.window)
        group.setObjectName(name)
        self.window.addDockWidget(area, group)
        group.hide()
        return group

    def _arrange(self) -> None:
        window = self.window
        window.splitDockWidget(window.slices_group, self.results_group, Qt.Orientation.Horizontal)
        window.resizeDocks([self.tools_group, window.slices_group, self.results_group],
                           [SIZE["panel_left"], SIZE["panel_right"], SIZE["panel_right"]],
                           Qt.Orientation.Horizontal)

    def _show(self) -> None:
        if not self.active:
            return
        self.window.slices.set_lesion(self.document.lesion.masks)
        self.window.view.set_lesion_body(lesion_mesh(self.document.atlas, self.document.lesion))
        hits = self.document.report.hits
        fade = hits and self.place.tool != "structure"
        self.window.state.set_focus(set(hits) if fade else None)

    def show_answer(self, lesion) -> None:
        if not self.active:
            return
        self.window.slices.set_answer(lesion.masks if lesion is not None else {})
        self.window.view.set_answer_body(lesion_mesh(self.document.atlas, lesion)
                                         if lesion is not None else None)

    def enter(self) -> None:
        self._saved = self.window._snapshot()
        self.active = True
        self.undo_action.setEnabled(True)
        self.redo_action.setEnabled(True)
        self.place.activate(True)
        self.window.view.mute_selection(True)
        self._show()
        if self.cases.revealed and self.cases.case is not None:
            self.show_answer(self.cases.case.target)

    def leave(self) -> None:
        self.window.view.mute_selection(False)
        self.place.activate(False)
        self.active = False
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.window.state.set_focus(None)
        self.window.slices.set_lesion({})
        self.window.slices.set_answer({})
        self.window.view.set_lesion_body(None)
        self.window.view.set_answer_body(None)
        if self._saved is not None:
            self.window._restore(*self._saved)
            self._saved = None
