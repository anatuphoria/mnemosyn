from __future__ import annotations

from functools import cache
from string import Template

from cns_desktop.design import icons
from cns_desktop.design.tokens import COLOURS, RADIUS, SIZE, TYPE


def _rgba(name: str, alpha: float) -> str:
    value = COLOURS[name].lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {round(alpha * 255)})"


def _roles() -> str:
    colours = {"title": "text", "heading": "text", "body": "text", "label": "text",
               "secondary": "text2", "data": "text2"}
    rules = []
    for role, (size, _line, weight) in TYPE.items():
        rules.append(f'*[role="{role}"] {{ font-size: {size}px; font-weight: {weight}; '
                     f'color: {COLOURS[colours[role]]}; background: transparent; }}')
    for name in ("text2", "text3", "accent_text", "edited", "raised", "lowered", "normal",
                 "danger", "success"):
        rules.append(f'*[tone="{name}"] {{ color: {COLOURS[name]}; }}')
    return "\n".join(rules)


SHEET = Template("""
QWidget { color: $text; background: $s1; selection-background-color: $accent;
          selection-color: white; }
QMainWindow, QDialog { background: $s0; }
QMainWindow::separator { background: $line; width: 1px; height: 1px; }
QMainWindow::separator:hover { background: $accent; }
QDockWidget { color: $text; }
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: $line; }

QScrollArea, QAbstractScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle { background: $s3; border-radius: 4px; min-height: 24px; min-width: 24px;
                     margin: 2px; }
QScrollBar::handle:hover { background: $control; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: $s0; color: $text; border: 1px solid $control; border-radius: ${r_control}px;
    selection-background-color: $accent; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    min-height: ${inner}px; max-height: ${inner}px; padding: 0 8px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: $text3; border-color: $line; }
*[edited="true"] { border: 1px solid $edited; }
QSpinBox, QDoubleSpinBox { padding-right: 20px; min-height: ${spin}px; max-height: ${spin}px; }
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::down-button { width: 18px; border: none; background: transparent; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url($up); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url($down); width: 10px; height: 10px; }
QComboBox { padding-right: 24px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url($down); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: $s3; border: 1px solid $line; padding: 4px;
    selection-background-color: $s2; outline: none; }

QPushButton { min-height: ${inner}px; max-height: ${inner}px; padding: 0 12px;
    background: $s3; color: $text; border: 1px solid $control; border-radius: ${r_control}px;
    font-weight: 500; }
QPushButton:hover { background: $s2; }
QPushButton:pressed { background: $s0; }
QPushButton:focus { border: 1px solid $accent; }
QPushButton:checked { background: $s3; border-color: $accent; }
QPushButton:disabled { color: $text3; border-color: $line; background: $s1; }
QPushButton[variant="primary"] { background: $accent; color: white; border: 1px solid $accent; }
QPushButton[variant="primary"]:hover { background: $accent_text; border-color: $accent_text; }
QPushButton[variant="ghost"] { background: transparent; border: 1px solid transparent;
    color: $text2; }
QPushButton[variant="ghost"]:hover { background: $s2; color: $text; }
QPushButton[variant="ghost"]:focus { border: 1px solid $accent; }

QToolButton { background: transparent; color: $text2; border: 1px solid transparent;
    border-radius: ${r_control}px; padding: 0; }
QToolButton:hover { background: $s2; color: $text; }
QToolButton:pressed { background: $s0; }
QToolButton:checked { background: $s3; color: $text; }
QToolButton:focus { border: 1px solid $accent; }
QToolButton:disabled { color: $text3; }
QToolButton::menu-indicator { image: none; width: 0; }

QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator, QAbstractItemView::indicator {
    width: 12px; height: 12px; border: 1px solid $control; background: $s0; border-radius: 3px; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked,
QAbstractItemView::indicator:checked { background: $accent; border-color: $accent; }
QCheckBox::indicator:indeterminate, QAbstractItemView::indicator:indeterminate {
    background: $s3; border-color: $accent; }
QCheckBox:focus { color: $text; }

QTreeView, QListView, QTableView { background: $s1; border: none; outline: none;
    show-decoration-selected: 1; }
QTreeView::item, QListView::item { min-height: ${row}px; padding: 0 4px;
    border-left: 2px solid transparent; }
QTreeView::item:hover, QListView::item:hover { background: $s2; }
QTreeView::item:selected, QListView::item:selected { background: $sel;
    border-left: 2px solid $accent; color: $text; }
QTreeView::branch { background: transparent; }
QTreeView::branch:selected { background: $sel; }
QHeaderView::section { background: $s1; color: $text2; border: none;
    border-bottom: 1px solid $line; padding: 4px 8px; }

QTextBrowser { background: $s1; border: none; }

QSlider::groove:horizontal { height: 4px; background: $s3; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: $text; border: 1px solid $control; }
QSlider::handle:horizontal:focus { border: 1px solid $accent; }
QProgressBar { background: $s3; border: none; border-radius: 3px; max-height: 6px;
    color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

QMenuBar { background: transparent; color: $text2; }
QMenuBar::item { background: transparent; padding: 4px 8px; border-radius: ${r_small}px; }
QMenuBar::item:selected { background: $s2; color: $text; }
QMenu { background: $s3; border: 1px solid $line; border-radius: ${r_control}px; padding: 4px; }
QMenu::item { padding: 4px 24px 4px 12px; border-radius: ${r_small}px; color: $text; }
QMenu::item:selected { background: $s2; }
QMenu::item:disabled { color: $text3; }
QMenu::separator { height: 1px; background: $line; margin: 4px 8px; }
QMenu::indicator { width: 12px; height: 12px; }
QToolTip { background: $s3; color: $text; border: 1px solid $line; padding: 4px 8px; }

QStatusBar { background: $s1; color: $text2; border-top: 1px solid $line; }
QStatusBar::item { border: none; }
QStatusBar QLabel { background: transparent; }

QTabWidget::pane { border: none; border-top: 1px solid $line; }
QTabBar::tab { background: transparent; color: $text2; padding: 4px 12px; border: none;
    border-radius: ${r_small}px; margin: 4px 2px; }
QTabBar::tab:selected { background: $s3; color: $text; }
QTabBar::tab:hover { color: $text; }

QFrame[segmented="true"] { background: $s0; border: 1px solid $line;
    border-radius: ${r_control}px; }
QFrame[segmented="true"]:focus { border: 1px solid $accent; }
QToolButton[segment="true"] { background: transparent; color: $text2; border: none;
    border-radius: ${r_small}px; padding: 0 10px; font-weight: 500; }
QToolButton[segment="true"]:hover { color: $text; }
QToolButton[segment="true"]:checked { background: $s3; color: $text; }
QFrame[panelheader="true"] { background: $s1; border: none; border-bottom: 1px solid $line; }
QFrame[card="true"] { background: $s2; border: 1px solid $line; border-radius: ${r_panel}px; }
QFrame[card="true"] QLabel { background: transparent; }
QToolButton[card="true"] { background: $s2; border: 1px solid $line; border-radius: ${r_panel}px;
    padding: 8px 12px; color: $text; text-align: left; }
QToolButton[card="true"]:hover { background: $s3; }
QToolButton[card="true"][tone="raised"] { color: $raised; }
QToolButton[card="true"][tone="lowered"] { color: $lowered; }
QScrollArea[strip="true"], QScrollArea[strip="true"] > QWidget > QWidget { background: $s0; }
QLabel[chip="true"] { background: $s2; border: 1px solid $line; border-radius: ${r_small}px;
    padding: 0 6px; font-size: 11px; font-weight: 500; }
QLabel[keycap="true"] { background: $s3; border: 1px solid $line; border-radius: ${r_small}px;
    padding: 0 4px; }

QFrame[topbar="true"] { background: $s1; border: none; border-bottom: 1px solid $line; }
QFrame[topbar="true"] > QWidget, QFrame[topbar="true"] > QMenuBar { background: transparent; }
QFrame[topbar="true"] QComboBox { background: $s0; }
QFrame[vline="true"] { background: transparent; border: none; border-left: 1px solid $line;
    margin: 10px 6px; }
QStatusBar QLabel[keycap="true"] { background: $s3; }

$roles
""")


@cache
def build() -> str:
    values = dict(COLOURS)
    values.update(
        r_small=RADIUS["small"], r_control=RADIUS["control"], r_panel=RADIUS["panel"],
        inner=SIZE["control"] - 2, spin=SIZE["control"] - 5, row=SIZE["row"], status=SIZE["status"],
        sel=_rgba("accent", 0.15), roles=_roles(),
        down=icons.file("chevron-down").as_posix(), up=icons.file("chevron-up").as_posix(),
    )
    return SHEET.substitute(values).strip() + "\n"
