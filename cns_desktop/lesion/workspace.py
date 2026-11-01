from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.tokens import SIZE

from .document import LesionDocument
from .place_panel import PlacePanel
from .results_panel import DeficitsPanel, HitPanel


def lesion_mesh(atlas, lesion):
    pieces = []
    for volume in atlas.volumes:
        mask = lesion.masks.get(volume.name)
        affine = np.asarray(volume.affine, dtype=float)
        if mask is None or not mask.any() or np.any(np.diag(affine)[:3] <= 0):
            continue
        grid = pv.ImageData(dimensions=mask.shape, spacing=tuple(np.diag(affine)[:3]),
                            origin=tuple(affine[:3, 3]))
        grid.point_data["lesion"] = mask.ravel(order="F").astype(np.uint8)
        surface = grid.contour([0.5], scalars="lesion")
        if surface.n_points:
            pieces.append(surface)
    if not pieces:
        return None
    return pieces[0] if len(pieces) == 1 else pieces[0].merge(pieces[1:])


class LesionWorkspace:
    def __init__(self, window) -> None:
        self.window = window
        self.document = LesionDocument(window.state.atlas, window)
        self.place, self.cases = PlacePanel(self.document, window), QWidget()
        self.deficits = DeficitsPanel(self.document)
        self.hit = HitPanel(self.document, window.state)
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
        self.document.changed.connect(self._show)
        window.workspaces.register("Lesion", self.docks, self.enter, self.leave, self._arrange,
                                   narrow=[("Lesion tools", "Lesion results")],
                                   shared=[window.slices_group])

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

    def enter(self) -> None:
        self._saved = self.window._snapshot()
        self.active = True
        self.place.activate(True)
        self._show()

    def leave(self) -> None:
        self.place.activate(False)
        self.active = False
        self.window.slices.set_lesion({})
        self.window.view.set_lesion_body(None)
        if self._saved is not None:
            self.window._restore(*self._saved)
            self._saved = None
