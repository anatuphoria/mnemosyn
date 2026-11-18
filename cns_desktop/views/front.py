from __future__ import annotations

from collections.abc import Iterable

from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer


class FrontLayer:
    def __init__(self, render_window, renderer, layer: int) -> None:
        self.renderer = vtkRenderer()
        self.renderer.SetLayer(layer)
        self.renderer.InteractiveOff()
        self.renderer.SetActiveCamera(renderer.GetActiveCamera())
        lights = renderer.GetLights()
        lights.InitTraversal()
        light = lights.GetNextItem()
        if light is not None:
            self.renderer.AutomaticLightCreationOff()
        while light is not None:
            self.renderer.AddLight(light)
            light = lights.GetNextItem()
        render_window.SetNumberOfLayers(max(layer + 1, render_window.GetNumberOfLayers()))
        render_window.AddRenderer(self.renderer)
        self._actors: dict[int, vtkActor] = {}
        self.shown: frozenset[int] = frozenset()

    def _actor(self, structure_id: int, block) -> vtkActor:
        actor = self._actors.get(structure_id)
        if actor is None:
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(block)
            mapper.ScalarVisibilityOff()
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.SetPickable(False)
            prop = actor.GetProperty()
            prop.SetInterpolationToGouraud()
            prop.SetSpecular(0.15)
            self.renderer.AddActor(actor)
            self._actors[structure_id] = actor
        return actor

    def show(self, ids: Iterable[int], blocks: dict, colors: dict) -> None:
        wanted = frozenset(ids)
        for structure_id in wanted:
            actor = self._actor(structure_id, blocks[structure_id])
            actor.GetProperty().SetColor(*colors[structure_id])
            actor.SetVisibility(True)
        for structure_id in self.shown - wanted:
            self._actors[structure_id].SetVisibility(False)
        self.shown = wanted

    def color_of(self, structure_id: int) -> tuple[float, float, float]:
        return tuple(self._actors[structure_id].GetProperty().GetColor())
