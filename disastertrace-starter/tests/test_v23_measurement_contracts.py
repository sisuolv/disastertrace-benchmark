"""J0a-core measurement-contract tests for the v23 development grid."""

from datetime import datetime, timezone

import pytest

from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
from disastertrace.monitoring_v1.measurement_contract_v23 import MeasurementTargetContract


def _row(target="t", method="m1", checkpoint="c1", *, outcome=0, fallback=0.5, **extra):
    return {
        "target_id": target,
        "method": method,
        "checkpoint_id": checkpoint,
        "checkpoint_index": 0,
        "base": fallback,
        "fallback": fallback,
        "outcome": outcome,
        **extra,
    }


def test_entire_missing_arm_is_not_comparison_eligible():
    result = score_complete_grid(
        [_row(method="m1")],
        [{"target_id": "t", "method": "m1", "checkpoint_id": "c1", "status": "valid", "probability": 0.4}],
        expected_methods=("m1", "m2"),
    )
    assert result["comparison_eligible"] is False
    assert result["comparison_exclusion_reason"] == "missing_expected_arm"


def test_event_contract_hash_collision_is_rejected():
    rows = [
        _row(event_contract_hash="hash-a"),
        _row(checkpoint="c2", event_contract_hash="hash-b"),
    ]
    with pytest.raises(ValueError, match="event contract hash"):
        score_complete_grid(rows, [])


def test_late_update_cannot_backfill_an_earlier_cutoff():
    cutoff = 1_000
    result = score_complete_grid(
        [_row(cutoff=cutoff)],
        [{
            "target_id": "t", "method": "m1", "checkpoint_id": "c1",
            "status": "valid", "probability": 0.0, "available_at": cutoff + 1,
        }],
    )
    row = result["rows"][0]
    assert row["submission_status"] == "late"
    assert row["prediction_source"] == "fallback"
    assert row["prediction"] == pytest.approx(0.5)


def test_fallback_must_be_identical_across_arms():
    with pytest.raises(ValueError, match="frozen fallback"):
        score_complete_grid(
            [_row(method="m1", fallback=0.2), _row(method="m2", fallback=0.8)],
            [],
            expected_methods=("m1", "m2"),
        )


def test_measurement_target_contract_contains_all_identity_fields():
    contract = MeasurementTargetContract(
        target_id="t",
        entity="KJFK",
        variable="visibility",
        units="m",
        event_operator="lt",
        threshold=5000.0,
        physical_start=1_000,
        physical_end=2_000,
        report_policy="iem_routine_unique_hour.v1",
        available_at_delay_s=600,
        event_version="h15.visibility.v23",
    )
    assert len(contract.contract_hash) == 64
    assert contract.to_dict()["available_at_delay_s"] == 600
    assert contract.contract_hash != MeasurementTargetContract(
        **{**contract.to_dict(), "threshold": 1000.0}
    ).contract_hash
