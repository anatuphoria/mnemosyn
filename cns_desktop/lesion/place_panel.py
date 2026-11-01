from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSlider, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from cns_atlas.lesions import (SIDES, Lesion, sphere, structure_lesion, territories,
                               territory_lesion)
from cns_desktop.design.theme import set_role
from cns_desktop.design.tokens import GAP, SIZE
from cns_desktop.design.widgets import SegmentedControl

TERRITORIES_MISSING = "Arterial territories are not in this build."
CORD_MISSING = "The spinal cord is not in this build."
STRUCTURE_HINT = "Click a structure in the slice or the 3D view to make it the lesion."
BRUSH_HINT = "Click or drag on the slice to paint; hold Ctrl to erase."
RADIUS = (2, 20)
START_RADIUS = 6


class PlacePanel(QWidget):
    def __init__(self, document, window, parent=None) -> None:
        super().__init__(parent)
        self.document, self.window = document, window
        atlas = document.atlas
        self.active = False
        self.side = SIDES[0]
        self.radius = float(START_RADIUS)
        self.stroke: dict[str, np.ndarray] | None = None
        self._erase = False
        self._sided = {s.id: s for s in territories(atlas)}
        tools = [("artery", "By artery")] if self._sided else []
        tools += [("brush", "Brush"), ("structure", "Structure")]
        self.tools = [key for key, _label in tools]
        self.tool_control = SegmentedControl(tools)
        self.tool_control.changed.connect(self.set_tool)
        self.side_control = SegmentedControl([(side, side.capitalize()) for side in SIDES])
        self.side_control.changed.connect(self.set_side)
        self.territory_tree = QTreeWidget()
        self.territory_tree.setHeaderHidden(True)
        self.territory_tree.itemClicked.connect(self._on_item)
        self._fill_tree()
        self.territory_note = self._note(TERRITORIES_MISSING)
        self.territory_note.setVisible(not self._sided)
        self.territory_tree.setVisible(bool(self._sided))
        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(*RADIUS)
        self.radius_slider.setValue(START_RADIUS)
        self.radius_slider.valueChanged.connect(self.set_radius)
        self.radius_label = QLabel()
        set_role(self.radius_label, "secondary")
        self.brush_hint = self._note(BRUSH_HINT)
        self.structure_hint = self._note(STRUCTURE_HINT)
        self.cord_note = self._note(CORD_MISSING)
        self.cord_note.setVisible("spine" not in {v.name for v in atlas.volumes})
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        self.clear_button = QPushButton("Clear")
        self.undo_button.clicked.connect(document.undo.undo)
        self.redo_button.clicked.connect(document.undo.redo)
        self.clear_button.clicked.connect(document.clear)
        for button in (self.undo_button, self.redo_button, self.clear_button):
            button.setFixedHeight(SIZE["control"])
        self.brush_row = QWidget()
        row = QHBoxLayout(self.brush_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(GAP["small"])
        row.addWidget(self.radius_slider, 1)
        row.addWidget(self.radius_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP["small"])
        for button in (self.undo_button, self.redo_button, self.clear_button):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SIZE["panel_pad"], SIZE["panel_pad"], SIZE["panel_pad"],
                                  SIZE["panel_pad"])
        layout.setSpacing(GAP["small"])
        for widget in (self.tool_control, self.side_control, self.territory_note,
                       self.territory_tree, self.brush_row, self.brush_hint, self.structure_hint):
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(self.cord_note)
        layout.addLayout(buttons)
        document.undo.canUndoChanged.connect(self.undo_button.setEnabled)
        document.undo.canRedoChanged.connect(self.redo_button.setEnabled)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)
        window.state.selection_changed.connect(self._on_selection)
        self.tool = ""
        self.set_tool(tools[0][0])
        self.set_radius(START_RADIUS)

    def _note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        set_role(label, "secondary")
        return label

    def _fill_tree(self) -> None:
        atlas = self.document.atlas
        concepts = [s for s in atlas.structures if s.kind == "territory" and s.side not in SIDES
                    and any(c in self._sided for c in atlas.children(s.id))]
        groups: dict[int, QTreeWidgetItem] = {}
        for concept in concepts:
            if concept.parent not in groups:
                parent = atlas.get(concept.parent)
                groups[concept.parent] = QTreeWidgetItem(self.territory_tree, [parent.name])
            item = QTreeWidgetItem(groups[concept.parent], [concept.name])
            item.setData(0, Qt.ItemDataRole.UserRole, concept.id)
        self.territory_tree.expandAll()

    def set_tool(self, tool: str) -> None:
        if tool not in self.tools:
            return
        self.cancel_stroke()
        self.tool = tool
        self.tool_control.set_current(tool)
        self.side_control.setVisible(tool == "artery")
        self.territory_tree.setVisible(tool == "artery" and bool(self._sided))
        self.brush_row.setVisible(tool == "brush")
        self.brush_hint.setVisible(tool == "brush")
        self.structure_hint.setVisible(tool == "structure")
        self._sync_brush()

    def set_side(self, side: str) -> None:
        self.side = side
        self.side_control.set_current(side)

    def set_radius(self, millimetres: float) -> None:
        self.radius = float(millimetres)
        if self.radius_slider.value() != round(millimetres):
            self.radius_slider.setValue(round(millimetres))
        self.radius_label.setText(f"{self.radius:g} mm")

    def activate(self, on: bool) -> None:
        self.active = on
        if not on:
            self.cancel_stroke()
        self._sync_brush()

    def _sync_brush(self) -> None:
        self.window.slices.brush = self.on_brush if self.active and self.tool == "brush" else None

    def _on_item(self, item: QTreeWidgetItem) -> None:
        concept = item.data(0, Qt.ItemDataRole.UserRole)
        if concept is not None:
            self.choose_territory(int(concept))

    def choose_territory(self, concept: int) -> None:
        atlas = self.document.atlas
        sided = next((self._sided[c] for c in atlas.children(concept)
                      if c in self._sided and self._sided[c].side == self.side), None)
        if sided is not None:
            self.document.set_lesion(territory_lesion(atlas, sided.id), sided.name)

    def _on_selection(self, structure_id) -> None:
        if self.active and self.tool == "structure" and structure_id is not None:
            atlas = self.document.atlas
            self.document.set_lesion(structure_lesion(atlas, structure_id),
                                     atlas.get(structure_id).name)

    def on_brush(self, kind: str, voxel, volume_name: str, erase: bool) -> None:
        if kind == "press":
            self.stroke = {name: mask.copy() for name, mask in self.document.lesion.masks.items()}
            self._erase = erase
        if self.stroke is None or volume_name not in self.stroke:
            return
        volume = next(v for v in self.document.atlas.volumes if v.name == volume_name)
        centre = (np.asarray(volume.affine) @ np.append(np.asarray(voxel, dtype=float), 1.0))[:3]
        ball = sphere(volume, centre, self.radius)
        mask = self.stroke[volume_name]
        self.stroke[volume_name] = mask & ~ball if self._erase else mask | ball
        self.window.slices.set_lesion(self.stroke)
        if kind == "release":
            lesion, self.stroke = Lesion(self.stroke), None
            self.document.set_lesion(lesion, "Erase" if self._erase else "Brush")

    def cancel_stroke(self) -> None:
        if self.stroke is not None:
            self.stroke = None
            self.window.slices.set_lesion(self.document.lesion.masks if self.active else {})
