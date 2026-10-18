from __future__ import annotations

WHEEL_FACTOR = 1.15


def install_navigation(view) -> None:
    interactor = view.iren.interactor
    style = interactor.GetInteractorStyle()

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

    style.AddObserver("RightButtonPressEvent", start_pan)
    style.AddObserver("RightButtonReleaseEvent", end_pan)
    style.AddObserver("MouseWheelForwardEvent", wheel(WHEEL_FACTOR))
    style.AddObserver("MouseWheelBackwardEvent", wheel(1 / WHEEL_FACTOR))
