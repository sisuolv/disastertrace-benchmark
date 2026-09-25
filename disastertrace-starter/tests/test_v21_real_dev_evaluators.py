from scripts.bind_v21_dev_asos_outcomes import _parse_sm
from scripts.run_v21_real_dev_deterministic_score import _projection_probability


def test_asos_statute_mile_parser_handles_decimal_fraction_and_missing():
    assert _parse_sm("10.00") == 10.0
    assert _parse_sm("1 1/4") == 1.25
    assert _parse_sm("P6") == 6.0
    assert _parse_sm("M") is None


def test_deterministic_forecast_map_uses_normalized_taf_metres():
    target_start, target_end = 1_000, 2_000
    low = {"periods": [{"valid_start": 1_000, "valid_end": 2_000, "visibility_m": {"lower": 4828.032}}]}
    high = {"periods": [{"valid_start": 1_000, "valid_end": 2_000, "visibility_m": {"lower": 9656.064}}]}
    missing = {"periods": [{"valid_start": 1_000, "valid_end": 2_000, "visibility_m": {"lower": "+inf"}}]}
    assert _projection_probability(low, target_start, target_end) == 0.8
    assert _projection_probability(high, target_start, target_end) == 0.2
    assert _projection_probability(missing, target_start, target_end) == 0.5
