from __future__ import annotations

SMALLEST = 0.01
ZERO = 1e-9


def plain(number: float, figures: int = 2, compact: bool = False) -> str:
    if number == 0:
        return "0"
    if abs(number) < SMALLEST:
        return f"<{SMALLEST:g}" if compact else f"under {SMALLEST:g}"
    if abs(number) >= 10 ** figures:
        return f"{number:.0f}"
    return f"{float(f'{number:.{figures}g}'):g}"


def ratio_text(ratio: float) -> str:
    arrow = "↑" if ratio > 1.02 else "↓" if ratio < 0.98 else "="
    return f"{arrow} {plain(ratio)}× healthy"


def removed_parts(document) -> set[str]:
    params = document.simulator.parameters_at(document.experiment, document.playhead)
    clamps = document.simulator.clamps_at(document.experiment, document.playhead, params)
    zero = {document.simulator.keys[i] for i, level in clamps.items() if abs(level) < ZERO}
    return {p.key for p in document.model.parts if p.values and set(p.values) & zero}
