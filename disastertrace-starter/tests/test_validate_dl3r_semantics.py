"""Unit tests for scripts/validate_dl3r_semantics.py.

Tests parsing logic, BBB/kind consistency, and latest_issuance grouping
without requiring the full real dataset.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# Import the validation script functions
import sys

_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "scripts"))
sys.path.insert(0, str(_project / "src"))

from validate_dl3r_semantics import (
    EXPECTED_FILES,
    count_soh_etx,
    extract_issued_yyyymmddhhmm,
    issued_at_to_yyyymmddhhmm,
    parse_reconciliation_table,
    validate_wmo_bbb_consistency,
    check_latest_issuance_uniqueness,
    cross_check_timestamps,
    extract_csv_product_ids,
    sha256_file,
)


class TestExpectedFiles:
    """Test that expected file enumeration is correct."""

    def test_expected_files_count(self):
        """Verify we have exactly 140 expected files."""
        assert len(EXPECTED_FILES) == 140

    def test_no_feb_2025_in_expected(self):
        """Verify 202502 is not in expected files (holdout)."""
        for station, year_month in EXPECTED_FILES:
            assert year_month != "202502", f"Found holdout month for {station}"

    def test_all_four_stations(self):
        """Verify all 4 stations are present."""
        stations = {st for st, _ in EXPECTED_FILES}
        assert stations == {"KSFO", "KDEN", "KJFK", "KORD"}

    def test_35_months_per_station(self):
        """Verify 35 months per station."""
        for station in ["KSFO", "KDEN", "KJFK", "KORD"]:
            station_months = [ym for st, ym in EXPECTED_FILES if st == station]
            assert len(station_months) == 35, f"{station} has {len(station_months)} months"


class TestCountSohEtx:
    """Test SOH/ETX frame counting."""

    def test_empty_text(self):
        """Empty text has zero counts."""
        assert count_soh_etx("") == (0, 0)

    def test_single_frame(self):
        """Single frame with SOH and ETX."""
        text = "\x01FRAME_CONTENT\x03"
        assert count_soh_etx(text) == (1, 1)

    def test_multiple_frames(self):
        """Multiple frames."""
        text = "\x01FRAME1\x03\x01FRAME2\x03\x01FRAME3\x03"
        assert count_soh_etx(text) == (3, 3)

    def test_unbalanced(self):
        """Unbalanced SOH/ETX counts."""
        text = "\x01FRAME1\x03\x01PARTIAL"
        assert count_soh_etx(text) == (2, 1)


class TestExtractIssuedYyyyMmDdHhMm:
    """Test product_id timestamp extraction."""

    def test_standard_product_id(self):
        """Standard product_id with BBB suffix."""
        pid = "202301010214-KMTR-FTUS46-TAFSFO-AAA"
        assert extract_issued_yyyymmddhhmm(pid) == "202301010214"

    def test_product_id_no_bbb(self):
        """Product_id without BBB suffix (original)."""
        pid = "202301010530-KMTR-FTUS46-TAFSFO"
        assert extract_issued_yyyymmddhhmm(pid) == "202301010530"

    def test_invalid_product_id(self):
        """Invalid product_id returns None."""
        assert extract_issued_yyyymmddhhmm("invalid") is None
        assert extract_issued_yyyymmddhhmm("short-id") is None


class TestIssuedAtToYyyyMmDdHhMm:
    """Test microseconds timestamp conversion."""

    def test_known_timestamp(self):
        """Convert known timestamp to string."""
        # 2023-01-01 02:14:00 UTC = 1672539240 seconds
        ts_us = 1672539240_000000
        result = issued_at_to_yyyymmddhhmm(ts_us)
        assert result == "202301010214"

    def test_midnight(self):
        """Convert midnight timestamp."""
        # 2023-06-15 00:00:00 UTC
        ts_us = 1686787200_000000
        result = issued_at_to_yyyymmddhhmm(ts_us)
        assert result == "202306150000"


class TestValidateWmoBbbConsistency:
    """Test wmo_bbb <-> amendment_kind validation."""

    def test_all_consistent(self):
        """All packages are consistent - no violations."""
        packages = [
            {"source_id": "1", "wmo_bbb": None, "amendment_kind": "original"},
            {"source_id": "2", "wmo_bbb": "AAA", "amendment_kind": "AMD"},
            {"source_id": "3", "wmo_bbb": "AAB", "amendment_kind": "AMD"},
            {"source_id": "4", "wmo_bbb": "CCA", "amendment_kind": "COR"},
        ]
        violations = validate_wmo_bbb_consistency(packages)
        assert len(violations) == 0

    def test_bbb_none_but_amd(self):
        """wmo_bbb=None but amendment_kind=AMD is a violation."""
        packages = [
            {"source_id": "1", "wmo_bbb": None, "amendment_kind": "AMD"},
        ]
        violations = validate_wmo_bbb_consistency(packages)
        assert len(violations) == 1
        assert "Expected original, got AMD" in violations[0]["error"]

    def test_bbb_aaa_but_original(self):
        """wmo_bbb=AAA but amendment_kind=original is a violation."""
        packages = [
            {"source_id": "1", "wmo_bbb": "AAA", "amendment_kind": "original"},
        ]
        violations = validate_wmo_bbb_consistency(packages)
        assert len(violations) == 1
        assert "Expected AMD, got original" in violations[0]["error"]

    def test_bbb_cca_but_amd(self):
        """wmo_bbb=CCA but amendment_kind=AMD is a violation."""
        packages = [
            {"source_id": "1", "wmo_bbb": "CCA", "amendment_kind": "AMD"},
        ]
        violations = validate_wmo_bbb_consistency(packages)
        assert len(violations) == 1
        assert "Expected COR, got AMD" in violations[0]["error"]

    def test_unknown_bbb_pattern(self):
        """Unknown BBB pattern (e.g., RRA) is flagged."""
        packages = [
            {"source_id": "1", "wmo_bbb": "RRA", "amendment_kind": "AMD"},
        ]
        violations = validate_wmo_bbb_consistency(packages)
        assert len(violations) == 1
        assert "Unknown wmo_bbb pattern" in violations[0]["error"]


class TestCheckLatestIssuanceUniqueness:
    """Test latest_issuance conflict detection."""

    def test_no_groups(self):
        """Empty package list has no conflicts."""
        conflicts = check_latest_issuance_uniqueness([])
        assert len(conflicts) == 0

    def test_single_package_per_group(self):
        """Single package per validity window - no conflicts possible."""
        packages = [
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,
                "native_semantics_sha256": "hash1",
            },
            {
                "station": "KSFO",
                "valid_start": 2000000,
                "valid_end": 3000000,
                "issued_at": 1900000,
                "native_semantics_sha256": "hash2",
            },
        ]
        conflicts = check_latest_issuance_uniqueness(packages)
        assert len(conflicts) == 0

    def test_multiple_same_latest_unique_hash(self):
        """Multiple packages at same latest issued_at with same hash - OK."""
        packages = [
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,
                "native_semantics_sha256": "hash1",
                "source_id": "a",
            },
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,
                "native_semantics_sha256": "hash1",
                "source_id": "b",
            },
        ]
        conflicts = check_latest_issuance_uniqueness(packages)
        assert len(conflicts) == 0

    def test_multiple_same_latest_different_hash(self):
        """Multiple packages at same latest issued_at with different hashes - CONFLICT."""
        packages = [
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,
                "native_semantics_sha256": "hash1",
                "source_id": "a",
            },
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,
                "native_semantics_sha256": "hash2",
                "source_id": "b",
            },
        ]
        conflicts = check_latest_issuance_uniqueness(packages)
        assert len(conflicts) == 1
        assert conflicts[0]["distinct_hashes"] == 2

    def test_superseded_different_hash_ok(self):
        """Older (superseded) packages with different hash is OK."""
        packages = [
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 800000,  # Older - superseded
                "native_semantics_sha256": "hash_old",
                "source_id": "old",
            },
            {
                "station": "KSFO",
                "valid_start": 1000000,
                "valid_end": 2000000,
                "issued_at": 900000,  # Latest
                "native_semantics_sha256": "hash_new",
                "source_id": "new",
            },
        ]
        conflicts = check_latest_issuance_uniqueness(packages)
        assert len(conflicts) == 0


class TestCrossCheckTimestamps:
    """Test timestamp cross-checking logic."""

    def test_perfect_match(self):
        """All timestamps match."""
        # 2023-01-01 02:14:00 UTC = 1672539240 seconds
        # 2023-01-01 03:14:00 UTC = 1672542840 seconds
        packages = [
            {"issued_at": 1672539240_000000},  # 2023-01-01 02:14
            {"issued_at": 1672542840_000000},  # 2023-01-01 03:14
        ]
        csv_product_ids = {
            "202301010214-KMTR-FTUS46-TAFSFO-AAA",
            "202301010314-KMTR-FTUS46-TAFSFO",
        }
        result = cross_check_timestamps(packages, csv_product_ids)
        assert result["in_raw_not_csv"] == []
        assert result["in_csv_not_raw"] == []

    def test_raw_has_extra(self):
        """Raw has timestamp not in CSV."""
        packages = [
            {"issued_at": 1672539240_000000},  # 2023-01-01 02:14
            {"issued_at": 1672542840_000000},  # 2023-01-01 03:14
        ]
        csv_product_ids = {
            "202301010214-KMTR-FTUS46-TAFSFO-AAA",
        }
        result = cross_check_timestamps(packages, csv_product_ids)
        assert "202301010314" in result["in_raw_not_csv"]
        assert result["in_csv_not_raw"] == []

    def test_csv_has_extra(self):
        """CSV has timestamp not in raw."""
        packages = [
            {"issued_at": 1672539240_000000},  # 2023-01-01 02:14
        ]
        csv_product_ids = {
            "202301010214-KMTR-FTUS46-TAFSFO-AAA",
            "202301010314-KMTR-FTUS46-TAFSFO",
        }
        result = cross_check_timestamps(packages, csv_product_ids)
        assert result["in_raw_not_csv"] == []
        assert "202301010314" in result["in_csv_not_raw"]


class TestParseReconciliationTable:
    """Test reconciliation table parsing."""

    def test_parse_valid_table(self):
        """Parse a valid reconciliation table."""
        content = """# Reconciliation

## Full 144-Row Detail Table

| Station | Year-Month | CSV unique product_id | Raw text frame count | Diff% | Backfill count | Final coverage count | Final coverage% | Notes |
|---------|------------|----------------------|---------------------|-------|----------------|---------------------|-----------------|-------|
| KSFO | 202301 | 302 | 303 | 0.33% | 0 | 303 | 100.33% | - |
| KDEN | 202506 | 330 | 318 | -3.64% | 12 | 330 | 100.0% | BACKFILLED |
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_reconciliation_table(Path(f.name))

        assert ("KSFO", "202301") in result
        assert result[("KSFO", "202301")]["csv_product_id_count"] == 302
        assert result[("KSFO", "202301")]["raw_frame_count"] == 303
        assert result[("KSFO", "202301")]["backfill_count"] == 0

        assert ("KDEN", "202506") in result
        assert result[("KDEN", "202506")]["backfill_count"] == 12
        assert result[("KDEN", "202506")]["notes"] == "BACKFILLED"


class TestExtractCsvProductIds:
    """Test CSV product_id extraction."""

    def test_extract_from_csv(self):
        """Extract product_ids from CSV content."""
        csv_content = """station,valid,product_id
KSFO,2023-01-01,202301010214-KMTR-FTUS46-TAFSFO-AAA
KSFO,2023-01-01,202301010530-KMTR-FTUS46-TAFSFO
KSFO,2023-01-02,202301020214-KMTR-FTUS46-TAFSFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".body", delete=False) as f:
            f.write(csv_content)
            f.flush()
            result = extract_csv_product_ids(Path(f.name))

        assert len(result) == 3
        assert "202301010214-KMTR-FTUS46-TAFSFO-AAA" in result
        assert "202301010530-KMTR-FTUS46-TAFSFO" in result

    def test_empty_file_returns_empty(self):
        """Empty file returns empty set (no proxy)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".body", delete=False) as f:
            # Write nothing
            f.flush()
            result = extract_csv_product_ids(Path(f.name))

        assert result == set()


class TestSha256File:
    """Test SHA256 file hashing."""

    def test_known_content(self):
        """Hash of known content."""
        content = b"Hello, World!"
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(content)
            f.flush()
            result = sha256_file(Path(f.name))

        # Known SHA256 of "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert result == expected


class TestHardGateLogic:
    """Test hard gate file enumeration logic."""

    def test_all_months_present(self):
        """Verify expected months span Jan 2023 to Dec 2025, excluding Feb 2025."""
        year_months = [ym for _, ym in EXPECTED_FILES]
        unique_months = sorted(set(year_months))

        # Should have 35 unique months
        assert len(unique_months) == 35

        # First month should be Jan 2023
        assert unique_months[0] == "202301"

        # Last month should be Dec 2025
        assert unique_months[-1] == "202512"

        # Feb 2025 should NOT be present
        assert "202502" not in unique_months

        # All other months 2023-2025 should be present
        expected_present = []
        for year in [2023, 2024, 2025]:
            for month in range(1, 13):
                ym = f"{year:04d}{month:02d}"
                if ym != "202502":
                    expected_present.append(ym)

        assert set(unique_months) == set(expected_present)
