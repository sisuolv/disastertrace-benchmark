"""Synthetic red/green tests for the v23-B source roster builder."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import build_v23_source_roster as roster


def _iv(lower, upper, lower_closed=True, upper_closed=True):
    return {"lower": lower, "upper": upper, "lower_closed": lower_closed, "upper_closed": upper_closed}


def _projection(prevailing, conditional=()):
    return {"segments": [{"start": 0, "end": 10, "prevailing": prevailing, "conditional": list(conditional)}]}


def _state(lower, upper):
    return {"visibility": _iv(lower, upper)}


def test_taf_event_flags_cover_low_high_conditional_crossing_and_uncovered():
    assert roster.taf_event_flag(_projection([_state(0, 4999)])) == 1
    assert roster.taf_event_flag(_projection([_state(5000, 10000)])) == 0
    low_cond = [{"states": [_state(0, 4999)]}]
    assert roster.taf_event_flag(_projection([_state(5000, 10000)], low_cond)) is None
    assert roster.taf_event_flag(_projection([_state(4000, 6000)])) is None
    assert roster.taf_event_flag({"segments": []}) is None


def test_metar_boundary_and_speci_are_visible():
    assert roster.metar_event_flag(_iv(0, 4999)) == 1
    assert roster.metar_event_flag(_iv(5000, 10000)) == 0
    assert roster.metar_event_flag(_iv(4999, 5001)) is None
    obs = [
        SimpleNamespace(observation_time=100, report_type="routine", visibility=_iv(6000, 7000)),
        SimpleNamespace(observation_time=200, report_type="special", visibility=_iv(0, 4999)),
    ]
    latest = roster.latest_visible_metar(obs, cutoff_us=200, available_at=lambda value: value)
    assert latest.report_type == "special"
    assert roster.latest_visible_metar(obs, cutoff_us=199, available_at=lambda value: value).report_type == "routine"


def test_output_has_no_outcome_fields_and_stats_do_not_overwrite():
    row = {"source_only": True, "features_do_not_include_outcome": True, "taf": {}}
    roster.validate_source_only_row(row)
    with pytest.raises(ValueError):
        roster.validate_source_only_row({**row, "outcome": 1})
    merged = roster.merge_parse_stats({}, ("KDEN", "2025-01"), {"taf_products": 3, "taf_skipped": 2})
    merged = roster.merge_parse_stats(merged, ("KDEN", "2025-01"), {"asos_observations": 4})
    assert merged[("KDEN", "2025-01")]["taf_products"] == 3
    assert merged[("KDEN", "2025-01")]["asos_observations"] == 4


def test_month_end_gap_and_staleness_are_explicit():
    assert roster.source_gap_month_end("2025-01", 31) is True
    assert roster.source_gap_month_end("2025-01", 30) is False
    assert roster.source_gap_month_end("2025-03", 31) is True
    assert roster.metar_age_hours(observation_us=0, cutoff_us=7_200_000_000) == 2.0


def test_read_contract_and_grid_contract_fail_closed():
    with pytest.raises(PermissionError):
        roster.preflight_git_contract("/definitely/not/a/git-config")
    with pytest.raises(ValueError):
        roster.require_v23_grid_contract(expected_methods=None, cutoff=None, available_at=None)
    assert roster.require_v23_grid_contract(expected_methods=("TAF",), cutoff=1, available_at=2)["expected_methods"] == ["TAF"]
