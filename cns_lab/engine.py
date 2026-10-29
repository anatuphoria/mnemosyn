from __future__ import annotations

import math
from collections import OrderedDict
from itertools import pairwise

import numpy as np

from cns_atlas.models import LabModel

from .expressions import compile_function
from .experiment import Block, Experiment
from .solver import integrate
from .times import DAY

SETTLE_TOLERANCE = 2e-5
SETTLE_NEWTON = 12
CACHE_SIZE = 32
RUN_RTOL = 1e-5
SETTLE_RTOL = 1e-6


class SettleError(ArithmeticError):
    def __init__(self) -> None:
        super().__init__("The model cannot settle with these values.")


class Run:
    def __init__(self, simulator: Simulator, experiment: Experiment, times: list[float],
                 states: list[list[float]]) -> None:
        self.simulator = simulator
        self.experiment = experiment
        self.times = np.asarray(times, dtype=float)
        self.states = np.asarray(states, dtype=float).reshape(len(times), len(simulator.keys))
        self.keys = simulator.keys
        self._index = {k: i for i, k in enumerate(self.keys)}

    def value(self, key: str) -> np.ndarray:
        return self.states[:, self._index[key]]

    def at(self, key: str, t: float) -> float:
        return float(np.interp(t, self.times, self.value(key)))

    def state(self, t: float) -> list[float]:
        return [float(np.interp(t, self.times, self.states[:, i])) for i in range(len(self.keys))]

    def display(self, key: str, t: float) -> float:
        return self.at(key, t) * self.simulator.values[key].display_scale

    def factor(self, name: str, t: float) -> float:
        return self.factors(t)[name]

    def factors(self, t: float) -> dict[str, float]:
        sim = self.simulator
        params = sim.parameters_at(self.experiment, t)
        state = self.state(t)
        for index, level in sim.clamps_at(self.experiment, t, params).items():
            state[index] = level
        out = sim.factor_function(t, (self.experiment.start_clock + t) % DAY, *state, *params)
        return dict(zip(sim.factor_names, out))


class Simulator:
    def __init__(self, model: LabModel) -> None:
        self.model = model
        self.keys = tuple(v.key for v in model.values)
        self.values = {v.key: v for v in model.values}
        self.parameter_keys = tuple(p.key for p in model.parameters)
        self.defaults = [p.value for p in model.parameters]
        self._param_index = {k: i for i, k in enumerate(self.parameter_keys)}
        self._value_index = {k: i for i, k in enumerate(self.keys)}
        exprs = {e.key: e.expr for e in model.effects}
        exprs.update({t.key: t.expr for t in model.terms})
        args = ("t", "clock", *self.keys, *self.parameter_keys)
        self.factor_names = tuple(exprs)
        self.factor_function = compile_function(exprs, args)
        offset = len(model.effects)
        self._terms = [[(offset + n, t.sign) for n, t in enumerate(model.terms) if t.value == key]
                       for key in self.keys]
        self._slow = [self.values[k].slow for k in self.keys]
        self._experiments = {e.key: e for e in model.experiments}
        self._tests = {t.key: t for t in model.tests}
        self._option_args = {}
        self._rate_functions: dict = {}
        self._runs: OrderedDict = OrderedDict()
        self._settled: OrderedDict = OrderedDict()

    def _evaluate(self, expr: str, names: dict[str, float]) -> float:
        key = (expr, tuple(names))
        function = self._option_args.get(key)
        if function is None:
            function = compile_function({"_v": expr}, tuple(names))
            self._option_args[key] = function
        return float(function(*names.values())[0])

    def _names(self, block: Block, params: list[float]) -> dict[str, float]:
        names = dict(zip(self.parameter_keys, params))
        experiment = self._experiments.get(block.experiment)
        if experiment is not None:
            options = block.option_map
            names.update({o.key: options.get(o.key, o.default) for o in experiment.options})
        return names

    def parameters_at(self, experiment: Experiment, t: float) -> list[float]:
        params = list(self.defaults)
        for key, value in experiment.values:
            if key in self._param_index:
                params[self._param_index[key]] = value
        for block in experiment.blocks:
            found = self._experiments.get(block.experiment)
            if found is None or not block.active(t, experiment.length):
                continue
            for edit in found.edits:
                if edit.op not in ("set", "add", "scale"):
                    continue
                level = self._evaluate(edit.expr, self._names(block, params))
                index = self._param_index[edit.target]
                if edit.op == "set":
                    params[index] = level
                elif edit.op == "add":
                    params[index] += level
                else:
                    params[index] *= level
        return params

    def clamps_at(self, experiment: Experiment, t: float, params: list[float]) -> dict[int, float]:
        clamps = {}
        for block in experiment.blocks:
            found = self._experiments.get(block.experiment)
            if found is None or not block.active(t, experiment.length):
                continue
            for edit in found.edits:
                if edit.op == "clamp":
                    clamps[self._value_index[edit.target]] = self._evaluate(
                        edit.expr, self._names(block, params))
        return clamps

    def _doses(self, experiment: Experiment, t0: float, t1: float,
               present_only: bool) -> dict[float, list[tuple[Block, int, str]]]:
        doses: dict[float, list[tuple[Block, int, str]]] = {}

        def add(time: float, block: Block, index: int, expr: str) -> None:
            if t0 <= time < t1:
                doses.setdefault(time, []).append((block, index, expr))

        for block in experiment.blocks:
            if present_only and not block.present:
                continue
            test = self._tests.get(block.experiment)
            if test is not None and not block.present:
                for after, value, amount in test.doses:
                    add(block.start + after, block, self._value_index[value], amount)
                continue
            found = self._experiments.get(block.experiment)
            if found is None:
                continue
            for edit in found.edits:
                if edit.op != "dose":
                    continue
                index = self._value_index[edit.target]
                if block.present:
                    if edit.daily:
                        first = t0 + (block.start - t0) % DAY
                        for k in range(math.ceil((t1 - first) / DAY) + 1):
                            add(first + k * DAY, block, index, edit.expr)
                    continue
                add(block.start, block, index, edit.expr)
                if edit.daily:
                    end = block.end(experiment.length)
                    time = block.start + DAY
                    while time < min(end, t1):
                        add(time, block, index, edit.expr)
                        time += DAY
        return doses

    def _breaks(self, experiment: Experiment, t0: float, t1: float, doses) -> list[float]:
        points = {t0, t1, *doses}
        for block in experiment.blocks:
            if not block.present:
                points.add(block.start)
                points.add(block.end(experiment.length))
        return sorted(p for p in points if t0 <= p <= t1)

    def _rates(self, clamped: frozenset[int]):
        function = self._rate_functions.get(clamped)
        if function is None:
            exprs = {e.key: e.expr for e in self.model.effects}
            exprs.update({t.key: t.expr for t in self.model.terms})
            names = []
            for i, members in enumerate(self._terms):
                name = f"_rate{i}"
                names.append(name)
                total = " + ".join(f"{'' if sign > 0 else '-'}{self.factor_names[index]}"
                                   for index, sign in members)
                if i in clamped or not total:
                    exprs[name] = "0"
                else:
                    exprs[name] = f"({total}) * _speed" if self._slow[i] else f"{total}"
            args = ("t", "clock", *self.keys, *self.parameter_keys, "_speed")
            function = compile_function(exprs, args, tuple(names))
            self._rate_functions[clamped] = function
        return function

    def _derivative(self, params: list[float], clamps: dict[int, float], speedup: float,
                    clock0: float):
        function = self._rates(frozenset(clamps))
        tail = (*params, speedup)

        def f(t: float, y: list[float]) -> list[float]:
            return list(function(t, (clock0 + t) % DAY, *y, *tail))

        return f

    def _march(self, experiment: Experiment, t0: float, t1: float, y: list[float],
               speedup: float = 1.0, present_only: bool = False,
               times: list | None = None, states: list | None = None) -> list[float]:
        doses = self._doses(experiment, t0, t1, present_only)
        points = self._breaks(experiment, t0, t1, doses)
        for a, b in pairwise(points):
            params = self.parameters_at(experiment, (a + b) / 2)
            clamps = self.clamps_at(experiment, (a + b) / 2, params)
            y = list(y)
            for index, level in clamps.items():
                y[index] = level
            for block, index, expr in doses.get(a, ()):
                y[index] += self._evaluate(expr, self._names(block, params))
            if times is not None and not (times and times[-1] == a and states[-1] == y):
                times.append(a)
                states.append(list(y))
            f = self._derivative(params, clamps, speedup, experiment.start_clock)
            rtol = RUN_RTOL if times is not None else SETTLE_RTOL
            step_times, step_states = integrate(f, a, y, b, self.model.max_step, rtol=rtol)
            y = step_states[-1]
            if times is not None:
                times.extend(step_times[1:])
                states.extend(step_states[1:])
        return y

    def settle(self, present: tuple[Block, ...], values: tuple) -> list[float]:
        key = (present, values)
        if key in self._settled:
            self._settled.move_to_end(key)
            return self._settled[key]
        experiment = Experiment(self.model.key, self.model.version, math.inf,
                                self.model.start_clock, present, values)
        y = [self.values[k].start for k in self.keys]
        speedup = self.model.settle_speedup
        y = self._march(experiment, 0.0, self.model.settle_days * DAY, y, speedup, True)
        y = self._periodic(experiment, y)
        self._settled[key] = y
        while len(self._settled) > CACHE_SIZE:
            self._settled.popitem(last=False)
        return y

    def _periodic(self, experiment: Experiment, y: list[float]) -> list[float]:
        def day(state):
            return np.asarray(self._march(experiment, 0.0, DAY, list(state), 1.0, True))

        held = set(self.clamps_at(experiment, 0.0, self.parameters_at(experiment, 0.0)))
        state = np.asarray(y, dtype=float)
        image = day(state)
        free = [i for i in range(len(y))
                if i not in held and not (state[i] == 0.0 and image[i] == 0.0)]

        def size(state, image):
            gap = (image - state)[free]
            scale = np.maximum(np.maximum(np.abs(image), np.abs(state))[free], 1.0)
            return gap, float(np.max(np.abs(gap) / scale, initial=0.0))

        for _ in range(SETTLE_NEWTON):
            if not np.all(np.isfinite(image)):
                raise SettleError()
            gap, error = size(state, image)
            if error < SETTLE_TOLERANCE:
                return [float(v) for v in image]
            jacobian = np.empty((len(free), len(free)))
            for column, i in enumerate(free):
                step = 1e-4 * max(1.0, abs(state[i]))
                nudged = state.copy()
                nudged[i] += step
                jacobian[:, column] = (day(nudged)[free] - image[free]) / step
            jacobian -= np.eye(len(free))
            try:
                move = np.linalg.solve(jacobian, -gap)
            except np.linalg.LinAlgError as exc:
                raise SettleError() from exc
            for _ in range(6):
                trial = state.copy()
                trial[free] += move
                trial_image = day(trial)
                if np.all(np.isfinite(trial_image)) and size(trial, trial_image)[1] < error:
                    break
                move /= 2
            state, image = trial, trial_image
        raise SettleError()

    def run(self, experiment: Experiment) -> Run:
        if experiment in self._runs:
            self._runs.move_to_end(experiment)
            return self._runs[experiment]
        start = self._settle_at(experiment)
        times: list[float] = []
        states: list[list[float]] = []
        self._march(experiment, 0.0, experiment.length, start, times=times, states=states)
        run = Run(self, experiment, times, states)
        self._runs[experiment] = run
        while len(self._runs) > CACHE_SIZE:
            self._runs.popitem(last=False)
        return run

    def _settle_at(self, experiment: Experiment) -> list[float]:
        present = tuple(b for b in experiment.blocks if b.present)
        y = self.settle(present, experiment.values)
        shift = (experiment.start_clock - self.model.start_clock) % DAY
        if not shift:
            return y
        moved = Experiment(self.model.key, self.model.version, shift, self.model.start_clock,
                           present, experiment.values)
        return self._march(moved, 0.0, shift, y, 1.0, True)

    def normal(self, length: float, start_clock: float) -> Run:
        return self.run(Experiment(self.model.key, self.model.version, length, start_clock))
