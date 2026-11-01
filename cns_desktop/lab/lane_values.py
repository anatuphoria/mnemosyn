from __future__ import annotations

import numpy as np

ABOVE = 1.02
BELOW = 0.98
TINY = 1e-12
FLAT = 0.05
NEAR_ZERO = 5e-4
WHOLE = 1000


def tone(mine: float, normal: float | None) -> str:
    if normal is None or abs(normal) <= TINY:
        return ""
    ratio = mine / normal
    return "raised" if ratio > ABOVE else "lowered" if ratio < BELOW else ""


def lane_scale(runs, key: str) -> tuple[float, float]:
    values = np.concatenate([np.asarray(run.value(key), dtype=float) for run in runs])
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    if high - low < TINY:
        spread = abs(high) * FLAT or 1.0
        low, high = low - spread, high + spread
    return low, high


def mark_text(value: float) -> str:
    if abs(value) < NEAR_ZERO:
        return "0"
    return f"{value:.0f}" if abs(value) >= WHOLE else f"{value:.3g}"
