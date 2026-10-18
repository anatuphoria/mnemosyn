from __future__ import annotations

import numpy as np

WHEEL_FACTOR = 1.15
DEGREES_PER_PIXEL = 0.4
MAX_ELEVATION = 85.0
UP = (0.0, 0.0, 1.0)


def elevation_of(camera) -> float:
    direction = np.array(camera.GetDirectionOfProjection())
    return float(np.degrees(np.arcsin(np.clip(-direction[2], -1.0, 1.0))))


def turn(view, dx: float, dy: float) -> None:
    camera = view.renderer.GetActiveCamera()
    camera.SetViewUp(*UP)
    camera.Azimuth(-dx * DEGREES_PER_PIXEL)
    current = elevation_of(camera)
    target = np.clip(current - dy * DEGREES_PER_PIXEL, -MAX_ELEVATION, MAX_ELEVATION)
    camera.Elevation(target - current)
    camera.SetViewUp(*UP)
    view.renderer.ResetCameraClippingRange()


def install_navigation(view) -> None:
    interactor = view.iren.interactor
    style = interactor.GetInteractorStyle()
    drag = {"last": None}

    def start_turn(*_):
        drag["last"] = interactor.GetEventPosition()

    def end_turn(*_):
        drag["last"] = None

    def move(*_):
        if drag["last"] is None:
            style.OnMouseMove()
            return
        x, y = interactor.GetEventPosition()
        x0, y0 = drag["last"]
        drag["last"] = (x, y)
        turn(view, x - x0, y - y0)
        view.render()

    def start_pan(*_):
        x, y = interactor.GetEventPosition()
        style.FindPokedRenderer(x, y)
        style.StartPan()

    def end_pan(*_):
        style.EndPan()

    def wheel(factor: float):
        def handler(*_):
            x, y = interactor.GetEventPosition()
            view.zoom_at(x, y, factor)
            view.render()
        return handler

    style.AddObserver("LeftButtonPressEvent", start_turn)
    style.AddObserver("LeftButtonReleaseEvent", end_turn)
    style.AddObserver("MouseMoveEvent", move)
    style.AddObserver("RightButtonPressEvent", start_pan)
    style.AddObserver("RightButtonReleaseEvent", end_pan)
    style.AddObserver("MouseWheelForwardEvent", wheel(WHEEL_FACTOR))
    style.AddObserver("MouseWheelBackwardEvent", wheel(1 / WHEEL_FACTOR))
