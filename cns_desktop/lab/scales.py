from __future__ import annotations

import math

from cns_atlas.models import Curve, LabModel, Parameter
from cns_lab.expressions import compile_function

MULTIPLES = ((1 / 3, "⅓×"), (0.5, "½×"), (1.0, "normal"), (2.0, "2×"), (3.0, "3×"))
SAME = 1e-9


def _clamp(fraction: float) -> float:
    return min(1.0, max(0.0, fraction))


class Scale:
    def fraction(self, value: float) -> float:
        raise NotImplementedError

    def value(self, fraction: float) -> float:
        raise NotImplementedError

    def marks(self) -> list[tuple[float, str]]:
        raise NotImplementedError

    def badge(self, value: float, normal: float) -> str:
        return ""


class LinearScale(Scale):
    def __init__(self, low: float, high: float, normal: float) -> None:
        self.low, self.high, self.normal = low, high, normal

    def fraction(self, value: float) -> float:
        span = self.high - self.low
        return _clamp((value - self.low) / span) if span else 0.0

    def value(self, fraction: float) -> float:
        return self.low + _clamp(fraction) * (self.high - self.low)

    def marks(self) -> list[tuple[float, str]]:
        middle = self.fraction(self.normal)
        ends = [(0.0, f"{self.low:g}"), (1.0, f"{self.high:g}")]
        kept = [m for m in ends if abs(m[0] - middle) > SAME]
        return sorted([*kept, (middle, "normal")])


class LogScale(Scale):
    def __init__(self, low: float, high: float, normal: float) -> None:
        self.low, self.high, self.normal = low, high, normal
        self._span = math.log(high / low)

    def fraction(self, value: float) -> float:
        return _clamp(math.log(max(value, self.low) / self.low) / self._span)

    def value(self, fraction: float) -> float:
        return self.low * math.exp(_clamp(fraction) * self._span)

    def marks(self) -> list[tuple[float, str]]:
        return [(self.fraction(self.normal * times), label) for times, label in MULTIPLES
                if self.low * (1 - SAME) <= self.normal * times <= self.high * (1 + SAME)]

    def badge(self, value: float, normal: float) -> str:
        if not normal or abs(value / normal - 1) < SAME:
            return ""
        return f"{value / normal:.2g}× normal"


class ClockScale(Scale):
    def __init__(self, period: float) -> None:
        self.period = period

    def fraction(self, value: float) -> float:
        return _clamp(value / self.period)

    def value(self, fraction: float) -> float:
        return _clamp(fraction) * self.period

    def marks(self) -> list[tuple[float, str]]:
        return [(q / 4, self.text(self.period * q / 4)) for q in range(5)]

    @staticmethod
    def text(minutes: float) -> str:
        whole = round(minutes)
        return f"{whole // 60}:{whole % 60:02d}"


def scale_for(parameter: Parameter) -> Scale:
    if parameter.control == "rate":
        return LogScale(parameter.low, parameter.high, parameter.value)
    if parameter.control == "clock":
        return ClockScale(1440 if parameter.high >= 720 else 720)
    return LinearScale(parameter.low, parameter.high, parameter.value)


def curve_points(model: LabModel, curve: Curve, values: dict[str, float],
                 count: int) -> list[tuple[float, float]]:
    keys = tuple(p.key for p in model.parameters)
    function = compile_function({"_y": curve.expr}, ("x", *keys))
    settings = [values.get(p.key, p.value) for p in model.parameters]
    step = (curve.x_high - curve.x_low) / max(count - 1, 1)
    points = []
    for i in range(count):
        x = curve.x_low + i * step
        try:
            y = float(function(x, *settings)[0])
        except (ZeroDivisionError, OverflowError, ValueError):
            y = math.nan
        points.append((x, y))
    return points
