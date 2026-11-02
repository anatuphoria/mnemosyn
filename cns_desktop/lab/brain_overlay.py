from __future__ import annotations

import itertools
import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from vtkmodules.vtkCommonCore import VTK_FONT_FILE
from vtkmodules.vtkRenderingCore import vtkBillboardTextActor3D, vtkRenderer, vtkTextRenderer

from cns_desktop.design.fonts import FONTS
from cns_desktop.design.tokens import TYPE, rgb

from .labels import plain, ratio_text, removed_parts
from .viewport import StripCard

RAISED = rgb("raised")
LOWERED = rgb("lowered")
PLAIN = rgb("text")
LABEL_BACK = tuple(c / 255 for c in rgb("s1"))
LABEL_FONT = str(FONTS / "Inter-Medium.ttf")
ZERO = 1e-9
GAP = 3
NUDGE = 10


def label_layer(view) -> vtkRenderer:
    layer = getattr(view, "label_layer", None)
    if layer is None:
        layer = vtkRenderer()
        layer.SetLayer(view.outline.renderer.GetLayer() + 1)
        layer.InteractiveOff()
        layer.SetActiveCamera(view.renderer.GetActiveCamera())
        window = view.ren_win
        window.SetNumberOfLayers(max(layer.GetLayer() + 1, window.GetNumberOfLayers()))
        window.AddRenderer(layer)
        view.label_layer = layer
    return layer


class BrainOverlay:
    def __init__(self, view) -> None:
        self.view = view
        self.renderer = label_layer(view)
        self.actors: dict[int, vtkBillboardTextActor3D] = {}
        self.labels: dict[int, str] = {}
        self._boxes: dict[int, tuple[float, float, float, float]] = {}
        self._extents: dict = {}
        self._measure = vtkTextRenderer()
        view.renderer.AddObserver("StartEvent", lambda *_: self.arrange())

    def show(self, labels: dict[int, tuple[str, tuple[int, int, int]]],
             positions: dict | None = None, extents: dict | None = None) -> None:
        self._extents = dict(extents or {})
        for structure_id in set(self.actors) - set(labels):
            self.renderer.RemoveActor(self.actors.pop(structure_id))
        for structure_id, (text, color) in labels.items():
            actor = self.actors.get(structure_id)
            if actor is None:
                actor = vtkBillboardTextActor3D()
                where = (positions or {}).get(structure_id)
                actor.SetPosition(*(self.view.centre_of(structure_id) if where is None
                                    else where))
                style = actor.GetTextProperty()
                style.SetFontFamily(VTK_FONT_FILE)
                style.SetFontFile(LABEL_FONT)
                style.SetFontSize(TYPE["secondary"][0])
                style.SetBackgroundColor(*LABEL_BACK)
                style.SetBackgroundOpacity(0.9)
                style.SetFrame(False)
                actor.SetPickable(False)
                self.renderer.AddActor(actor)
                self.actors[structure_id] = actor
            actor.SetInput(text)
            actor.GetTextProperty().SetColor(*(c / 255 for c in color))
        self.labels = {k: v[0] for k, v in labels.items()}
        self.view._request_render()

    def clear(self) -> None:
        self.show({})

    def boxes(self) -> dict[int, tuple[float, float, float, float]]:
        return dict(self._boxes)

    def _size(self, actor) -> tuple[int, int]:
        bounds = [0, 0, 0, 0]
        dpi = self.view.ren_win.GetDPI()
        if self._measure.GetBoundingBox(actor.GetTextProperty(), actor.GetInput(), bounds, dpi):
            return bounds[1] - bounds[0], bounds[3] - bounds[2]
        size = actor.GetTextProperty().GetFontSize()
        return int(len(actor.GetInput()) * size * 0.6), int(size * 1.5)

    def arrange(self) -> None:
        renderer = self.view.renderer
        anchors = []
        for structure_id, actor in self.actors.items():
            renderer.SetWorldPoint(*actor.GetPosition(), 1.0)
            renderer.WorldToDisplay()
            x, y, _z = renderer.GetDisplayPoint()
            edge = x
            extent = self._extents.get(structure_id)
            if extent is not None:
                for corner in itertools.product(*zip(*extent)):
                    renderer.SetWorldPoint(*corner, 1.0)
                    renderer.WorldToDisplay()
                    edge = max(edge, renderer.GetDisplayPoint()[0])
            anchors.append((y, x, edge, structure_id, actor))
        placed: dict[int, tuple[float, float, float, float]] = {}
        for y, x, edge, structure_id, actor in sorted(anchors, key=lambda a: (-a[0], a[1])):
            width, height = self._size(actor)
            left, bottom = edge + NUDGE, y - height / 2
            moved = True
            while moved:
                moved = False
                for other in placed.values():
                    if (left < other[2] and other[0] < left + width
                            and bottom < other[3] and other[1] < bottom + height):
                        bottom = other[1] - GAP - height
                        moved = True
            actor.SetDisplayOffset(round(left - x), round(bottom - y))
            placed[structure_id] = (left, bottom, left + width, bottom + height)
        self._boxes = placed


def _mix(own, target, amount: float) -> tuple[float, float, float]:
    return tuple((o + (t / 255 - o) * amount) for o, t in zip(own, target))


class LabBrain:
    def __init__(self, document, view, viewport, state) -> None:
        self.document = document
        self.view = view
        self.viewport = viewport
        self.state = state
        self.overlay = BrainOverlay(view)
        self.active = False
        self._buttons: dict[str, StripCard] = {}
        self._syncing = False
        self.on_show_on_timeline = None
        self.on_show_in_atlas = None
        self._camera = None
        document.changed.connect(self.refresh)
        document.model_changed.connect(self._on_model)
        document.playhead_moved.connect(lambda _t: self.refresh())
        document.selection_changed.connect(self._from_lab)
        state.selection_changed.connect(self._from_brain)

    def _shaped(self) -> dict[str, list[int]]:
        atlas = self.state.atlas
        shaped = {}
        for part in self.document.model.parts:
            if part.structure is None or part.structure not in atlas:
                continue
            ids = [i for i in self.state.geometry_in(part.structure)
                   if atlas.has_mesh(i) and i in self.view.blocks]
            if ids:
                shaped[part.key] = ids
        return shaped

    def strip_keys(self) -> list[str]:
        shaped = self._shaped()
        return [p.key for p in self.document.model.parts if p.key not in shaped]

    def strip_button(self, key: str) -> StripCard:
        return self._buttons[key]

    def strip_menu(self, key: str) -> QMenu:
        menu = QMenu(self._buttons.get(key))
        part = self.document.model.part(key)
        if (part.structure is not None and part.structure in self.state.atlas
                and self.on_show_in_atlas is not None):
            menu.addAction(QAction("Show in the atlas", menu,
                                   triggered=lambda: self.on_show_in_atlas(key)))
        if self.on_show_on_timeline is not None:
            menu.addAction(QAction("Show on the timeline", menu,
                                   triggered=lambda: self.on_show_on_timeline(key)))
        return menu

    def brain_bounds(self) -> tuple[float, ...]:
        atlas = self.state.atlas
        brain = next((s for s in atlas.structures if s.name == "Brain" and s.parent is not None
                      and atlas.get(s.parent).parent is None), None)
        ids = [] if brain is None else [i for i in self.state.geometry_in(brain.id)
                                        if atlas.has_mesh(i) and i in self.view.blocks]
        if not ids:
            return tuple(self.view.scene_bounds)
        extents = [self.view.extent_of(i) for i in ids]
        low = np.min([e[0] for e in extents], axis=0)
        high = np.max([e[1] for e in extents], axis=0)
        return (low[0], high[0], low[1], high[1], low[2], high[2])

    def frame(self) -> None:
        self.view.set_home(self.brain_bounds(), self.viewport.strip_reserve())
        self.view.reset_view()

    def _on_model(self) -> None:
        if self.active:
            self._fill_strip()
            self.frame()

    def activate(self) -> None:
        self.active = True
        camera = self.view.renderer.GetActiveCamera()
        self._camera = (self.view.camera_position.to_list(), camera.GetViewAngle())
        self._fill_strip()
        self.state.set_focus([i for ids in self._shaped().values() for i in ids])
        self.refresh()
        self.frame()

    def deactivate(self) -> None:
        self.active = False
        self.view.set_home(None)
        if self._camera is not None:
            position, angle = self._camera
            self.view.camera_position = position
            self.view.renderer.GetActiveCamera().SetViewAngle(angle)
            self._camera = None
            self.view.render()
        self.view.set_lab_colors({i: None for ids in self._shaped().values() for i in ids})
        self.overlay.clear()
        self.state.set_focus(None)

    def _fill_strip(self) -> None:
        layout = self.viewport.strip.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._buttons = {}
        for key in self.strip_keys():
            button = StripCard()
            button.clicked.connect(lambda _=False, k=key: self.document.select(("part", k)))
            button.hover_changed.connect(self.viewport.place_strip)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, k=key, b=button: self.strip_menu(k).exec(b.mapToGlobal(pos)))
            layout.addWidget(button)
            button.show()
            self._buttons[key] = button
        self.viewport.place_strip()

    def _ratio(self, key: str) -> float:
        doc = self.document
        if doc.run is None or doc.normal is None:
            return 1.0
        mine, theirs = doc.run.at(key, doc.playhead), doc.normal.at(key, doc.playhead)
        if abs(theirs) < ZERO:
            return 1.0 if abs(mine) < ZERO else 3.0
        return max(mine / theirs, 0.0)

    def _text(self, part) -> tuple[str, tuple[int, int, int]]:
        if not part.values or self.document.run is None:
            return part.name, PLAIN
        if part.key in removed_parts(self.document):
            return f"{part.name} · removed", LOWERED
        key = part.values[0]
        value = self.document.simulator.values[key]
        ratio = self._ratio(key)
        colour = RAISED if ratio > 1.02 else LOWERED if ratio < 0.98 else PLAIN
        if value.relative or self.document.run is None:
            return f"{part.name} · {value.name} {ratio_text(ratio)}", colour
        shown = self.document.run.display(key, self.document.playhead)
        return f"{part.name} · {value.name} {plain(shown, 3)} {value.display_unit}", colour

    def _short(self, part, text: str) -> str:
        _title, _, detail = text.partition(" · ")
        if part.values:
            name = self.document.simulator.values[part.values[0]].name
            detail = detail.removeprefix(f"{name} ")
        detail = detail.removeprefix("= ")
        return f"{part.name} · {detail}" if detail else part.name

    def refresh(self) -> None:
        if not self.active:
            return
        shaped = self._shaped()
        before = self.viewport.strip.content_height()
        colors, labels, positions, extents = {}, {}, {}, {}
        atlas = self.state.atlas
        for part in self.document.model.parts:
            text, colour = self._text(part)
            if part.key in shaped:
                ids = shaped[part.key]
                labels[ids[0]] = (text, colour)
                positions[ids[0]] = sum(self.view.centre_of(i) for i in ids) / len(ids)
                bounds = [self.view.extent_of(i) for i in ids]
                extents[ids[0]] = (np.min([b[0] for b in bounds], axis=0),
                                   np.max([b[1] for b in bounds], axis=0))
                ratio = self._ratio(part.values[0]) if part.values else 1.0
                amount = min(1.0, abs(math.log(ratio)) / math.log(3)) if ratio > 0 else 1.0
                target = RAISED if ratio >= 1 else LOWERED
                for structure_id in ids:
                    if self.document.run is None:
                        colors[structure_id] = None
                        continue
                    own = tuple(c / 255 for c in atlas.get(structure_id).rgb_triplet)
                    colors[structure_id] = _mix(own, target, amount)
            elif part.key in self._buttons:
                button = self._buttons[part.key]
                button.setText(text.replace(" · ", "\n", 1), self._short(part, text))
                button.setToolTip(text)
                button.set_tone("raised" if colour == RAISED else
                                "lowered" if colour == LOWERED else "")
        self.view.set_lab_colors(colors)
        self.overlay.show(labels, positions, extents)
        if self._buttons and self.viewport.strip.content_height() != before:
            self.viewport.place_strip()

    def _from_lab(self, selection) -> None:
        if not self.active or self._syncing or not selection or selection[0] != "part":
            return
        part = self.document.model.part(selection[1])
        structure_id = part.structure if selection[1] in self._shaped() else None
        if structure_id is not None and self.state.selected != structure_id:
            self._syncing = True
            try:
                self.state.select(structure_id)
            finally:
                self._syncing = False

    def _from_brain(self, structure_id) -> None:
        if not self.active or self._syncing:
            return
        part = next((k for k, ids in self._shaped().items()
                     if structure_id in ids
                     or structure_id == self.document.model.part(k).structure), None)
        if part is not None:
            self._syncing = True
            try:
                self.document.select(("part", part))
            finally:
                self._syncing = False
