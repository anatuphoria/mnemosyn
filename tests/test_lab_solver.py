import math
from itertools import pairwise

import pytest

from cns_lab.solver import SolverError, integrate


def test_decay_matches_the_exact_solution():
    times, states = integrate(lambda t, y: [-0.1 * y[0]], 0.0, [1.0], 100.0, max_step=30.0)
    assert times[0] == 0.0 and times[-1] == 100.0
    assert states[-1][0] == pytest.approx(math.exp(-10.0), rel=2e-5)


def test_an_oscillator_keeps_its_amplitude_over_a_month_of_minutes():
    w = 2 * math.pi / 1440

    def f(t, y):
        return [y[1], -w * w * y[0]]

    _, states = integrate(f, 0.0, [1.0, 0.0], 40320.0, max_step=30.0)
    assert states[-1][0] == pytest.approx(1.0, abs=1e-4)
    assert math.hypot(states[-1][0], states[-1][1] / w) == pytest.approx(1.0, abs=1e-4)


def test_breaks_are_hit_exactly():
    times, _ = integrate(lambda t, y: [1.0], 0.0, [0.0], 40.0, max_step=30.0, breaks=(10.0, 25.5))
    assert 10.0 in times and 25.5 in times


def test_breaks_outside_the_span_are_ignored():
    times, _ = integrate(lambda t, y: [1.0], 0.0, [0.0], 40.0, max_step=30.0,
                         breaks=(-5.0, 0.0, 40.0, 90.0))
    assert times.count(0.0) == 1 and times.count(40.0) == 1 and 90.0 not in times


def test_max_step_is_respected():
    times, _ = integrate(lambda t, y: [0.0], 0.0, [1.0], 500.0, max_step=30.0)
    assert max(b - a for a, b in pairwise(times)) <= 30.0 + 1e-9


def test_states_follow_a_rhythm_with_few_steps():
    w = 2 * math.pi / 1440
    times, states = integrate(lambda t, y: [w * math.cos(w * t)], 0.0, [0.0], 2880.0,
                              max_step=30.0)
    assert len(times) < 400
    assert states[-1][0] == pytest.approx(0.0, abs=1e-6)


def test_a_blow_up_raises():
    with pytest.raises(SolverError):
        integrate(lambda t, y: [y[0] * y[0]], 0.0, [1.0], 2.0, max_step=0.5)


def test_a_state_that_is_not_a_number_raises():
    with pytest.raises(SolverError):
        integrate(lambda t, y: [float("nan")], 0.0, [1.0], 2.0, max_step=0.5)
