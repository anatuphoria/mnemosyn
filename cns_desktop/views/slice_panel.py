from __future__ import annotations

import math

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
        if self.labels is None:
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

    def redraw(self) -> None:
        if self.labels is None:
            return
        axis = self.state.slice_axis
        labels_2d = slices.extract(self.labels.data, self.labels.affine, axis, self.index)
        template_2d = None
        if self.template is not None:
            template_2d = slices.extract(self.template.data, self.template.affine, axis,
                                         self.index)
        size = len(self.colors)
        hidden = slices.mask_table(size, [i for i in self.state.geometry_ids
                                          if self.state.is_hidden(i)])
        chosen = [] if self.state.selected is None else self.state.geometry_in(self.state.selected)
        selected = slices.mask_table(size, chosen)
        self.image = slices.compose(labels_2d, template_2d, self.colors, hidden, selected,
                                    self.opacity)
        self.item.setImage(self.image, autoLevels=False, levels=(0, 255))
        height, width = self.image.shape[:2]
        places = ((width / 2, 0), (width / 2, height), (0, height / 2), (width, height / 2))
        for letter, text, place in zip(self.letters, EDGES[axis], places):
            letter.setText(text)
            letter.setPos(*place)

    def structure_at_pixel(self, row: int, col: int) -> int | None:
        if self.image is None or not (0 <= row < self.image.shape[0]
                                      and 0 <= col < self.image.shape[1]):
            return None
        voxel = slices.voxel_for_pixel(self.labels.shape, self.state.slice_axis, self.index,
                                       row, col)
        structure_id = self.state.atlas.label_at(slices.world_for_voxel(self.labels.affine, voxel))
        if structure_id is None or self.state.is_hidden(structure_id):
            return None
        return structure_id

    def name_at_pixel(self, row: int, col: int) -> str:
        structure_id = self.structure_at_pixel(row, col)
        return "" if structure_id is None else self.state.atlas.get(structure_id).name

    def click_pixel(self, row: int, col: int) -> None:
        structure_id = self.structure_at_pixel(row, col)
        if structure_id is not None:
            self.state.select(structure_id)

    def centre_on_selection(self) -> None:
        if self.labels is None or self.state.selected is None:
            return
        ids = self.state.geometry_in(self.state.selected)
        centre = slices.centre_mm(self.labels.data, self.labels.affine, ids)
        if centre is not None:
            axis = self.state.slice_axis
            self.state.set_slice(axis, centre[slices.AXIS_INDEX[axis]])

    def _pixel(self, scene_pos) -> tuple[int, int]:
        point = self.item.mapFromScene(scene_pos)
        return int(math.floor(point.y())), int(math.floor(point.x()))

    def _on_mouse_moved(self, scene_pos) -> None:
        self.hovered.emit(self.name_at_pixel(*self._pixel(scene_pos)))

    def _on_mouse_clicked(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_pixel(*self._pixel(event.scenePos()))
