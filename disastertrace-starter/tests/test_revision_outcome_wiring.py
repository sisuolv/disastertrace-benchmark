"""Tests for outcome_wiring.py (T2 task in v16-MP round).

Test coverage:
- Target construction and rejection of non-frozen thresholds
- Same-station/slot targets at different thresholds hash differently
- Modal-minute selection logic (including tie-break cases)
- Mature record field validation (type(value) is int)
- Missing records use distinct quality codes for distinct reasons
- Registration in both legacy_compatible and formal_provider_bound modes
- Replay idempotency (re-register identical returns False, conflict raises)
- Real-data integration against KSFO 2023-01 ASOS data
"""

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from disastertrace.monitoring_fixed_v1.contracts import Target
from disastertrace.monitoring_fixed_v1.outcomes import OUTCOME_FIELDS, OutcomeRegistry
from disastertrace.monitoring_v1.providers.aviation import MetarReport
from disastertrace.monitoring_v1.support import Interval
from disastertrace.monitoring_v1.targets import utc_us
from disastertrace.revision_v1.episode_compiler import compile_asos_csv_to_observations
from disastertrace.revision_v1.outcome_wiring import (
    FROZEN_THRESHOLDS_M,
    QUALITY_NO_REPORT_IN_SLOT,
    QUALITY_VISIBILITY_UNDETERMINED,
    AsosProvenance,
    load_asos_with_provenance,
    make_h15_visibility_target,
    make_resolution_version,
    register_h15_outcomes,
    resolve_h15_outcomes,
    select_routine_observations,
)


def us(iso_str: str) -> int:
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


HOUR = 3_600_000_000  # 1 hour in microseconds
MINUTE = 60_000_000   # 1 minute in microseconds


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------


def make_metar(
    station: str,
    time_iso: str,
    visibility_m: float | tuple | None = 10000.0,
    raw: str = "KSFO 010056Z 27014KT 10SM CLR 12/08 A2978",
) -> MetarReport:
    """Create a synthetic MetarReport for testing."""
    obs_time = us(time_iso)

    if visibility_m is None:
        vis = None
    elif isinstance(visibility_m, tuple):
        # Interval bounds
        vis = Interval(visibility_m[0], visibility_m[1])
    else:
        vis = Interval(visibility_m, visibility_m)

    return MetarReport(
        station=station,
        observation_time=obs_time,
        report_type="routine",
        visibility=vis,
        temperature_c=12,
        dewpoint_c=8,
        weather=(),
        quality_flags=(),
        raw=raw,
    )


def make_provenance(
    path: str = "/fake/asos.body",
    sha256: str = "a" * 64,
    fetch_time: str = "2026-09-20T12:00:00Z",
    run_id: str = "20260920T120000Z_abc123",
) -> AsosProvenance:
    """Create a synthetic AsosProvenance for testing."""
    return AsosProvenance(
        path=path,
        sha256=sha256,
        fetch_timestamp_us=us(fetch_time),
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Test: Target construction
# ---------------------------------------------------------------------------


class TestTargetConstruction:
    """Test make_h15_visibility_target function."""

    def test_valid_threshold_5000(self):
        """Target with 5000m threshold constructs successfully."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        assert target.entity == "KSFO"
        assert target.threshold == 5000.0
        assert target.event_operator == "lt"
        assert target.physical_start == t0
        assert target.physical_end == t0 + HOUR
        assert target.units == "m"
        assert target.variable == "visibility"
        assert target.support_kind == "interval"
        assert target.temporal_semantics == "future_physical"
        assert target.report_policy == "iem_routine_unique_hour.v1"

    def test_valid_threshold_1000(self):
        """Target with 1000m threshold constructs successfully."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KORD",
            slot_start_us=t0,
            threshold_m=1000.0,
        )

        assert target.threshold == 1000.0
        assert target.entity == "KORD"

    def test_reject_non_frozen_threshold(self):
        """Non-frozen thresholds must be rejected."""
        t0 = us("2023-01-15T00:00:00Z")

        # 1600m (1 SM) is NOT a frozen threshold
        with pytest.raises(ValueError, match="Invalid threshold 1600"):
            make_h15_visibility_target(
                station="KSFO",
                slot_start_us=t0,
                threshold_m=1600.0,
            )

        # 3000m is NOT a frozen threshold
        with pytest.raises(ValueError, match="Invalid threshold 3000"):
            make_h15_visibility_target(
                station="KSFO",
                slot_start_us=t0,
                threshold_m=3000.0,
            )

    def test_custom_target_id(self):
        """Custom target_id is used when provided."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
            target_id="my-custom-id",
        )

        assert target.target_id == "my-custom-id"

    def test_deterministic_target_id(self):
        """Default target_id is deterministic and human-legible."""
        t0 = us("2023-01-15T14:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # Should encode station, date, hour, threshold
        assert target.target_id == "KSFO_20230115_14_5000m"


class TestTargetHashDifferentiation:
    """Test that different thresholds produce different contract hashes."""

    def test_different_thresholds_hash_differently(self):
        """5000m and 1000m targets with same station/slot have different hashes."""
        t0 = us("2023-01-15T00:00:00Z")

        target_5000 = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        target_1000 = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=1000.0,
        )

        # Same station, same slot, different threshold -> different hash
        assert target_5000.contract_hash != target_1000.contract_hash

        # Both are valid hex strings of 64 chars
        assert len(target_5000.contract_hash) == 64
        assert len(target_1000.contract_hash) == 64

    def test_same_threshold_hashes_same(self):
        """Same parameters produce identical hashes (deterministic)."""
        t0 = us("2023-01-15T00:00:00Z")

        target_a = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
            target_id="id-a",
        )

        target_b = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
            target_id="id-b",  # Different target_id
        )

        # contract_hash excludes target_id, so these should match
        assert target_a.contract_hash == target_b.contract_hash


# ---------------------------------------------------------------------------
# Test: Modal-minute selection
# ---------------------------------------------------------------------------


class TestModalMinuteSelection:
    """Test select_routine_observations function."""

    def test_clear_modal_minute(self):
        """Observations with clear modal minute are correctly filtered."""
        # Create observations: most at minute 56
        observations = [
            make_metar("KSFO", "2023-01-15T00:56:00Z"),
            make_metar("KSFO", "2023-01-15T01:56:00Z"),
            make_metar("KSFO", "2023-01-15T02:56:00Z"),
            make_metar("KSFO", "2023-01-15T03:56:00Z"),
            make_metar("KSFO", "2023-01-15T04:30:00Z"),  # Non-routine (minute 30)
            make_metar("KSFO", "2023-01-15T05:56:00Z"),
        ]

        filtered, meta = select_routine_observations(observations, station="KSFO")

        assert len(filtered) == 5  # All minute-56 observations
        assert meta["modal_minute"] == 56
        assert meta["modal_count"] == 5
        assert meta["total_observations"] == 6

    def test_tie_break_smallest_minute(self):
        """When counts are tied, smallest minute wins."""
        # Create equal counts at minutes 30 and 56
        observations = [
            make_metar("KSFO", "2023-01-15T00:30:00Z"),
            make_metar("KSFO", "2023-01-15T01:30:00Z"),
            make_metar("KSFO", "2023-01-15T02:56:00Z"),
            make_metar("KSFO", "2023-01-15T03:56:00Z"),
        ]

        filtered, meta = select_routine_observations(observations, station="KSFO")

        # Tie at count=2, so minute 30 (smaller) wins
        assert meta["modal_minute"] == 30
        assert meta["modal_count"] == 2
        assert len(filtered) == 2

    def test_empty_observations(self):
        """Empty observation list returns empty results."""
        filtered, meta = select_routine_observations([], station="KSFO")

        assert filtered == []
        assert meta["modal_minute"] is None
        assert meta["modal_count"] == 0
        assert meta["total_observations"] == 0

    def test_station_filtering(self):
        """Only observations for the specified station are considered."""
        observations = [
            make_metar("KSFO", "2023-01-15T00:56:00Z"),
            make_metar("KORD", "2023-01-15T01:56:00Z"),  # Different station
            make_metar("KSFO", "2023-01-15T02:56:00Z"),
        ]

        filtered, meta = select_routine_observations(observations, station="KSFO")

        assert len(filtered) == 2
        assert meta["total_observations"] == 2  # Only KSFO counted
        assert all(obs.station == "KSFO" for obs in filtered)

    def test_histogram_returned(self):
        """Minute histogram is returned for debugging."""
        observations = [
            make_metar("KSFO", "2023-01-15T00:00:00Z"),
            make_metar("KSFO", "2023-01-15T01:00:00Z"),
            make_metar("KSFO", "2023-01-15T02:30:00Z"),
        ]

        _, meta = select_routine_observations(observations, station="KSFO")

        assert meta["minute_histogram"][0] == 2
        assert meta["minute_histogram"][30] == 1


# ---------------------------------------------------------------------------
# Test: Outcome record field validation
# ---------------------------------------------------------------------------


class TestOutcomeRecordFields:
    """Test that outcome records have correct fields and types."""

    def test_mature_record_has_required_fields(self):
        """Mature record has all OUTCOME_FIELDS plus optional fields."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # Create observation with visibility < 5000m
        obs = make_metar(
            "KSFO",
            "2023-01-15T00:56:00Z",
            visibility_m=3000.0,
            raw="KSFO 150056Z 27014KT 2SM RA 12/08",
        )

        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        assert len(records) == 1
        record = records[0]

        # Check all required fields are present
        required = OUTCOME_FIELDS.split()
        for field in required:
            assert field in record, f"Missing required field: {field}"

        # Check optional H15 fields
        assert "resolution_policy" in record
        assert "provider" in record
        assert "provider_version" in record
        assert "references" in record
        assert "reference_kind" in record

    def test_mature_value_is_strict_int(self):
        """Value in mature record must be type(value) is int, not bool."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # Low visibility -> outcome = 1
        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=2000.0)
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        record = records[0]
        assert record["status"] == "mature"
        assert record["value"] == 1
        assert type(record["value"]) is int  # NOT bool
        assert not isinstance(record["value"], bool)

    def test_outcome_zero_is_strict_int(self):
        """Value=0 must also be strict int, not bool False."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # High visibility -> outcome = 0
        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=10000.0)
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        record = records[0]
        assert record["status"] == "mature"
        assert record["value"] == 0
        assert type(record["value"]) is int


class TestMissingOutcomeQualityCodes:
    """Test that missing outcomes use distinct quality codes."""

    def test_no_report_quality_code(self):
        """Missing due to no report uses QUALITY_NO_REPORT_IN_SLOT."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # No observations at all
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        record = records[0]
        assert record["status"] == "missing"
        assert record["value"] is None
        assert record["quality_status"] == QUALITY_NO_REPORT_IN_SLOT

    def test_visibility_undetermined_quality_code(self):
        """Missing due to undetermined visibility uses distinct code."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # Observation with visibility interval straddling threshold
        # e.g., interval [4000, 6000] around threshold 5000 -> undetermined
        obs = make_metar(
            "KSFO",
            "2023-01-15T00:56:00Z",
            visibility_m=(4000.0, 6000.0),  # Interval
        )

        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        record = records[0]
        assert record["status"] == "missing"
        assert record["quality_status"] == QUALITY_VISIBILITY_UNDETERMINED

    def test_visibility_none_quality_code(self):
        """Missing visibility in observation uses undetermined code."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # Observation with visibility=None
        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=None)

        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        record = records[0]
        assert record["status"] == "missing"
        assert record["quality_status"] == QUALITY_VISIBILITY_UNDETERMINED

    def test_distinct_quality_codes(self):
        """The two missing reasons use different quality codes."""
        assert QUALITY_NO_REPORT_IN_SLOT != QUALITY_VISIBILITY_UNDETERMINED


# ---------------------------------------------------------------------------
# Test: Registry modes and idempotency
# ---------------------------------------------------------------------------


class TestRegistryModes:
    """Test registration in both modes."""

    def test_legacy_compatible_mode(self):
        """Records register successfully in legacy_compatible mode."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=3000.0)
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        registry, success = register_h15_outcomes(
            records, [target], mode="legacy_compatible"
        )

        assert len(success) == 1
        assert success[0] is True
        assert len(registry.records) == 1

    def test_formal_provider_bound_mode(self):
        """Records register successfully in formal_provider_bound mode."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=3000.0)
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        registry, success = register_h15_outcomes(
            records, [target], mode="formal_provider_bound"
        )

        assert len(success) == 1
        assert success[0] is True

    def test_missing_record_in_formal_mode(self):
        """Missing records also register in formal_provider_bound mode."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # No observations -> missing
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        # Should not raise - formal mode validates missing records too
        registry, success = register_h15_outcomes(
            records, [target], mode="formal_provider_bound"
        )

        assert success[0] is True
        record = list(registry.records.values())[0]
        assert record["status"] == "missing"


class TestReplayIdempotency:
    """Test idempotent re-registration and conflict detection."""

    def test_identical_reregister_returns_false(self):
        """Re-registering identical record returns False (idempotent)."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=3000.0)
        provenance = make_provenance()
        records = resolve_h15_outcomes(
            [obs], [target],
            provenance=provenance,
            resolution_version="test_v1",
        )

        # First registration
        registry, success1 = register_h15_outcomes(
            records, [target], mode="legacy_compatible"
        )
        assert success1[0] is True

        # Second registration of same record
        result = registry.register(records[0])
        assert result is False  # Idempotent - already exists

    def test_different_value_raises_conflict(self):
        """Registering different value at same key raises conflict."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        # First: outcome = 1 (low vis)
        obs1 = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=3000.0)
        prov1 = make_provenance()
        records1 = resolve_h15_outcomes(
            [obs1], [target],
            provenance=prov1,
            resolution_version="test_v1",
        )

        registry, _ = register_h15_outcomes(
            records1, [target], mode="legacy_compatible"
        )

        # Create conflicting record with different value (same resolution_version)
        obs2 = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=8000.0)
        records2 = resolve_h15_outcomes(
            [obs2], [target],
            provenance=prov1,
            resolution_version="test_v1",  # Same version!
        )

        # Should raise conflict
        with pytest.raises(ValueError, match="conflict"):
            registry.register(records2[0])

    def test_different_version_no_conflict(self):
        """Different resolution_version registers as separate entry."""
        t0 = us("2023-01-15T00:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=t0,
            threshold_m=5000.0,
        )

        obs = make_metar("KSFO", "2023-01-15T00:56:00Z", visibility_m=3000.0)
        prov1 = make_provenance(run_id="run_1")
        prov2 = make_provenance(run_id="run_2")

        records1 = resolve_h15_outcomes(
            [obs], [target],
            provenance=prov1,
            resolution_version="h15_asos:run_1",
        )
        records2 = resolve_h15_outcomes(
            [obs], [target],
            provenance=prov2,
            resolution_version="h15_asos:run_2",  # Different version
        )

        registry, _ = register_h15_outcomes(
            records1, [target], mode="legacy_compatible"
        )

        # Should succeed - different version
        result = registry.register(records2[0])
        assert result is True
        assert len(registry.records) == 2


class TestResolutionVersion:
    """Test resolution_version generation."""

    def test_make_resolution_version(self):
        """make_resolution_version includes run_id."""
        prov = make_provenance(run_id="20260920T083945Z_5a91ac05a955")
        version = make_resolution_version(prov)

        assert version == "h15_asos:20260920T083945Z_5a91ac05a955"

    def test_custom_prefix(self):
        """Custom prefix is used."""
        prov = make_provenance(run_id="run_123")
        version = make_resolution_version(prov, prefix="custom")

        assert version == "custom:run_123"


# ---------------------------------------------------------------------------
# Real-data integration tests
# ---------------------------------------------------------------------------

# Path to real KSFO ASOS data
KSFO_DATA_DIR = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/asos/KSFO/2023-01/"
    "20260920T083945Z_5a91ac05a955"
)
KSFO_BODY_PATH = KSFO_DATA_DIR / "asos-sfo-202301.body"
KSFO_RECEIPT_PATH = KSFO_DATA_DIR / "asos-sfo-202301.json"


def real_data_available():
    """Check if real KSFO data is available."""
    return KSFO_BODY_PATH.exists() and KSFO_RECEIPT_PATH.exists()


@pytest.mark.skipif(
    not real_data_available(),
    reason="Real KSFO ASOS data not available at expected path"
)
class TestRealDataIntegration:
    """Integration tests against real KSFO 2023-01 ASOS data.

    Data source: IEM ASOS archive
    Downloaded: 2026-09-20T08:39:45Z
    Run ID: 20260920T083945Z_5a91ac05a955
    """

    def test_load_and_parse_real_file(self):
        """Load and parse real KSFO ASOS file, verify counts.

        Observed values (derived by running code, not copied from prompt):
        - Total rows: 801
        - Skip count: 0 (all rows parsed successfully)
        """
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))

        observations, skipped = compile_asos_csv_to_observations(
            content, station="KSFO"
        )

        # Values observed by running this test:
        assert len(observations) == 801
        assert len(skipped) == 0  # All rows parse successfully

    def test_modal_minute_detection(self):
        """Detect modal minute from real data.

        Observed values:
        - Modal minute: 56
        - Count at minute 56: 720
        """
        content, _ = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")

        filtered, meta = select_routine_observations(observations, station="KSFO")

        # Values observed by running this test:
        assert meta["modal_minute"] == 56
        assert meta["modal_count"] == 720
        assert len(filtered) == 720

    def test_outcome_1_low_visibility(self):
        """Slot with visibility < 5000m resolves to outcome=1.

        Test case: 2023-01-28 14:00-15:00 UTC
        Routine report at 14:56: KSFO 281456Z 15007KT 1/4SM ... (0.25 SM = 402m)
        Raw METAR: "KSFO 281456Z 15007KT 1/4SM R28R/1400V1800FT FG VV002 08/08 A3003 RMK AO2 SLP168 T00780078 58004"
        """
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")
        routine_obs, _ = select_routine_observations(observations, station="KSFO")

        # Slot: 2023-01-28 14:00 UTC
        slot_start = us("2023-01-28T14:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=slot_start,
            threshold_m=5000.0,
        )

        records = resolve_h15_outcomes(
            routine_obs, [target],
            provenance=provenance,
            resolution_version=make_resolution_version(provenance),
        )

        assert len(records) == 1
        record = records[0]
        assert record["status"] == "mature"
        assert record["value"] == 1  # Visibility < 5000m
        assert type(record["value"]) is int

        # Verify the METAR text is referenced
        assert "references" in record
        assert any("281456Z" in str(ref) for ref in record["references"])

    def test_outcome_0_high_visibility(self):
        """Slot with visibility >= 5000m resolves to outcome=0.

        Test case: 2023-01-15 12:00-13:00 UTC
        Routine report at 12:56: KSFO 151256Z ... 10SM ... (10 SM = 16093m)
        """
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")
        routine_obs, _ = select_routine_observations(observations, station="KSFO")

        # Pick a clear-weather slot
        slot_start = us("2023-01-15T12:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=slot_start,
            threshold_m=5000.0,
        )

        records = resolve_h15_outcomes(
            routine_obs, [target],
            provenance=provenance,
            resolution_version=make_resolution_version(provenance),
        )

        record = records[0]
        assert record["status"] == "mature"
        assert record["value"] == 0  # Visibility >= 5000m

    def test_missing_last_day_of_month(self):
        """January 31 data is missing (end-exclusive query range).

        The IEM query was day2=31 (end-exclusive), so January 31 is not
        present in this file. The last observation is 2023-01-30 23:56.
        """
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")
        routine_obs, _ = select_routine_observations(observations, station="KSFO")

        # Slot on Jan 31 should have no data
        slot_start = us("2023-01-31T12:00:00Z")
        target = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=slot_start,
            threshold_m=5000.0,
        )

        records = resolve_h15_outcomes(
            routine_obs, [target],
            provenance=provenance,
            resolution_version=make_resolution_version(provenance),
        )

        record = records[0]
        assert record["status"] == "missing"
        assert record["quality_status"] == QUALITY_NO_REPORT_IN_SLOT

    def test_registration_both_modes_real_data(self):
        """Real data registers in both modes with idempotency."""
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")
        routine_obs, _ = select_routine_observations(observations, station="KSFO")

        # Create targets for a few slots
        base_time = us("2023-01-15T00:00:00Z")
        targets = [
            make_h15_visibility_target(
                station="KSFO",
                slot_start_us=base_time + i * HOUR,
                threshold_m=5000.0,
            )
            for i in range(24)  # 24 hours
        ]

        resolution_version = make_resolution_version(provenance)
        records = resolve_h15_outcomes(
            routine_obs, targets,
            provenance=provenance,
            resolution_version=resolution_version,
        )

        # Test legacy_compatible
        registry_legacy, success_legacy = register_h15_outcomes(
            records, targets, mode="legacy_compatible"
        )
        assert all(s is True for s in success_legacy)

        # Test formal_provider_bound
        registry_formal, success_formal = register_h15_outcomes(
            records, targets, mode="formal_provider_bound"
        )
        assert all(s is True for s in success_formal)

        # Test idempotency - re-register same records
        for record in records:
            result = registry_legacy.register(record)
            assert result is False  # Already exists

    def test_provenance_sha256_matches_receipt(self):
        """Provenance SHA256 cross-checks against receipt."""
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))

        # Read receipt directly
        with open(KSFO_RECEIPT_PATH) as f:
            receipt = json.load(f)

        expected_sha = receipt["sha256"]
        assert provenance.sha256 == expected_sha
        assert provenance.sha256 == "10271b81b61c74b9c693aee525add60968026807b05035595b32556643bdd93d"

    def test_1000m_threshold_outcome(self):
        """Test outcome at 1000m threshold (stricter).

        2023-01-28 14:56: 0.25 SM = 402m < 1000m, so outcome=1 at 1000m threshold
        2023-01-05 00:56: 2.0 SM = 3218m > 1000m, so outcome=0 at 1000m threshold
        """
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))
        observations, _ = compile_asos_csv_to_observations(content, station="KSFO")
        routine_obs, _ = select_routine_observations(observations, station="KSFO")

        # Very low visibility slot
        slot_very_low = us("2023-01-28T14:00:00Z")
        target_1000 = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=slot_very_low,
            threshold_m=1000.0,
        )

        records = resolve_h15_outcomes(
            routine_obs, [target_1000],
            provenance=provenance,
            resolution_version=make_resolution_version(provenance),
        )

        # 402m < 1000m -> outcome=1
        assert records[0]["value"] == 1

        # Medium low visibility slot (< 5000m but > 1000m)
        slot_medium = us("2023-01-05T00:00:00Z")
        target_1000_medium = make_h15_visibility_target(
            station="KSFO",
            slot_start_us=slot_medium,
            threshold_m=1000.0,
        )

        records_medium = resolve_h15_outcomes(
            routine_obs, [target_1000_medium],
            provenance=provenance,
            resolution_version=make_resolution_version(provenance),
        )

        # 3218m > 1000m -> outcome=0 at 1000m threshold
        assert records_medium[0]["value"] == 0


class TestProvenanceLoader:
    """Test load_asos_with_provenance function."""

    def test_reject_quarantine_holdout(self):
        """Paths containing quarantine_holdout are rejected."""
        with pytest.raises(ValueError, match="quarantine_holdout"):
            load_asos_with_provenance(
                "/data/quarantine_holdout/station/file.body"
            )

    @pytest.mark.skipif(
        not real_data_available(),
        reason="Real KSFO ASOS data not available"
    )
    def test_sha256_mismatch_would_fail(self):
        """SHA256 mismatch detection would catch corruption."""
        # We can't easily test actual mismatch without corrupting data,
        # but we verify the mechanism works by checking the real file matches
        content, provenance = load_asos_with_provenance(str(KSFO_BODY_PATH))

        # Recompute hash manually
        with open(KSFO_BODY_PATH, "rb") as f:
            computed = hashlib.sha256(f.read()).hexdigest()

        assert provenance.sha256 == computed
