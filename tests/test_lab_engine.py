import math

import numpy as np
import pytest

from cns_lab.engine import SettleError, Simulator
from cns_lab.experiment import Block, Experiment
from cns_lab.solver import SolverError
from lab_helpers import toy_model

DAY = 1440.0


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    return Simulator(toy_model(tmp_path_factory.mktemp("toy")))


def plain(length=2 * DAY, blocks=(), values=()):
    return Experiment("toy", 1, length, 480.0, tuple(blocks), tuple(values))


def test_the_normal_run_repeats_day_after_day(sim):
    run = sim.normal(3 * DAY, 480.0)
    for key in ("x", "y", "m"):
        assert run.at(key, DAY) == pytest.approx(run.at(key, 2 * DAY), rel=5e-4)
        assert run.at(key, 0.0) == pytest.approx(run.at(key, DAY), rel=5e-4)


def test_the_normal_run_has_a_daily_rhythm(sim):
    run = sim.normal(DAY, 480.0)
    x = run.value("x")
    assert x.max() / x.min() > 1.2


def test_a_dose_raises_y_at_its_time_only(sim):
    run = sim.run(plain(blocks=[Block("pill", 600.0, None, (("dose", 2.0),))]))
    normal = sim.normal(2 * DAY, 480.0)
    assert run.at("y", 599.0) == pytest.approx(normal.at("y", 599.0), rel=5e-4)
    assert run.at("y", 601.0) > normal.at("y", 601.0) + 1.5


def test_a_clamp_present_from_the_start_settles_in_that_state(sim):
    run = sim.run(plain(blocks=[Block("remove_b", 0.0, None, (), "present")]))
    assert np.all(run.value("m") == 0.0)
    assert run.at("x", 0.0) == pytest.approx(run.at("x", DAY), rel=5e-4)
    assert run.at("x", 0.0) > sim.normal(2 * DAY, 480.0).at("x", 0.0) * 1.2


def test_a_clamp_from_a_time_starts_at_its_time(sim):
    run = sim.run(plain(blocks=[Block("remove_b", 600.0, None, ())]))
    assert run.at("m", 599.0) > 0.5 and run.at("m", 601.0) == 0.0


def test_a_timed_block_ends_at_its_length(sim):
    run = sim.run(plain(blocks=[Block("stress", 600.0, 60.0, (("strength", 2.0),))]))
    normal = sim.normal(2 * DAY, 480.0)
    assert run.at("x", 650.0) > normal.at("x", 650.0) * 1.3
    assert run.at("x", 600.0 + 720.0) == pytest.approx(normal.at("x", 1320.0), rel=0.05)


def test_a_daily_course_doses_every_day_of_its_length(sim):
    run = sim.run(plain(length=5 * DAY, blocks=[Block("course", 600.0, 3 * DAY, (("dose", 1.0),))]))
    normal = sim.normal(5 * DAY, 480.0)
    for day in range(3):
        t = 600.0 + day * DAY + 1.0
        assert run.at("y", t) > normal.at("y", t) + 0.5
    assert run.at("y", 600.0 + 3 * DAY + 1.0) < normal.at("y", 600.0 + 3 * DAY + 1.0) + 0.5


def test_a_test_block_gives_its_doses(sim):
    run = sim.run(plain(blocks=[Block("pill_test", 600.0, None, ())]))
    assert run.at("y", 601.0) > sim.normal(2 * DAY, 480.0).at("y", 601.0) + 1.5


def test_edited_values_apply_from_time_zero(sim):
    run = sim.run(plain(values=[("k", 3.0)]))
    normal = sim.normal(2 * DAY, 480.0)
    assert run.at("x", 0.0) != pytest.approx(normal.at("x", 0.0), rel=1e-3)
    assert run.at("x", 0.0) == pytest.approx(run.at("x", DAY), rel=5e-4)


def test_factors_are_computed_at_any_time(sim):
    run = sim.normal(DAY, 480.0)
    rhythm = run.factor("rhythm", 0.0)
    assert rhythm == pytest.approx(1 + 0.3 * math.cos(2 * math.pi * (480 - 360) / 1440))
    assert run.factor("clear_x", 100.0) == pytest.approx(0.1 * run.at("x", 100.0))


def test_display_values_use_the_display_scale(sim):
    run = sim.normal(DAY, 480.0)
    assert run.display("x", 0.0) == pytest.approx(10.0 * run.at("x", 0.0))


def test_runs_and_settled_states_are_cached(sim):
    experiment = plain(values=[("w", 0.2)])
    assert sim.run(experiment) is sim.run(experiment)


def test_every_parameter_at_its_limits_gives_a_finite_run_or_a_settle_error(sim):
    model = sim.model
    cases = [[(p.key, p.low)] for p in model.parameters]
    cases += [[(p.key, p.high)] for p in model.parameters]
    cases += [[(p.key, p.low) for p in model.parameters], [(p.key, p.high) for p in model.parameters]]
    for values in cases:
        try:
            run = sim.run(plain(length=DAY, values=values))
        except (SettleError, SolverError) as exc:
            assert str(exc)
            continue
        assert np.all(np.isfinite(run.states)), values


def test_errors_inside_the_equations_become_solver_errors(tmp_path, monkeypatch):
    sim = Simulator(toy_model(tmp_path))
    real = sim._rates
    armed = []

    def broken(clamped):
        function = real(clamped)

        def rates(*args):
            if armed and args[0] > 100:
                raise ZeroDivisionError("float division by zero")
            return function(*args)
        return rates

    monkeypatch.setattr(sim, "_rates", broken)
    sim.settle((), (("w", 0.2),))
    armed.append(1)
    with pytest.raises(SolverError):
        sim.run(plain(length=DAY, values=[("w", 0.2)]))
