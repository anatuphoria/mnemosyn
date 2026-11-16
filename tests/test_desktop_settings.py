import re

import pytest
from PySide6.QtCore import QSettings

from cns_atlas import Atlas
from cns_desktop import preferences
from cns_desktop.app import DISCLAIMER_KEY
from cns_desktop.design import stylesheet, theme, tokens
from cns_desktop.design.tokens import DARK, LIGHT, PALETTES, contrast
from cns_desktop.main_window import MainWindow
from cns_desktop.views.settings_dialog import NEXT_START
from cns_desktop.views.welcome import SEEN_KEY

pytestmark = pytest.mark.usefixtures("themed")
SURFACES = ("s0", "s1", "s2", "s3")
SIGNALS = ("accent_text", "edited", "raised", "lowered", "normal", "danger", "success")


@pytest.fixture
def stored(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def open_with(qapp, root, tmp_path, stored):
    window = MainWindow(Atlas.open(root), progress_path=tmp_path / "progress.sqlite",
                        settings=stored)
    window.show()
    qapp.processEvents()
    return window


def close(qapp, window):
    window.lab.document.undo.setClean()
    qapp.processEvents()
    window.close()


def test_the_light_theme_has_every_role_and_reaches_the_same_contrast():
    assert set(LIGHT) == set(DARK) and len(PALETTES["light"]) == len(PALETTES["dark"])
    for role in ("text", "text2"):
        for surface in SURFACES:
            assert contrast(LIGHT[role], LIGHT[surface]) >= 4.5, (role, surface)
    for role in SIGNALS:
        for surface in SURFACES:
            assert contrast(LIGHT[role], LIGHT[surface]) >= 3.0, (role, surface)
    for surface in ("s0", "s1", "s2"):
        assert contrast(LIGHT["text3"], LIGHT[surface]) >= 3.0, surface
        assert contrast(LIGHT["control"], LIGHT[surface]) >= 3.0, surface
    assert contrast("#ffffff", LIGHT["accent"]) >= 4.5
    for colour in PALETTES["light"]:
        assert contrast(colour, LIGHT["s1"]) >= 3.0, colour


def test_choosing_a_theme_changes_the_colours_and_the_stylesheet():
    dark = stylesheet.build()
    try:
        theme.choose("light")
        assert tokens.theme() == "light" and tokens.COLOURS == LIGHT
        assert tokens.DATA_PALETTE == list(PALETTES["light"])
        light = stylesheet.build()
        assert light != dark
        assert set(re.findall(r"#[0-9a-fA-F]{6}\b", light)) <= set(LIGHT.values())
        theme.choose("neon")
        assert tokens.theme() == "dark"
    finally:
        theme.choose("dark")
    assert tokens.COLOURS == DARK and stylesheet.build() == dark


def test_the_stored_theme_falls_back_to_dark(stored):
    assert preferences.stored_theme(None) == "dark" and preferences.stored_theme(stored) == "dark"
    preferences.store_theme(stored, "light")
    assert preferences.stored_theme(stored) == "light"
    stored.setValue(preferences.THEME_KEY, "neon")
    assert preferences.stored_theme(stored) == "dark"
    preferences.store_theme(stored, "neon")
    assert stored.value(preferences.THEME_KEY) == "neon"


def test_settings_is_in_the_file_menu_and_stores_the_theme_for_the_next_start(
        qapp, toy_lab_atlas, tmp_path, stored):
    window = open_with(qapp, toy_lab_atlas, tmp_path, stored)
    assert window.settings_action in window.topbar.menu("File").actions()
    box = window.show_settings()
    assert box.theme.currentData() == "dark" and box.theme_note.isHidden()
    box.theme.setCurrentIndex(box.theme.findData("light"))
    assert stored.value(preferences.THEME_KEY) == "light"
    assert not box.theme_note.isHidden() and box.theme_note.text() == NEXT_START
    assert tokens.theme() == "dark"
    box.theme.setCurrentIndex(box.theme.findData("dark"))
    assert box.theme_note.isHidden()
    box.accept()
    close(qapp, window)


def test_timeline_choices_apply_at_once_and_come_back_in_the_next_window(
        qapp, toy_lab_atlas, tmp_path, stored):
    window = open_with(qapp, toy_lab_atlas, tmp_path, stored)
    timeline = window.lab.timeline
    box = window.show_settings()
    assert all(b.isChecked() for b in box.timeline_boxes.values())
    box.timeline_boxes["show_overview"].setChecked(False)
    box.timeline_boxes["compare"].setChecked(False)
    assert not timeline.show_overview and not timeline.compare_on and timeline.show_guides
    box.accept()
    timeline._set_guides(False)
    close(qapp, window)
    again = open_with(qapp, toy_lab_atlas, tmp_path, stored)
    timeline = again.lab.timeline
    assert not timeline.show_overview and not timeline.compare_on and not timeline.show_guides
    assert timeline.show_hover
    box = again.show_settings()
    assert not box.timeline_boxes["show_guides"].isChecked()
    box.accept()
    close(qapp, again)


def test_the_start_choices_write_the_keys_the_start_reads(qapp, toy_lab_atlas, tmp_path, stored):
    stored.setValue(DISCLAIMER_KEY, True)
    stored.setValue(SEEN_KEY, True)
    window = open_with(qapp, toy_lab_atlas, tmp_path, stored)
    box = window.show_settings()
    assert not box.disclaimer.isChecked() and not box.welcome.isChecked()
    box.disclaimer.setChecked(True)
    box.welcome.setChecked(True)
    assert not stored.value(DISCLAIMER_KEY, True, type=bool)
    assert not stored.value(SEEN_KEY, True, type=bool)
    box.accept()
    close(qapp, window)


def test_settings_work_without_a_place_to_store_them(qapp, toy_lab_atlas, tmp_path):
    window = open_with(qapp, toy_lab_atlas, tmp_path, None)
    box = window.show_settings()
    assert not box.disclaimer.isEnabled() and not box.welcome.isEnabled()
    box.timeline_boxes["show_hover"].setChecked(False)
    assert not window.lab.timeline.show_hover
    box.theme.setCurrentIndex(box.theme.findData("light"))
    box.accept()
    close(qapp, window)
