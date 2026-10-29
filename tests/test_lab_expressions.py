import pytest

from cns_lab.expressions import ExpressionError, compile_function, names
from cns_lab.times import TimeError, duration, moment


def test_names_lists_every_name_but_functions():
    assert names("b2 * C * hill(x3, K_gr, n) - w2 * x2") == {"b2", "C", "x3", "K_gr", "n", "w2",
                                                              "x2"}


def test_constants_are_not_names():
    assert names("2 * pi * clock / 1440") == {"clock"}


@pytest.mark.parametrize("bad", ["__import__('os')", "x.real", "x[0]", "lambda: 1",
                                 "x if y else z", "open(f)", "1 < 2", "x = 1", "", "'text'",
                                 "hill(x)", "exp(x, y)"])
def test_anything_outside_the_grammar_is_refused(bad):
    with pytest.raises(ExpressionError):
        names(bad)


def test_compiled_functions_compute_in_order():
    f = compile_function({"a": "x * 2", "b": "hill(x, 2, 3) + pi * 0"}, ("x",))
    assert f(2.0) == pytest.approx((4.0, 0.5))


def test_compiled_functions_can_use_earlier_results():
    f = compile_function({"a": "x + 1", "b": "a * 10"}, ("x",))
    assert f(1.0) == pytest.approx((2.0, 20.0))


def test_pos_cuts_below_zero():
    f = compile_function({"a": "pos(x)"}, ("x",))
    assert f(-3.0) == (0.0,) and f(2.0) == (2.0,)


def test_moments_and_durations():
    assert moment("day 1 08:00") == 480 and moment("day 2 08:00") == 1920
    assert duration("30 min") == 30 and duration("2 h") == 120 and duration("3 d") == 4320
    assert duration("4 w") == 40320 and duration("1.5 h") == 90


@pytest.mark.parametrize("bad", ["day 0 08:00", "day 1 25:00", "day 1 8", "08:00"])
def test_bad_moments_are_refused(bad):
    with pytest.raises(TimeError):
        moment(bad)


@pytest.mark.parametrize("bad", ["8 hours", "-2 h", "h", "0 min", ""])
def test_bad_durations_are_refused(bad):
    with pytest.raises(TimeError):
        duration(bad)
