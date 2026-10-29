import pytest

from cns_desktop.lab.labels import plain


@pytest.mark.parametrize(("number", "text"), [
    (0.0, "0"), (1.5e-08, "under 0.01"), (0.012, "0.012"), (0.5, "0.5"), (1.0, "1"),
    (2.44, "2.4"), (15.53, "16"), (123.4, "123"), (40000.0, "40000"), (-0.3, "-0.3"),
])
def test_numbers_never_use_scientific_notation(number, text):
    assert plain(number) == text


def test_three_figures_when_asked():
    assert plain(15.53, 3) == "15.5" and plain(1.234e-5, 3) == "under 0.01"
