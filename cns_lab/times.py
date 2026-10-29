from __future__ import annotations

import re

DAY = 1440.0
UNITS = {"min": 1.0, "h": 60.0, "d": DAY, "w": 7 * DAY}
_MOMENT = re.compile(r"day ([1-9][0-9]*) ([0-9]{2}):([0-9]{2})")
_DURATION = re.compile(r"([0-9]+(?:\.[0-9]+)?) (min|h|d|w)")


class TimeError(ValueError):
    pass


def moment(text: str) -> float:
    found = _MOMENT.fullmatch(text.strip()) if isinstance(text, str) else None
    if found is None:
        raise TimeError(f"{text!r}: a moment is written like 'day 2 08:00'")
    day, hour, minute = (int(g) for g in found.groups())
    if hour > 23 or minute > 59:
        raise TimeError(f"{text!r}: not a time of day")
    return (day - 1) * DAY + hour * 60.0 + minute


def duration(text: str) -> float:
    found = _DURATION.fullmatch(text.strip()) if isinstance(text, str) else None
    if found is None:
        raise TimeError(f"{text!r}: a duration is written like '30 min', '2 h', '3 d' or '4 w'")
    minutes = float(found.group(1)) * UNITS[found.group(2)]
    if minutes <= 0:
        raise TimeError(f"{text!r}: a duration must be more than zero")
    return minutes


def clock(text: str) -> float:
    found = re.fullmatch(r"([0-9]{2}):([0-9]{2})", text.strip()) if isinstance(text, str) else None
    if found is None or int(found.group(1)) > 23 or int(found.group(2)) > 59:
        raise TimeError(f"{text!r}: a clock time is written like '08:00'")
    return int(found.group(1)) * 60.0 + int(found.group(2))
