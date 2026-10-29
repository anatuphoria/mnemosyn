from __future__ import annotations

import math

from PySide6.QtWidgets import QToolButton
from vtkmodules.vtkRenderingCore import vtkBillboardTextActor3D

RAISED = (224, 138, 90)
LOWERED = (111, 160, 255)
ZERO = 1e-9


class BrainOverlay:
    def __init__(self, view) -> None:
        self.view = view
        self.actors: dict[int, vtkBillboardTextActor3D] = {}
        self.labels: dict[int, str] = {}

    def show(self, labels: dict[int, tuple[str, tuple[int, int, int]]]) -> None:
        for structure_id in set(self.actors) - set(labels):
            self.view.renderer.RemoveActor(self.actors.pop(structure_id))
        for structure_id, (text, color) in labels.items():
            actor = self.actors.get(structure_id)
            if actor is None:
                actor = vtkBillboardTextActor3D()
                actor.SetPosition(*self.view.centre_of(structure_id))
                actor.GetTextProperty().SetFontSize(14)
                actor.GetTextProperty().SetBackgroundColor(0.09, 0.09, 0.11)
                actor.GetTextProperty().SetBackgroundOpacity(0.8)
                actor.SetPickable(False)
                self.view.renderer.AddActor(actor)
                self.actors[structure_id] = actor
            actor.SetInput(text)
            actor.GetTextProperty().SetColor(*(c / 255 for c in color))
        self.labels = {k: v[0] for k, v in labels.items()}
        self.view._request_render()

    def clear(self) -> None:
        self.show({})


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
        self._buttons: dict[str, QToolButton] = {}
        self._syncing = False
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(lambda _t: self.refresh())
        document.selection_changed.connect(self._from_lab)
        state.selection_changed.connect(self._from_brain)

    def _shaped(self) -> dict[str, int]:
        atlas = self.state.atlas
        return {p.key: p.structure for p in self.document.model.parts
                if p.structure is not None and p.structure in atlas
                and atlas.has_mesh(p.structure) and p.structure in self.view.blocks}

    def strip_keys(self) -> list[str]:
        shaped = self._shaped()
        return [p.key for p in self.document.model.parts if p.key not in shaped]

    def strip_button(self, key: str) -> QToolButton:
        return self._buttons[key]

    def activate(self) -> None:
        self.active = True
        self._fill_strip()
        self.state.set_focus(self._shaped().values())
        self.refresh()

    def deactivate(self) -> None:
        self.active = False
        self.view.set_lab_colors({i: None for i in self._shaped().values()})
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
            button = QToolButton()
            button.setAutoRaise(True)
            button.clicked.connect(lambda _=False, k=key: self.document.select(("part", k)))
            layout.addWidget(button)
            self._buttons[key] = button
        layout.addStretch(1)

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
            return part.name, (216, 216, 224)
        key = part.values[0]
        value = self.document.simulator.values[key]
        ratio = self._ratio(key)
        colour = RAISED if ratio > 1.02 else LOWERED if ratio < 0.98 else (216, 216, 224)
        if value.relative or self.document.run is None:
            arrow = "↑" if ratio > 1.02 else "↓" if ratio < 0.98 else "="
            return f"{part.name} · {value.name} {arrow} {ratio:.2g}×", colour
        shown = self.document.run.display(key, self.document.playhead)
        return f"{part.name} · {value.name} {shown:.3g} {value.display_unit}", colour

    def refresh(self) -> None:
        if not self.active:
            return
        shaped = self._shaped()
        colors, labels = {}, {}
        atlas = self.state.atlas
        for part in self.document.model.parts:
            text, colour = self._text(part)
            if part.key in shaped:
                structure_id = shaped[part.key]
                own = tuple(c / 255 for c in atlas.get(structure_id).rgb_triplet)
                if self.document.run is None:
                    colors[structure_id] = None
                    labels[structure_id] = (text, colour)
                    continue
                ratio = self._ratio(part.values[0]) if part.values else 1.0
                amount = min(1.0, abs(math.log(ratio)) / math.log(3)) if ratio > 0 else 1.0
                target = RAISED if ratio >= 1 else LOWERED
                colors[structure_id] = _mix(own, target, amount)
                labels[structure_id] = (text, colour)
            elif part.key in self._buttons:
                self._buttons[part.key].setText(text)
        self.view.set_lab_colors(colors)
        self.overlay.show(labels)

    def _from_lab(self, selection) -> None:
        if not self.active or self._syncing or not selection or selection[0] != "part":
            return
        structure_id = self._shaped().get(selection[1])
        if structure_id is not None and self.state.selected != structure_id:
            self._syncing = True
            try:
                self.state.select(structure_id)
            finally:
                self._syncing = False

    def _from_brain(self, structure_id) -> None:
        if not self.active or self._syncing:
            return
        part = next((k for k, s in self._shaped().items() if s == structure_id), None)
        if part is not None:
            self._syncing = True
            try:
                self.document.select(("part", part))
            finally:
                self._syncing = False
