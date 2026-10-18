from __future__ import annotations

from collections.abc import Iterable

from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer
from vtkmodules.vtkRenderingOpenGL2 import vtkOutlineGlowPass, vtkRenderStepsPass

GLOW_COLOR = (1.0, 0.95, 0.6)
GLOW_INTENSITY = 4.0


class OutlineLayer:
    def __init__(self, render_window, renderer) -> None:
        self.renderer = vtkRenderer()
        self.renderer.SetLayer(1)
        self.renderer.InteractiveOff()
        self.renderer.SetActiveCamera(renderer.GetActiveCamera())
        render_window.SetNumberOfLayers(max(2, render_window.GetNumberOfLayers()))
        render_window.AddRenderer(self.renderer)
        self._steps = vtkRenderStepsPass()
        self._glow = vtkOutlineGlowPass()
        self._glow.SetDelegatePass(self._steps)
        self._glow.SetOutlineIntensity(GLOW_INTENSITY)
        self.renderer.SetPass(self._glow)
        self._actors: dict[int, vtkActor] = {}
        self.shown: frozenset[int] = frozenset()

    def add_blocks(self, ids: list[int], blocks: list) -> None:
        for structure_id, block in zip(ids, blocks):
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(block)
            mapper.ScalarVisibilityOff()
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.SetPickable(False)
            actor.SetVisibility(structure_id in self.shown)
            prop = actor.GetProperty()
            prop.SetColor(*GLOW_COLOR)
            prop.LightingOff()
            self.renderer.AddActor(actor)
            self._actors[structure_id] = actor

    def show(self, ids: Iterable[int]) -> None:
        wanted = frozenset(ids)
        for structure_id in (wanted ^ self.shown) & self._actors.keys():
            self._actors[structure_id].SetVisibility(structure_id in wanted)
        self.shown = wanted & self._actors.keys()
