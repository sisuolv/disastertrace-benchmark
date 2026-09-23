"""Consumer regressions from the v12 review; no source or model requests."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from test_monitoring_native_feature_session import setup

from disastertrace.monitoring_fixed_v1.native_feature import NativeFeaturePredictor
from disastertrace.monitoring_v1.regional_calibration import apply_monotone


def bank():
    return copy.deepcopy(setup()[2]["native_feature_bank"])


@pytest.mark.parametrize("blocks", [
    [{"lower": 0, "upper": 1, "value": -0.25}],
    [{"lower": 0.6, "upper": 0.8, "value": 0.2},
     {"lower": 0.1, "upper": 0.3, "value": 0.4}],
    [{"lower": 0.1, "upper": 0.6, "value": 0.2},
     {"lower": 0.5, "upper": 0.9, "value": 0.4}],
    [{"lower": 0.1, "upper": 0.5, "value": 0.2},
     {"lower": 0.5, "upper": 0.9, "value": 0.4}],
    [{"lower": 0, "upper": 1, "value": True}],
    [{"lower": 0, "upper": 1, "value": float("nan")}],
    [{"lower": 0, "upper": 1, "value": float("inf")}],
    [{"lower": 0, "upper": 1, "value": 10**400}],
])
def test_actual_calibrated_consumer_rejects_invalid_maps(blocks):
    value = bank()
    value["post_calibration"]["1000"] = blocks
    with pytest.raises(ValueError):
        NativeFeaturePredictor(value, at=0, calibrated=True)


def test_legitimate_sparse_gaps_and_extrapolation_are_preserved():
    value = bank()
    blocks = [{"lower": 0.1, "upper": 0.2, "value": 0.2},
              {"lower": 0.8, "upper": 0.9, "value": 0.4}]
    value["post_calibration"]["1000"] = blocks
    NativeFeaturePredictor(value, at=0, calibrated=True)
    assert [apply_monotone(blocks, p) for p in [0, 0.15, 0.5, 1]] == [0.2, 0.2, 0.4, 0.4]


def test_touching_domains_with_identical_value_are_compatible():
    value = bank()
    value["post_calibration"]["1000"] = [
        {"lower": 0, "upper": 0.5, "value": 0.2},
        {"lower": 0.5, "upper": 1, "value": 0.2},
    ]
    NativeFeaturePredictor(value, at=0, calibrated=True)


@pytest.mark.parametrize("position", ["mean", "scale", "intercepts"])
def test_huge_coefficient_rejected_with_controlled_value_error(position):
    value = bank()
    value[position][0] = 10**400
    with pytest.raises(ValueError):
        NativeFeaturePredictor(value, at=0)


def test_e_denominator_keeps_missing_frames_and_independent_of_y():
    from disastertrace.monitoring_v1.reporting import e_status_summary

    states = dict(zip("abcd", ["supported", "refuted", "undetermined", "inconsistent"]))
    result = e_status_summary(states, list("abcde"))
    assert result["determined"] == 2
    assert result["registered"] == 5
    assert result["missing_frame"] == 1
    assert sum(result["states"].values()) + result["missing_frame"] == 5


def test_e_summary_rejects_unknown_state_and_duplicate_roster():
    from disastertrace.monitoring_v1.reporting import e_status_summary

    with pytest.raises(ValueError):
        e_status_summary({"a": "entailed"}, ["a"])
    with pytest.raises(ValueError):
        e_status_summary({"a": "supported"}, ["a", "a"])


def test_annual_execute_sample_failure_has_unique_results(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    path = repo / "plans/v12_execution_20260915_01/annual_catalogs.py"
    spec = importlib.util.spec_from_file_location("v12_annual_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    units = [f"month-{i}" for i in range(72)]
    (tmp_path / "PLAN.json").write_text(json.dumps({"units": units, "sample_units": units[:3], "files": {}}))
    called = []

    def acquire(args):
        name = args[2]
        called.append(name)
        return {"unit": name, "complete": name != units[2]}

    monkeypatch.setattr(module, "acquire_unit", acquire)
    with pytest.raises(SystemExit) as result:
        module.execute(tmp_path, repo)
    assert result.value.code == 1
    actual = json.loads((tmp_path / "RESULT.json").read_text())
    assert len(actual["results"]) == 3
    assert actual["completed_units"] == 2
    assert len(actual["not_attempted"]) == 69
    assert set(called) == set(units[:3])
