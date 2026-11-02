import math

import pytest

from cns_desktop.lab.scales import ClockScale, LinearScale, LogScale, curve_points, scale_for
from lab_helpers import toy_model


def test_a_rate_slides_in_multiples_of_normal():
    s = LogScale(0.01, 0.1, 0.035)
    assert s.fraction(0.035) == pytest.approx(math.log(3.5) / math.log(10))
    assert s.value(s.fraction(0.07)) == pytest.approx(0.07)
    assert [label for _, label in s.marks()] == ["⅓×", "½×", "normal", "2×"]
    assert s.badge(0.07, 0.035) == "2× normal" and s.badge(0.035, 0.035) == ""
    assert s.badge(0.0175, 0.035) == "0.5× normal"


def test_a_clock_reads_hours_and_minutes():
    s = ClockScale(1440)
    assert s.text(500) == "8:20"
    assert [label for _, label in s.marks()] == ["0:00", "6:00", "12:00", "18:00", "24:00"]
    assert ClockScale(720).marks()[-1][1] == "12:00"
    assert s.fraction(720) == 0.5


def test_a_plain_slider_marks_low_normal_and_high():
    s = LinearScale(0.0, 5.0, 1.0)
    assert s.marks() == [(0.0, "0"), (0.2, "normal"), (1.0, "5")]
    assert s.fraction(9.0) == 1.0 and s.fraction(-1.0) == 0.0
    assert s.badge(2.0, 1.0) == ""


def test_each_setting_gets_the_scale_of_its_kind(tmp_path):
    model = toy_model(tmp_path)
    assert isinstance(scale_for(model.parameter("w")), LogScale)
    assert isinstance(scale_for(model.parameter("stress")), LinearScale)


def test_curve_points_follow_the_edited_value(tmp_path):
    model = toy_model(tmp_path)
    curve = model.curve("feedback")
    normal = dict(curve_points(model, curve, {}, 11))
    edited = dict(curve_points(model, curve, {"k": 4.0}, 11))
    assert normal[1.0] == pytest.approx(1.0) and edited[4.0] == pytest.approx(0.5 * 17 / 16)
    assert len(normal) == 11 and min(normal) == 0.0 and max(normal) == 10.0
