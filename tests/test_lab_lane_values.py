from types import SimpleNamespace

import numpy as np
import pytest

from cns_desktop.lab.lane_values import lane_scale, mark_text, tone


def run_of(values):
    return SimpleNamespace(value=lambda _key: np.asarray(values, dtype=float))


def test_tone_follows_the_two_percent_rule():
    assert tone(1.03, 1.0) == "raised" and tone(0.97, 1.0) == "lowered"
    assert tone(1.01, 1.0) == "" and tone(5.0, None) == "" and tone(5.0, 0.0) == ""


def test_lane_scale_covers_every_run_and_widens_a_flat_line():
    assert lane_scale([run_of([1, 3]), run_of([0, 2])], "x") == (0.0, 3.0)
    low, high = lane_scale([run_of([2, 2])], "x")
    assert low == pytest.approx(1.9) and high == pytest.approx(2.1)
    assert lane_scale([run_of([0, 0])], "x") == (-1.0, 1.0)


def test_scale_marks_read_zero_and_three_figures():
    assert mark_text(0.0001) == "0" and mark_text(5.6213) == "5.62" and mark_text(0.0012) == "0.0012"
