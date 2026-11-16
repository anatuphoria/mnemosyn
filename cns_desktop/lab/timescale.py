from __future__ import annotations

from dataclasses import dataclass

DAY = 1440.0


def coarse_text(minutes: float) -> str:
    minutes = round(minutes)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h" if hours else f"{days} d"
    return f"{hours} h {mins} min" if mins else f"{hours} h"


def fine_text(minutes: float) -> str:
    seconds = round(minutes * 60)
    hours, rest = divmod(seconds, 3600)
    mins, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {mins} min" if mins else f"{hours} h"
    if mins and secs:
        return f"{mins} min {secs} s"
    return f"{mins} min" if mins or not secs else f"{secs} s"


@dataclass(frozen=True)
class TimeScale:
    lengths: tuple[tuple[str, float], ...]
    default: float
    shortest: float
    min_span: float
    gap: float
    unit: str
    unit_minutes: float
    ruler: tuple[float, ...]
    fine: bool
    least: float

    def text(self, minutes: float) -> str:
        return fine_text(minutes) if self.fine else coarse_text(minutes)

    def snap(self, t: float, span: float) -> float:
        if self.fine:
            step = 1 / 60 if span < 10 else 0.25
        else:
            step = 1.0 if span < 2 * DAY else 15.0
        return round(t / step) * step


HOURS = TimeScale(
    (("6 h", 360.0), ("1 d", DAY), ("2 d", 2 * DAY), ("3 d", 3 * DAY), ("5 d", 5 * DAY),
     ("1 w", 7 * DAY), ("4 w", 28 * DAY), ("8 w", 56 * DAY)),
    DAY, 60.0, 30.0, 60.0, "h", 60.0, (30, 60, 120, 240, 360, 720, 1440, 2880, 10080), False, 1.0)
MINUTES = TimeScale(
    (("2 min", 2.0), ("5 min", 5.0), ("10 min", 10.0), ("30 min", 30.0), ("1 h", 60.0),
     ("3 h", 180.0)),
    10.0, 1.0, 0.25, 1.0, "min", 1.0, (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60), True, 0.05)
SCALES = {"hours": HOURS, "minutes": MINUTES}


def scale_of(model) -> TimeScale:
    return SCALES.get(getattr(model, "scale", "hours"), HOURS)
