from __future__ import annotations

import math
from collections.abc import Callable, Sequence

C = (0.0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1.0, 1.0)
A = (
    (),
    (1 / 5,),
    (3 / 40, 9 / 40),
    (44 / 45, -56 / 15, 32 / 9),
    (19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729),
    (9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656),
    (35 / 384, 0.0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84),
)
B = (35 / 384, 0.0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0.0)
E = (71 / 57600, 0.0, -71 / 16695, 71 / 1920, -17253 / 339200, 22 / 525, -1 / 40)
SAFETY, SHRINK, GROW = 0.9, 0.2, 5.0


class SolverError(ArithmeticError):
    pass


def _span(f, t0: float, y0: list[float], t1: float, max_step: float, rtol: float, atol: float,
          times: list[float], states: list[list[float]], h: float) -> float:
    t, y = t0, list(y0)
    k1 = f(t, y)
    broken = False
    while t < t1:
        h = min(h, max_step, t1 - t)
        if h < 1e-9 * max(1.0, abs(t)):
            if broken:
                raise SolverError(f"the model gave a value that is not a number at {t:.3f} min")
            raise SolverError(f"step too small at {t:.3f} min")
        a2, a3, a4, a5, a6, a7 = A[1:]
        k2 = f(t + C[1] * h, [yi + h * a2[0] * q1 for yi, q1 in zip(y, k1)])
        k3 = f(t + C[2] * h, [yi + h * (a3[0] * q1 + a3[1] * q2)
                              for yi, q1, q2 in zip(y, k1, k2)])
        k4 = f(t + C[3] * h, [yi + h * (a4[0] * q1 + a4[1] * q2 + a4[2] * q3)
                              for yi, q1, q2, q3 in zip(y, k1, k2, k3)])
        k5 = f(t + C[4] * h, [yi + h * (a5[0] * q1 + a5[1] * q2 + a5[2] * q3 + a5[3] * q4)
                              for yi, q1, q2, q3, q4 in zip(y, k1, k2, k3, k4)])
        k6 = f(t + h, [yi + h * (a6[0] * q1 + a6[1] * q2 + a6[2] * q3 + a6[3] * q4 + a6[4] * q5)
                       for yi, q1, q2, q3, q4, q5 in zip(y, k1, k2, k3, k4, k5)])
        new = [yi + h * (a7[0] * q1 + a7[2] * q3 + a7[3] * q4 + a7[4] * q5 + a7[5] * q6)
               for yi, q1, q3, q4, q5, q6 in zip(y, k1, k3, k4, k5, k6)]
        k7 = f(t + h, new)
        e1, _, e3, e4, e5, e6, e7 = E
        error = 0.0
        for yi, ni, q1, q3, q4, q5, q6, q7 in zip(y, new, k1, k3, k4, k5, k6, k7):
            e = h * (e1 * q1 + e3 * q3 + e4 * q4 + e5 * q5 + e6 * q6 + e7 * q7)
            e /= atol + rtol * max(abs(yi), abs(ni))
            error += e * e
        error = math.sqrt(error / len(y)) if y else 0.0
        if not math.isfinite(error):
            broken = True
            h *= SHRINK
            continue
        broken = False
        if error <= 1.0:
            t = t1 if t1 - (t + h) < 1e-12 * max(1.0, abs(t1)) else t + h
            y = new
            k1 = k7
            times.append(t)
            states.append(y)
            factor = GROW if error == 0.0 else min(GROW, SAFETY * error ** -0.2)
        else:
            factor = max(SHRINK, SAFETY * error ** -0.2)
        h *= factor
    return h


def integrate(f: Callable[[float, list[float]], list[float]], t0: float, y0: list[float],
              t1: float, max_step: float, breaks: Sequence[float] = (), rtol: float = 1e-6,
              atol: float = 1e-9,
              at_break: Callable[[float, list[float]], list[float]] | None = None,
              ) -> tuple[list[float], list[list[float]]]:
    if any(not math.isfinite(v) for v in y0):
        raise SolverError("the starting state is not a number")
    stops = sorted({b for b in breaks if t0 < b < t1})
    times, states = [t0], [list(y0)]
    h = min(max_step, (t1 - t0) or max_step) * 0.01 or max_step
    start, y = t0, list(y0)
    for stop in [*stops, t1]:
        h = _span(f, start, y, stop, max_step, rtol, atol, times, states, max(h, 1e-6))
        start, y = stop, states[-1]
        if at_break is not None and stop < t1:
            y = at_break(stop, list(y))
            if y != states[-1]:
                times.append(stop)
                states.append(list(y))
    return times, states
