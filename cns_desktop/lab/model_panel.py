from __future__ import annotations

import math

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QToolButton, QVBoxLayout, QWidget)

from cns_desktop.design.theme import set_role, set_tone
from cns_desktop.design.tokens import GAP, SIZE
from cns_desktop.design.widgets import SearchField
from cns_lab.relations import drivers, selection_name

from .controls import CurveGraph
from .labels import ratio_text
from .setting_group import SettingGroup
from .setting_row import SettingRow

SAME = 1e-12
OTHER = "Other"
MOVED = 3
MOVED_LEAST = 0.02
HINT = "Select a lane name, a part or an arrow to see the settings that shape it."
NOTHING_DIRECT = "No setting of this model acts on it directly."
NO_MATCH = "No setting matches."


def short_source(references) -> str:
    parts = []
    for ref in references:
        authors = [a.strip() for a in ref.authors.split(",") if a.strip()]
        first = authors[0] if authors else ref.title
        parts.append(f"{first}{' et al.' if len(authors) > 1 else ''} ({ref.year})")
    return "; ".join(parts)


def _quiet(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    set_role(label, "secondary")
    set_tone(label, "text3")
    label.setContentsMargins(SIZE["panel_pad"], GAP["tight"], SIZE["panel_pad"], GAP["tight"])
    return label


class ModelPanel(QWidget):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self._open: dict[str, dict[str, bool]] = {}
        self._context_key = None
        self._field_width = 0
        self.search = SearchField("Find a setting")
        self.search.textChanged.connect(lambda _text: self._filter())
        self.changed_only = QPushButton("Changed")
        self.changed_only.setCheckable(True)
        self.changed_only.setToolTip("Show only the settings you changed")
        self.changed_only.toggled.connect(lambda _on: self._filter())
        self.reset_all = QPushButton("Reset all")
        self.reset_all.clicked.connect(document.reset_values)
        self.body = QWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QVBoxLayout()
        layout.addLayout(top)
        top.setContentsMargins(GAP["small"], GAP["small"], GAP["small"], GAP["small"])
        top.setSpacing(GAP["small"])
        top.addWidget(self.search)
        buttons = QHBoxLayout()
        top.addLayout(buttons)
        buttons.setSpacing(GAP["small"])
        buttons.addWidget(self.changed_only)
        buttons.addStretch(1)
        buttons.addWidget(self.reset_all)
        layout.addWidget(self.scroll, 1)
        document.changed.connect(self.refresh)
        document.model_changed.connect(self.populate)
        document.selection_changed.connect(self._on_selection)
        document.playhead_moved.connect(self._on_playhead)
        self.populate()

    def _on_selection(self, _selection) -> None:
        self._update_context()

    def _on_playhead(self, _t: float) -> None:
        self._update_moved()

    def minimumSizeHint(self) -> QSize:
        return QSize(SIZE["panel_min"], super().minimumSizeHint().height())

    def _text(self, key: str) -> str:
        found = self.document.atlas.lab_text(self.document.model.key, key)
        return found[0] if found else ""

    def _make_row(self, p, with_control: bool = True) -> SettingRow:
        notes = (self._text(f"parameter.{p.key}.up"), self._text(f"parameter.{p.key}.down"))
        row = SettingRow(p, self._texts[p.key], notes, with_control)
        row.previewed.connect(self._preview)
        row.committed.connect(self._commit)
        row.reset_requested.connect(self.document.reset_value)
        return row

    def populate(self) -> None:
        model = self.document.model
        references = self.document.atlas.references
        self._rows: dict[str, SettingRow] = {}
        self._context_rows: list[SettingRow] = []
        self._graphs: dict[str, CurveGraph] = {}
        self._blocks: dict[str, QWidget] = {}
        self._groups: list[SettingGroup] = []
        self._group_of: dict[str, SettingGroup] = {}
        self._titles: list[str] = []
        self._texts: dict[str, tuple[str, str, str]] = {}
        self._context_key = None
        shown = [p for p in model.parameters if p.panel]
        for p in shown:
            source = short_source([references[k] for k in p.refs if k in references])
            self._texts[p.key] = (p.name, self._text(f"parameter.{p.key}.meaning"), source)
        self.body = QWidget()
        self.column = QVBoxLayout(self.body)
        self.column.setContentsMargins(0, 0, 0, GAP["small"])
        self.column.setSpacing(0)
        self.context = QWidget()
        self.context_rows = QVBoxLayout(self.context)
        self.context_rows.setContentsMargins(0, 0, 0, GAP["small"])
        self.context_rows.setSpacing(0)
        self.context_title = QLabel()
        set_role(self.context_title, "data")
        self.context_title.setContentsMargins(SIZE["panel_pad"], GAP["medium"], SIZE["panel_pad"],
                                              GAP["tight"])
        self.context_note = _quiet()
        self.moved = _quiet()
        self.context_rows.addWidget(self.context_title)
        self.context_rows.addWidget(self.context_note)
        self.context_list = QVBoxLayout()
        self.context_rows.addLayout(self.context_list)
        self.context_list.setSpacing(0)
        self.context_rows.addWidget(self.moved)
        self.hint = _quiet(HINT)
        self.no_match = _quiet(NO_MATCH)
        self.no_match.hide()
        self.column.addWidget(self.hint)
        self.column.addWidget(self.context)
        self.column.addWidget(self.no_match)
        order: list[str] = []
        for p in shown:
            if p.group not in order:
                order.append(p.group)
        order.sort(key=lambda g: g == "")
        remembered = self._open.setdefault(model.key, {})
        for name in order:
            title = self._text(f"group.{name}.name") if name else OTHER
            group = SettingGroup(title)
            group.set_open(remembered.get(name, True))
            group.toggled.connect(lambda open_, n=name: remembered.__setitem__(n, open_))
            self._titles.append(group.title)
            self._groups.append(group)
            placed: set[str] = set()
            for p in shown:
                if p.group != name or p.key in placed:
                    continue
                curve = model.curve_of(p.key) if p.control == "curve" else None
                if curve is not None:
                    group.add(self._curve_block(curve))
                    placed.update(curve.parameters)
                else:
                    row = self._make_row(p)
                    group.add(row)
                    self._rows[p.key] = row
                    placed.add(p.key)
            for key in placed:
                self._group_of[key] = group
            self.column.addWidget(group)
        self.column.addStretch(1)
        self.scroll.setWidget(self.body)
        inline = [row for row in self._rows.values() if row.inline]
        self._field_width = max((row.field.sizeHint().width() for row in inline), default=0)
        for row in inline:
            row.field.setFixedWidth(self._field_width)
        self.refresh()

    def _curve_block(self, curve) -> QWidget:
        model = self.document.model
        box = QWidget()
        stack = QVBoxLayout(box)
        stack.setContentsMargins(0, GAP["small"], 0, 0)
        stack.setSpacing(0)
        title = QLabel(curve.name)
        title.setWordWrap(True)
        title.setContentsMargins(SIZE["panel_pad"], 0, GAP["small"], GAP["tight"])
        stack.addWidget(title)
        graph = CurveGraph(model, curve, {})
        graph.previewed.connect(self._preview)
        graph.committed.connect(self._commit)
        holder = QHBoxLayout()
        stack.addLayout(holder)
        holder.setContentsMargins(SIZE["panel_pad"], 0, GAP["small"], 0)
        holder.addWidget(graph)
        for key in curve.parameters:
            row = self._make_row(model.parameter(key), with_control=False)
            stack.addWidget(row)
            self._rows[key] = row
            self._graphs[key] = graph
            self._blocks[key] = box
        return box

    @property
    def _spins(self) -> dict[str, QDoubleSpinBox]:
        return {key: row.field for key, row in self._rows.items()}

    @property
    def _labels(self) -> dict[str, QLabel]:
        return {key: row.label for key, row in self._rows.items()}

    def row(self, key: str) -> SettingRow:
        return self._rows[key]

    def spin(self, key: str) -> QDoubleSpinBox:
        return self._rows[key].field

    def reset_button(self, key: str) -> QToolButton:
        return self._rows[key].reset

    def control(self, key: str) -> QWidget:
        if key in self._graphs:
            return self._graphs[key]
        return self._rows[key].control

    def badge(self, key: str) -> QLabel:
        return self._rows[key].badge

    def note(self, key: str) -> QLabel:
        return self._rows[key].note

    def group_titles(self) -> list[str]:
        return list(self._titles)

    def groups(self) -> list[SettingGroup]:
        return list(self._groups)

    def row_text(self, key: str) -> tuple[str, str, str]:
        return self._texts[key]

    def context_keys(self) -> list[str]:
        return [row.key for row in self._context_rows]

    def context_heading(self) -> str:
        return self.context_title.text() if self.context.isVisibleTo(self) else ""

    def is_marked(self, key: str) -> bool:
        return key in self.document.experiment.value_map

    def _current(self, key: str) -> float:
        return self.document.experiment.value_map.get(key, self.document.model.parameter(key).value)

    def _rounded(self, key: str, value: float) -> float:
        return round(value, self._rows[key].field.decimals())

    def _commit(self, key: str, value: float) -> None:
        value = self._rounded(key, value)
        normal = self.document.model.parameter(key).value
        if abs(value - normal) <= SAME * max(1.0, abs(normal)):
            if self.is_marked(key):
                self.document.reset_value(key)
            else:
                self.refresh()
            return
        if abs(value - self._current(key)) > SAME:
            self.document.set_value(key, value)
        else:
            self.refresh()

    def _preview(self, key: str, value: float) -> None:
        value = self._rounded(key, value)
        for row in self._all_rows(key):
            row.show_value(value)

    def _all_rows(self, key: str) -> list[SettingRow]:
        return [r for r in (self._rows.get(key), *self._context_rows) if r and r.key == key]

    def refresh(self) -> None:
        edited = self.document.experiment.value_map
        model = self.document.model
        for row in (*self._rows.values(), *self._context_rows):
            row.set_value(edited.get(row.key, model.parameter(row.key).value), row.key in edited)
        for curve in model.curves:
            if curve.parameters and curve.parameters[0] in self._graphs:
                graph = self._graphs[curve.parameters[0]]
                graph.set_values(dict(edited), any(k in edited for k in curve.parameters))
        for group in self._groups:
            group.set_changed(sum(1 for k, g in self._group_of.items() if g is group and k in edited))
        count = sum(1 for key in edited if key in self._rows)
        self.changed_only.setText(f"Changed {count}" if count else "Changed")
        self.changed_only.setEnabled(bool(count) or self.changed_only.isChecked())
        self.reset_all.setEnabled(bool(edited))
        self._update_context()
        self._filter()

    def _context_wanted(self):
        selection = self.document.selection
        model = self.document.model
        if selection and selection[0] in ("value", "part", "link"):
            name = selection_name(model, selection)
            if name:
                return ("shapes", selection, name, drivers(model, selection))
        edited = tuple(k for k in self.document.experiment.value_map if k in self._rows)
        if edited:
            return ("changes", None, "", edited)
        return None

    def _update_context(self) -> None:
        wanted = self._context_wanted()
        if wanted != self._context_key:
            self._context_key = wanted
            self._build_context(wanted)
        self.hint.setVisible(wanted is None and bool(self._rows))
        self._update_moved()

    def _build_context(self, wanted) -> None:
        for row in self._context_rows:
            self.context_list.removeWidget(row)
            row.deleteLater()
        self._context_rows = []
        if wanted is None:
            self.context.hide()
            return
        kind, _selection, name, keys = wanted
        self.context_title.setText(f"SHAPES {name.upper()}" if kind == "shapes" else "YOUR CHANGES")
        self.context_note.setText(NOTHING_DIRECT if not keys else "")
        self.context_note.setVisible(not keys)
        model = self.document.model
        edited = self.document.experiment.value_map
        for key in keys:
            row = self._make_row(model.parameter(key))
            if row.inline:
                row.field.setFixedWidth(self._field_width)
            row.set_value(edited.get(key, model.parameter(key).value), key in edited)
            self.context_list.addWidget(row)
            self._context_rows.append(row)
        self.context.show()

    def _update_moved(self) -> None:
        doc = self.document
        wanted = self._context_key
        run, normal = getattr(doc, "run", None), getattr(doc, "normal", None)
        if wanted is None or wanted[0] != "changes" or run is None or normal is None:
            self.moved.hide()
            return
        t = doc.playhead
        found = []
        for value in doc.model.values:
            if value.lane is None:
                continue
            base = normal.at(value.key, t)
            if abs(base) < SAME:
                continue
            ratio = run.at(value.key, t) / base
            if ratio > 0 and abs(math.log(ratio)) > math.log(1 + MOVED_LEAST):
                found.append((abs(math.log(ratio)), value.name, ratio))
        found.sort(reverse=True)
        if not found:
            self.moved.setText(f"At {doc.scale.text(t)} every value is within 2% of healthy.")
        else:
            lines = [f"{name} {ratio_text(ratio)}" for _size, name, ratio in found[:MOVED]]
            self.moved.setText(f"At {doc.scale.text(t)}:\n" + "\n".join(lines))
        self.moved.show()

    def _filter(self) -> None:
        words = self.search.text()
        only = self.changed_only.isChecked()
        edited = self.document.experiment.value_map
        filtering = bool(words.strip()) or only
        visible = {key: row.matches(words) and (not only or key in edited)
                   for key, row in self._rows.items()}
        for key, row in self._rows.items():
            row.setVisible(visible[key])
        for key, box in self._blocks.items():
            box.setVisible(any(visible[k] for k, b in self._blocks.items() if b is box))
        any_shown = False
        for group in self._groups:
            shown = sum(1 for key, g in self._group_of.items() if g is group and visible.get(key))
            group.setVisible(shown > 0)
            group.force_open(filtering and shown > 0)
            any_shown = any_shown or shown > 0
        self.no_match.setVisible(filtering and not any_shown)
        self.context.setVisible(self._context_key is not None and not filtering)
        self.hint.setVisible(not filtering and self._context_key is None and bool(self._rows))
