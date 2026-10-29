from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDockWidget, QStackedWidget, QWidget

from cns_desktop.design.tokens import SIZE
from cns_desktop.design.widgets import PanelHeader, SegmentedControl


class PanelGroup(QDockWidget):
    page_changed = Signal(str)

    def __init__(self, name: str, pages: list[tuple[str, str, QWidget]], parent=None) -> None:
        super().__init__(name, parent)
        self.setObjectName(name)
        self.name = name
        self.setMinimumWidth(SIZE["panel_min"])
        self._labels: dict[str, str] = {}
        self._pages: dict[str, QWidget] = {}
        self._own: list[str] = []
        self._guests: list[PanelGroup] = []
        self._host: PanelGroup | None = None
        self.stack = QStackedWidget()
        self.setWidget(self.stack)
        self.tabs = SegmentedControl([])
        self.tabs.changed.connect(self._on_tab)
        self.header = PanelHeader(name, self.tabs)
        self.float_button = self.header.add_button("picture-in-picture-2", "Float or dock",
                                                   lambda: self.setFloating(not self.isFloating()))
        self.close_button = self.header.add_button("x", "Close", self.close)
        self.setTitleBarWidget(self.header)
        self.featuresChanged.connect(lambda _features: self._sync_buttons())
        for key, label, widget in pages:
            self._own.append(key)
            self._add_page(key, label, widget)
        self._sync_buttons()
        self._sync_header()

    def _add_page(self, key: str, label: str, widget: QWidget) -> None:
        self._labels[key] = label
        self._pages[key] = widget
        self.stack.addWidget(widget)
        self.tabs.add_option(key, label)

    def _take_page(self, key: str) -> tuple[str, QWidget]:
        widget = self._pages.pop(key)
        label = self._labels.pop(key)
        self.stack.removeWidget(widget)
        self.tabs.remove_option(key)
        return label, widget

    def _sync_header(self) -> None:
        pages = [page.minimumSizeHint().width() for page in self._pages.values()]
        self.setMinimumWidth(max([SIZE["panel_min"], *pages]))
        several = len(self._pages) > 1
        self.header.tabs.setVisible(several)
        self.header.title.setVisible(not several)
        if not several and self._pages:
            self.header.set_title(self._labels[next(iter(self._pages))])
        current = self.tabs.current()
        if current in self._pages:
            self.stack.setCurrentWidget(self._pages[current])

    def _sync_buttons(self) -> None:
        features = self.features()
        self.float_button.setVisible(bool(features & QDockWidget.DockWidgetFeature
                                          .DockWidgetFloatable))
        self.close_button.setVisible(bool(features & QDockWidget.DockWidgetFeature
                                          .DockWidgetClosable))

    def _on_tab(self, key: str) -> None:
        if key in self._pages:
            self.stack.setCurrentWidget(self._pages[key])
            self.page_changed.emit(key)

    def setVisible(self, visible: bool) -> None:
        if visible and self._host is not None:
            self._host.setVisible(True)
            return
        super().setVisible(visible)

    def keys(self) -> list[str]:
        return list(self._pages)

    def page(self, key: str) -> QWidget:
        if key in self._pages:
            return self._pages[key]
        if self._host is not None:
            return self._host.page(key)
        raise KeyError(key)

    def current(self) -> str:
        return self.tabs.current()

    def show_page(self, key: str) -> None:
        if self._host is not None:
            self._host.show_page(key)
            return
        if key not in self._pages:
            raise KeyError(key)
        self.tabs.set_current(key)
        self.stack.setCurrentWidget(self._pages[key])

    def reveal(self, key: str) -> None:
        host = self._host or self
        host.show()
        host.raise_()
        host.show_page(key)

    def host(self) -> PanelGroup | None:
        return self._host

    def joined(self) -> list[PanelGroup]:
        return list(self._guests)

    def join(self, guest: PanelGroup) -> None:
        if guest is self or guest in self._guests or guest._host is not None or self._host:
            return
        for other in list(guest._guests):
            guest.release(other)
        current = self.current()
        for key in list(guest._own):
            label, widget = guest._take_page(key)
            self._add_page(key, label, widget)
        guest._host = self
        guest.toggleViewAction().setVisible(False)
        guest.hide()
        self._guests.append(guest)
        if current:
            self.tabs.set_current(current)
        self._sync_header()
        guest._sync_header()

    def release(self, guest: PanelGroup, show: bool = True) -> None:
        if guest not in self._guests:
            return
        for key in guest._own:
            label, widget = self._take_page(key)
            guest._add_page(key, label, widget)
        guest._host = None
        self._guests.remove(guest)
        guest.toggleViewAction().setVisible(True)
        if show and self.isVisible():
            guest.show()
        self._sync_header()
        guest._sync_header()

    def release_all(self, show: bool = True) -> None:
        for guest in list(self._guests):
            self.release(guest, show)

    @staticmethod
    def of(widget: QWidget) -> PanelGroup | None:
        node = widget
        while node is not None:
            if isinstance(node, PanelGroup):
                return node
            node = node.parentWidget()
        return None
