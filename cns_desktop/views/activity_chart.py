from __future__ import annotations

import zlib

import numpy as np
import pyqtgraph as pg

from ..state import AppState

DURATION_S = 60.0
SAMPLES = 600


def placeholder_series(structure_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Fake deterministic signal until a real model exists."""
    rng = np.random.default_rng(zlib.crc32(structure_id.encode()))
    t = np.linspace(0.0, DURATION_S, SAMPLES)
    freqs = rng.uniform(0.02, 0.4, size=3)
    phases = rng.uniform(0, 2 * np.pi, size=3)
    y = sum(np.sin(2 * np.pi * f * t + p) / (i + 1) for i, (f, p) in enumerate(zip(freqs, phases)))
    y += rng.normal(0, 0.08, SAMPLES)
    return t, y


class ActivityChart(pg.PlotWidget):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setBackground("#0a0a10")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setLabel("bottom", "time", units="s")
        self.setLabel("left", "activity (a.u.)")
        self.curve = self.plot(pen=pg.mkPen(width=2))
        state.selection_changed.connect(self.show_structure)
        self.show_structure(state.selected)

    def show_structure(self, sid: str | None) -> None:
        if sid is None:
            self.curve.setData([], [])
            self.setTitle("Select a structure")
            return
        s = self.state.atlas.structures[sid]
        t, y = placeholder_series(sid)
        self.curve.setData(t, y, pen=pg.mkPen(s.color, width=2))
        self.setTitle(f"{s.name} - PLACEHOLDER data (no model yet)")
