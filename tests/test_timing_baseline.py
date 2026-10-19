import json

import pytest

from timing_baseline import TimingBaseline


@pytest.fixture
def path(tmp_path):
    return tmp_path / "baseline.json"


def test_the_first_measurement_is_recorded_and_passes(path):
    assert TimingBaseline(path).judge("route step", 0.010, 0.030) is None
    assert json.loads(path.read_text()) == {"route step": 0.010}


def test_a_quarter_and_a_millisecond_slower_fails_with_what_to_do(path):
    TimingBaseline(path).judge("route step", 0.010, 0.030)
    message = TimingBaseline(path).judge("route step", 0.0126, 0.030)
    assert "route step" in message
    assert "10.0 ms" in message and "12.6 ms" in message and "30.0 ms" in message
    assert "--reset-timing-baseline" in message


def test_a_quarter_slower_by_less_than_a_millisecond_passes(path):
    TimingBaseline(path).judge("lookup", 0.0005, 0.001)
    assert TimingBaseline(path).judge("lookup", 0.0009, 0.001) is None


def test_a_millisecond_slower_by_less_than_a_quarter_passes(path):
    TimingBaseline(path).judge("toggle", 0.020, 0.050)
    assert TimingBaseline(path).judge("toggle", 0.0245, 0.050) is None


def test_a_faster_run_never_lowers_the_record(path):
    TimingBaseline(path).judge("route step", 0.010, 0.030)
    TimingBaseline(path).judge("route step", 0.005, 0.030)
    assert json.loads(path.read_text()) == {"route step": 0.010}


def test_reset_records_todays_time_even_when_slower(path):
    TimingBaseline(path).judge("route step", 0.010, 0.030)
    assert TimingBaseline(path, reset=True).judge("route step", 0.020, 0.030) is None
    assert json.loads(path.read_text()) == {"route step": 0.020}


def test_over_the_limit_fails_and_is_not_recorded(path):
    message = TimingBaseline(path).judge("route step", 0.040, 0.030)
    assert "route step" in message and "40.0 ms" in message and "30.0 ms" in message
    assert not path.exists()


def test_assert_within_reports_every_failure_at_once(path):
    baseline = TimingBaseline(path)
    baseline.assert_within({"a": (0.010, 0.030), "b": (0.010, 0.030)})
    with pytest.raises(AssertionError) as failure:
        baseline.assert_within({"a": (0.020, 0.030), "b": (0.040, 0.030)})
    assert "a:" in str(failure.value) and "b:" in str(failure.value)
