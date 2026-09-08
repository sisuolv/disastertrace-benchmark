from copy import deepcopy
from decimal import Decimal

import pytest

from disastertrace.automated.calibration import DEFAULT_RATES, read
from disastertrace.automated.execution_observations import estimate_captured_cost


def estimate(start, end, **changes):
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_cache_hit_tokens": 80,
        "prompt_cache_miss_tokens": 20,
        "completion_tokens_details": {"reasoning_tokens": 40},
    }
    usage.update(changes)
    return estimate_captured_cost(usage, start, end, read(DEFAULT_RATES))


@pytest.mark.parametrize(
    "start,end,window,cost",
    [
        ("2026-09-07T01:00:00+00:00", "2026-09-07T01:01:00+00:00", "peak", "0.00007592"),
        ("2026-09-07T04:00:00+00:00", "2026-09-07T04:01:00+00:00", "off_peak", "0.00003796"),
        ("2026-09-06T02:00:00+00:00", "2026-09-06T02:01:00+00:00", "off_peak", "0.00003796"),
    ],
)
def test_cache_and_window_cost_includes_reasoning_once(start, end, window, cost):
    result = estimate(start, end)
    assert result["window"] == window
    assert Decimal(result["usd"]) == Decimal(cost)
    assert result["status"] == "estimated_from_capture"


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-09-07T00:59:59+00:00", "2026-09-07T01:00:00+00:00"),
        ("2026-09-07T03:59:59+00:00", "2026-09-07T04:00:00+00:00"),
        ("2026-09-07T05:59:59+00:00", "2026-09-07T06:00:00+00:00"),
        ("2026-09-07T09:59:59+00:00", "2026-09-07T10:00:00+00:00"),
        ("2026-09-07T01:01:00+00:00", "2026-09-07T09:01:00+00:00"),
        ("2026-09-07T02:01:00+00:00", "2026-09-07T02:00:00+00:00"),
        ("2026-09-07T02:00:00", "2026-09-07T02:01:00"),
        (None, "2026-09-07T02:01:00+00:00"),
    ],
)
def test_ambiguous_or_unverified_window_has_no_point_estimate(start, end):
    result = estimate(start, end)
    assert result["usd"] is None
    assert result["status"] == "unverified_time_window"


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_cache_hit_tokens": None},
        {"prompt_cache_hit_tokens": True},
        {"prompt_cache_hit_tokens": 81},
        {"prompt_cache_miss_tokens": -1},
    ],
)
def test_invalid_cache_counts_do_not_assume_cache_miss(changes):
    result = estimate("2026-09-07T02:00:00+00:00", "2026-09-07T02:01:00+00:00", **changes)
    assert result["usd"] is None
    assert result["status"] == "unverified_cache_usage"


def test_changed_price_window_rule_is_not_silently_interpreted():
    rates = deepcopy(read(DEFAULT_RATES))
    rates["window"]["peak_rule"] = "New pricing schedule"
    result = estimate_captured_cost({}, None, None, rates)
    assert result["status"] == "unsupported_price_snapshot"
    assert result["usd"] is None
