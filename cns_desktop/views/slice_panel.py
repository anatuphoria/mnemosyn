from __future__ import annotations

import math
from contextlib import contextmanager

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from .. import slices
from ..state import AppState

NO_TEMPLATE = "No template in this atlas"
NO_LABELS = "No labelled volume in this atlas"
NOT_RAS = "Slices need a volume stored in RAS orientation"
COORDINATE = {"axial": "z", "coronal": "y", "sagittal": "x"}
EDGES = {"axial": ("A", "P", "L", "R"), "coronal": ("S", "I", "L", "R"),
         "sagittal": ("S", "I", "A", "P")}
ANCHORS = ((0.5, 0.0), (0.5, 1.0), (0.0, 0.5), (1.0, 0.5))


class SlicePanel(QWidget):
    hovered = Signal(str)

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        atlas = state.atlas
        self.labels = atlas.volumes[0] if atlas.volumes else None
        self.template = atlas.template
        self.colors = slices.color_table(atlas.structures)
        self.opacity = slices.DEFAULT_OPACITY
        self.image: np.ndarray | None = None
        self.index = 0
        self._centres = None
        self.tracts = atlas.tracts
        self.preferred: frozenset[int] = frozenset()
        self._tract_coords: dict[int, tuple[np.ndarray, ...]] = {}
        self._holds = 0
        self._redraw_wanted = False
        self.redraw_count = 0

        bar = QHBoxLayout()
        group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for axis in slices.AXES:
            button = QPushButton(axis.capitalize())
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, a=axis: self.set_axis(a))
            group.addButton(button)
            bar.addWidget(button)
            self.buttons[axis] = button
        self.centre_button = QPushButton("Centre on selection (C)")
        self.centre_button.clicked.connect(self.centre_on_selection)
        bar.addWidget(self.centre_button)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.position = QLabel()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(round(self.opacity * 100))
        self.note = QLabel(NO_TEMPLATE if self.template is None else "")

        self.view = pg.GraphicsLayoutWidget()
        self.box = self.view.addViewBox(lockAspect=True, invertY=True)
        self.box.setMenuEnabled(False)
        self.box.setMouseEnabled(x=False, y=False)
        self.item = pg.ImageItem(axisOrder="row-major")
        self.box.addItem(self.item)
        self.letters = [pg.TextItem(color="w", anchor=anchor) for anchor in ANCHORS]
        for letter in self.letters:
            self.box.addItem(letter)

        controls = QHBoxLayout()
        controls.addWidget(self.slider, 3)
        controls.addWidget(self.position)
        controls.addWidget(QLabel("Labels"))
        controls.addWidget(self.opacity_slider, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.view, 1)
        layout.addLayout(controls)
        layout.addWidget(self.note)

        self.slider.valueChanged.connect(self._on_slider)
        self.opacity_slider.valueChanged.connect(self._on_opacity)
        self.view.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.view.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        state.selection_changed.connect(lambda _id: self.redraw())
        state.visibility_changed.connect(lambda _ids: self.redraw())
        state.slice_changed.connect(self._on_slice_changed)
        state.focus_changed.connect(lambda _focus: self.redraw())

        if self.labels is not None and not slices.is_ras(self.labels.affine):
            self.labels = None
            self.note.setText(NOT_RAS)
        elif self.labels is None:
            self.note.setText(NO_LABELS)
        if self.labels is None:
            self.setEnabled(False)
            return
        self._on_slice_changed(state.slice_axis, state.slice_mm)

    def set_axis(self, axis: str) -> None:
        if self.labels is None or axis == self.state.slice_axis:
            return
        middle = self.labels.shape[slices.AXIS_INDEX[axis]] // 2
        self.state.set_slice(axis, slices.mm_for_index(self.labels.affine, axis, middle))

    def _on_slice_changed(self, axis: str, mm: float) -> None:
        if self.labels is None:
            return
        shape, affine = self.labels.shape, self.labels.affine
        index = slices.index_for_mm(affine, shape, axis, mm)
        snapped = slices.mm_for_index(affine, axis, index)
        if snapped != mm:
            self.state.set_slice(axis, snapped)
            return
        self.index = index
        with QSignalBlocker(self.slider):
            self.slider.setRange(0, slices.slice_count(shape, axis) - 1)
            self.slider.setValue(index)
        self.buttons[axis].setChecked(True)
        self.position.setText(f"{COORDINATE[axis]} = {snapped:+.0f} mm")
        self.redraw()

    def _on_slider(self, value: int) -> None:
        axis = self.state.slice_axis
        self.state.set_slice(axis, slices.mm_for_index(self.labels.affine, axis, value))

    def _on_opacity(self, value: int) -> None:
        self.opacity = value / 100
        self.redraw()

    @contextmanager
    def held(self):
        self._holds += 1
        try:
            yield
        finally:
            self._holds -= 1
            if not self._holds and self._redraw_wanted:
                self._redraw_wanted = False
                self.redraw()

    def redraw(self) -> None:
        if self._holds:
            self._redraw_wanted = True
            return
        if self.labels is None:
            return
        self.redraw_count += 1
        axis = self.state.slice_axis
        labels_2d = slices.extract(self.labels.data, self.labels.affine, axis, self.index)
        template_2d = None
        if self.template is not None:
            template_2d = slices.extract(self.template.data, self.template.affine, axis,
                                         self.index)
        size = len(self.colors)
        hidden = slices.mask_table(size, [i for i in self.state.geometry_ids
                                          if not self._shown(i)])
        chosen = self.state.highlighted_ids()
        selected = slices.mask_table(size, chosen)
        self.image = slices.compose(labels_2d, template_2d, self.colors, hidden, selected,
                                    self.opacity)
        self._draw_tracts(axis, set(chosen))
        self.item.setImage(self.image, autoLevels=False, levels=(0, 255))
        height, width = self.image.shape[:2]
        places = ((width / 2, 0), (width / 2, height), (0, height / 2), (width, height / 2))
        for letter, text, place in zip(self.letters, EDGES[axis], places):
            letter.setText(text)
            letter.setPos(*place)

    def _shown(self, structure_id: int) -> bool:
        return not self.state.is_hidden(structure_id) and self.state.in_focus(structure_id)

    def _tracts_ready(self) -> bool:
        return (self.tracts is not None and self.labels is not None
                and self.tracts.shape == tuple(self.labels.shape)
                and np.allclose(self.tracts.affine, self.labels.affine))

    def _coords(self, structure_id: int) -> tuple[np.ndarray, ...]:
        if structure_id not in self._tract_coords:
            flat = np.asarray(self.tracts.voxels(structure_id), dtype=np.int64)
            self._tract_coords[structure_id] = tuple(
                c.astype(np.int16) for c in np.unravel_index(flat, self.tracts.shape))
        return self._tract_coords[structure_id]

    def _draw_tracts(self, axis: str, chosen: set[int]) -> None:
        if not self._tracts_ready():
            return
        a = slices.AXIS_INDEX[axis]
        visible = [i for i in self.tracts.ids if self._shown(i)]
        for structure_id in sorted(visible, key=lambda i: -self.tracts.size(i)):
            coords = self._coords(structure_id)
            here = coords[a] == self.index
            if not here.any():
                continue
            rows, cols = slices.pixels_for_voxels(self.labels.shape, axis,
                                                  tuple(c[here] for c in coords))
            slices.draw_tract(self.image, rows, cols, self.colors[structure_id],
                              structure_id in chosen, self.opacity)

    def structure_at_pixel(self, row: int, col: int) -> int | None:
        if self.image is None or not (0 <= row < self.image.shape[0]
                                      and 0 <= col < self.image.shape[1]):
            return None
        voxel = slices.voxel_for_pixel(self.labels.shape, self.state.slice_axis, self.index,
                                       row, col)
        point = slices.world_for_voxel(self.labels.affine, voxel)
        if self._tracts_ready():
            visible = [i for i in self.tracts.tracts_at(point) if self._shown(i)]
            preferred = [i for i in visible if i in self.preferred]
            if preferred or visible:
                return (preferred or visible)[0]
        structure_id = self.state.atlas.label_at(point)
        if structure_id is None or not self._shown(structure_id):
            return None
        return structure_id

    def name_at_pixel(self, row: int, col: int) -> str:
        structure_id = self.structure_at_pixel(row, col)
        return "" if structure_id is None else self.state.atlas.get(structure_id).name

    def click_pixel(self, row: int, col: int) -> None:
        structure_id = self.structure_at_pixel(row, col)
        if structure_id is not None:
            self.state.select(structure_id)

    def label_centres(self):
        if self._centres is None and self.labels is not None:
            self._centres = slices.label_centres(self.labels.data)
        return self._centres

    def centre_on_selection(self) -> None:
        ids = self.state.highlighted_ids()
        if self.labels is None or not ids:
            return
        centre = slices.centre_from_table(self.label_centres(), self.labels.affine, ids)
        if centre is None and self._tracts_ready():
            coords = [self._coords(i) for i in ids if self.tracts.size(i)]
            if coords:
                voxel = [float(np.concatenate([c[a] for c in coords]).mean()) for a in range(3)]
                centre = slices.world_for_voxel(self.labels.affine, voxel)
        if centre is not None:
            axis = self.state.slice_axis
            shape, affine = self.labels.shape, self.labels.affine
            index = slices.index_for_mm(affine, shape, axis, centre[slices.AXIS_INDEX[axis]])
            self.state.set_slice(axis, slices.mm_for_index(affine, axis, index))

    def _pixel(self, scene_pos) -> tuple[int, int]:
        point = self.item.mapFromScene(scene_pos)
        return int(math.floor(point.y())), int(math.floor(point.x()))

    def _on_mouse_moved(self, scene_pos) -> None:
        self.hovered.emit(self.name_at_pixel(*self._pixel(scene_pos)))

    def _on_mouse_clicked(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_pixel(*self._pixel(event.scenePos()))
