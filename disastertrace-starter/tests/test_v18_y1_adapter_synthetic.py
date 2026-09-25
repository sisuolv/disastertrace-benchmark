import pytest

from disastertrace.revision_v1.y1_adapter_synthetic import (
    RealReceiptRejected,
    SYNTHETIC_AVAILABILITY_BASIS,
    settle_synthetic_outcomes,
    synthetic_metar,
    synthetic_provenance,
    v18_target_to_h15_target,
)

STATION = "KSFO"
TARGET_START = 1_735_707_600_000_000
TARGET_END = 1_735_711_200_000_000  # +1h


def _target(threshold_m=5000.0):
    return v18_target_to_h15_target(
        episode_id="v18-dev-KSFO-2025-01-01", station=STATION,
        target_start_us=TARGET_START, target_end_us=TARGET_END, threshold_m=threshold_m,
    )


def test_target_id_carries_sub_hour_precision_not_the_hour_only_default():
    target = _target()
    assert target.physical_start == TARGET_START
    assert target.physical_end == TARGET_END
    assert "v18-dev-KSFO-2025-01-01" in target.target_id


def test_a_genuinely_non_hour_window_keeps_exact_microsecond_precision():
    """The test above uses exactly a 1-hour window, which never exercises
    make_h15_visibility_target's own float-hours round-trip -- independent
    review found the original version of this test's name promised
    sub-hour precision it never actually checked (mutating the adapter to
    hardcode support_window_hours=1.0 still passed it). A 65-minute window
    is the smallest one review found loses exactly 1 microsecond through
    int(hours * 3_600_000_000) without the adapter's own correction."""
    start = 1_735_707_600_000_000
    end = start + 65 * 60_000_000  # 65 minutes, not a multiple of an hour
    target = v18_target_to_h15_target(
        episode_id="v18-dev-KSFO-65min", station=STATION,
        target_start_us=start, target_end_us=end, threshold_m=5000.0,
    )
    assert target.physical_start == start
    assert target.physical_end == end  # exact, not end - 1


def test_settle_produces_a_real_mature_outcome_from_a_synthetic_observation():
    prov = synthetic_provenance(fixture_label="below-threshold", fetch_timestamp_us=TARGET_END)
    obs = [synthetic_metar(station=STATION, observation_time_us=TARGET_START + 600_000_000, visibility_m=3000.0)]
    (record,) = settle_synthetic_outcomes(
        targets=[_target()], observations=obs, provenance=prov, resolution_version="test-v1",
    )
    assert record["status"] == "mature"
    assert record["value"] == 1  # 3000m < 5000m threshold: event occurred
    assert record["availability_basis"] == SYNTHETIC_AVAILABILITY_BASIS
    assert record["provenance"] == {"source_revision": "SYNTHETIC"}


def test_settle_produces_missing_when_no_observation_falls_in_the_slot():
    prov = synthetic_provenance(fixture_label="no-obs", fetch_timestamp_us=TARGET_END)
    (record,) = settle_synthetic_outcomes(
        targets=[_target()], observations=[], provenance=prov, resolution_version="test-v1",
    )
    assert record["status"] == "missing"
    assert record["value"] is None


def test_refuses_a_provenance_whose_sha256_matches_a_tracked_real_receipt():
    real_sha = "a" * 64
    prov = synthetic_provenance(fixture_label="disguised", fetch_timestamp_us=TARGET_START)
    # Simulate a caller accidentally handing in a real receipt's hash via a
    # tampered provenance object (frozen dataclass -> construct directly).
    from dataclasses import replace
    tampered = replace(prov, sha256=real_sha)
    with pytest.raises(RealReceiptRejected):
        settle_synthetic_outcomes(
            targets=[_target()], observations=[], provenance=tampered, resolution_version="test-v1",
            tracked_receipt_sha256=frozenset({real_sha}),
        )


def test_refuses_a_provenance_whose_run_id_is_not_synthetic():
    from dataclasses import replace
    prov = synthetic_provenance(fixture_label="x", fetch_timestamp_us=TARGET_START)
    tampered = replace(prov, run_id="20260920T091835Z_5f8988c0e49a")  # a real-looking run id
    with pytest.raises(RealReceiptRejected):
        settle_synthetic_outcomes(
            targets=[_target()], observations=[], provenance=tampered, resolution_version="test-v1",
        )


def test_module_imports_only_pure_outcome_wiring_functions_no_fetch_code():
    import disastertrace.revision_v1.y1_adapter_synthetic as mod
    import inspect
    source = inspect.getsource(mod)
    for forbidden in ("urlopen", "requests", "load_asos_with_provenance", "http"):
        assert forbidden not in source, f"adapter must not reference {forbidden!r}"
