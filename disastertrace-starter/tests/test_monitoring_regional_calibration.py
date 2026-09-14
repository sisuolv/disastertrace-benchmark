import math

import pytest

from disastertrace.monitoring_v1.regional_calibration import apply_monotone, fit_monotone


def test_pool_adjacent_violations_and_preserve_probability_bounds():
    fitted = fit_monotone([(0.1, 1, 1), (0.2, 0, 1), (0.8, 1, 1)])
    assert apply_monotone(fitted, 0.1) == apply_monotone(fitted, 0.2) == 0.5
    assert apply_monotone(fitted, 0.8) == pytest.approx(2 / 3)


def test_weighted_views_do_not_change_total_observation_weight():
    once = fit_monotone([(0.3, 1, 1), (0.8, 0, 1)])
    views = fit_monotone([(0.3, 1, 0.25)] * 4 + [(0.8, 0, 0.5)] * 2)
    assert once == views


@pytest.mark.parametrize("rows", [[], [(math.nan, 0, 1)], [(0.2, 2, 1)], [(0.2, 1, -1)]])
def test_invalid_calibration_data_rejected(rows):
    with pytest.raises(ValueError):
        fit_monotone(rows)
