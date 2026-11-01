from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from cns_desktop.design.panels import PanelGroup
from cns_desktop.design.tokens import SIZE

from .document import LesionDocument


class LesionWorkspace:
    def __init__(self, window) -> None:
        self.window = window
        self.document = LesionDocument(window.state.atlas, window)
        self.place, self.cases = QWidget(), QWidget()
        self.deficits, self.hit = QWidget(), QWidget()
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

    def enter(self) -> None:
        self._saved = self.window._snapshot()

    def leave(self) -> None:
        if self._saved is not None:
            self.window._restore(*self._saved)
            self._saved = None
