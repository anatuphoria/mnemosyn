from __future__ import annotations


from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QCheckBox,
                               QMessageBox)


from cns_atlas import DISCLAIMER

from .design import dialogs, widgets
from .views.about_dialog import DOWNLOAD_URL, HANDBOOK_URL, PROBLEM_URL, AboutDialog
from .views.welcome import SEEN_KEY, WelcomeTour

__all__ = ["DOWNLOAD_URL", "HANDBOOK_URL", "PROBLEM_URL", "WindowMenus"]


class WindowMenus:
    def _add_actions(self) -> None:
        view = self.topbar.menu("View")

        def action(text: str, key: str, slot, menu=view) -> QAction:
            act = QAction(text, self, shortcut=QKeySequence(key), triggered=slot)
            act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.addAction(act)
            menu.addAction(act)
            self.shortcuts[text] = act
            return act

        action("Hide", "H", self._hide_selected)
        action("Isolate", "I", self._isolate_selected)
        action("Show all", "U", self.state.show_all)
        view.addSeparator()
        action("Tracts", "T", self.state.toggle_tracts)
        view.addSeparator()
        action("Reset view", "R", self.view.reset_view)
        action("Frame selection", "F", self.frame)
        action("Centre slice", "C", self.slices.centre_on_selection)
        focus_filter = QAction(self, shortcut=QKeySequence.StandardKey.Find,
                               triggered=lambda: self.tree.filter_box.setFocus())
        self.addAction(focus_filter)
        study = self.topbar.menu("Study")
        action("Start quiz", "Q", self.open_quiz_setup, study)
        study.addAction(QAction("Progress", self, triggered=self.show_progress))
        study.addSeparator()
        study.addAction(QAction("Back up progress…", self, triggered=self.ask_backup))
        self.reset_action = QAction("Reset progress…", self, triggered=self.ask_reset)
        study.addAction(self.reset_action)
        icons = {"Hide": "eye-off", "Isolate": "scan", "Show all": "eye", "Tracts": "waypoints",
                 "Start quiz": "graduation-cap"}

        def buttons(names):
            return [None if name is None else widgets.icon_button(self.shortcuts[name],
                                                                  icons[name])
                    for name in names]

        full = ("Hide", "Isolate", "Show all", None, "Tracts", None, "Start quiz")
        self.topbar.add_group("Explore", buttons(full))
        self.topbar.add_group("Slices", buttons(full))
        self.topbar.add_group("Pathways", [*self.pathways.controls(), None,
                                           *buttons(("Tracts", None, "Start quiz"))])
        for name, icon in (("Frame selection", "maximize"), ("Reset view", "rotate-ccw")):
            self.viewport.add_tool(widgets.icon_button(self.shortcuts[name], icon))
        self.viewport.add_tool(buttons(("Tracts",))[0])
        leave = QAction("Close route", self, shortcut=QKeySequence("Esc"),
                        triggered=self.pathways.leave)
        leave.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        leave.setEnabled(False)
        self.addAction(leave)
        self.shortcuts["Close route"] = leave
        for name, key, slot in (("Play or pause", "Space", self.pathways.toggle_play),
                                ("Back", "Left", self.pathways.back),
                                ("Next", "Right", self.pathways.next)):
            route_key = QAction(name, self, shortcut=QKeySequence(key), triggered=slot)
            route_key.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            route_key.setEnabled(False)
            self.addAction(route_key)
            self.shortcuts[name] = route_key

    def _add_window_menu(self) -> None:
        self.window_menu = self.topbar.menu("Window")
        for dock in (self.structures_group, self.routes_group, self.step_group,
                     self.slices_group, self.info_group, self.activity_group):
            self.window_menu.addAction(dock.toggleViewAction())
        self.window_separator = self.window_menu.addSeparator()
        self.window_menu.addAction(QAction("Reset layout", self,
                                           triggered=lambda: self.workspaces.reset()))

    def _add_help_menu(self) -> None:
        help_menu = self.topbar.menu("Help")
        about = QAction("About Mnemosyn", self, shortcut=QKeySequence("F1"),
                        triggered=self.show_about)
        about.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.addAction(about)
        help_menu.addAction(about)
        self.shortcuts["About"] = about
        self.welcome_action = QAction("Welcome tour", self, triggered=self.show_welcome)
        help_menu.addAction(self.welcome_action)
        for text, target in (("Handbook on the website", HANDBOOK_URL),
                             ("Check for a newer version", DOWNLOAD_URL),
                             ("Report a problem", PROBLEM_URL)):
            help_menu.addAction(QAction(text, self, triggered=lambda _checked=False, u=target:
                                        self.open_url(QUrl(u))))
        help_menu.addSeparator()
        help_menu.addAction(QAction("Open data folder", self, triggered=self.open_data_folder))
        self.help_menu = help_menu

    def _add_settings_action(self) -> None:
        menu = self.topbar.menu("File")
        menu.addSeparator()
        self.settings_action = QAction("Settings…", self, shortcut=QKeySequence("Ctrl+,"),
                                       triggered=lambda _checked=False: self.show_settings())
        self.settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        menu.addAction(self.settings_action)

    def show_settings(self):
        from .views.settings_dialog import SettingsDialog

        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()
        return self.settings_dialog

    def show_welcome(self) -> WelcomeTour | None:
        if self.quiz_active or self.workspaces.locked:
            return None
        if self.pathway_active:
            self.pathways.leave()
        if self.settings is not None:
            self.settings.setValue(SEEN_KEY, True)
        self.welcome = WelcomeTour(self)
        self.welcome.show()
        return self.welcome

    def welcome_if_new(self) -> None:
        if self.settings is not None and not self.settings.value(SEEN_KEY, False, type=bool):
            self.show_welcome()

    def open_url(self, url: QUrl) -> None:
        QDesktopServices.openUrl(url)

    def open_data_folder(self) -> None:
        folder = self.progress_path.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        self.open_url(QUrl.fromLocalFile(str(folder)))

    def show_about(self) -> None:
        AboutDialog(self.state.atlas, self).exec()

    def show_disclaimer(self) -> QMessageBox:
        box = dialogs.message_box(self, "info", "Before you start", DISCLAIMER)
        box.setCheckBox(QCheckBox("Don't show this again", box))
        box.open()
        return box
