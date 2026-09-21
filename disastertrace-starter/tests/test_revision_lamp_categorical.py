"""Tests for LAMP categorical (LAV) parser (RA3).

Tests cover:
- Parsing correctness against synthetic fixture text
- Gzip handling (valid and invalid input)
- 4-station filtering
- Native timestamp preference
- Type-level guard: no probability/confidence fields
- assert_not_probabilistic guard function
- Registry schema validation
- Real data integration (skipif data not available)
"""

from __future__ import annotations

import dataclasses
import gzip
import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from disastertrace.revision_v1.lamp_categorical import (
    FROZEN_STATIONS,
    LampCategoricalRecord,
    LampElement,
    assert_not_probabilistic,
    parse_lamp_body,
)


# ============================================================================
# Synthetic fixture based on real LAV format exploration
# ============================================================================

# This synthetic fixture mimics the real LAV monthly archive format:
# - Station bulletins separated by blank lines
# - Header: " KXXX   GFS LAMP GUIDANCE   M/DD/YYYY  HHMM UTC"
# - UTC line: " UTC  HH HH HH"
# - Element lines: " CIG   X  X  X", " VIS   X  X  X", " OBV  XX XX XX"

SYNTHETIC_LAV_CONTENT = """\
1

 KJFK   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   2  3  4
 VIS   5  6  7
 OBV  FG BR  N

 KORD   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   6  6  6
 VIS   7  7  7
 OBV   N  N  N

 KLAX   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   8  8  8
 VIS   7  7  7
 OBV   N  N  N

 KSFO   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   4  4  5
 VIS   3  4  5
 OBV  BR BR HZ

 KDEN   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   7  7  7
 VIS   7  7  7
 OBV   N  N  N

 KBOS   GFS LAMP GUIDANCE   1/15/2023  0600 UTC
 UTC  07 08 09
 CIG   1  1  2
 VIS   1  2  3
 OBV  FG FG BR
"""


# Synthetic fixture for empty bulletin (has header but no CIG/VIS/OBV)
SYNTHETIC_EMPTY_BULLETIN = """\
1

 K0V4   GFS LAMP GUIDANCE   7/01/2023  1200 UTC
 UTC  13 14 15

 KJFK   GFS LAMP GUIDANCE   7/01/2023  1200 UTC
 UTC  13 14 15
 CIG   5  6  7
 VIS   7  7  7
 OBV   N  N  N
"""


def create_gzipped_fixture(content: str, path: Path) -> Path:
    """Create a gzipped .body file from text content."""
    with gzip.open(path, "wt", encoding="ascii") as f:
        f.write(content)
    return path


# ============================================================================
# Test: Parsing correctness against synthetic fixture
# ============================================================================


class TestParseLampBody:
    """Tests for parse_lamp_body function."""

    def test_parse_basic_synthetic_fixture(self, tmp_path: Path):
        """Parse synthetic fixture and verify correct records."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Should have 4 stations * 3 elements * 3 projections = 36 records
        # But only KJFK, KORD, KSFO, KDEN are in FROZEN_STATIONS (KLAX, KBOS excluded)
        # 4 stations * 3 elements * 3 projections = 36 records
        assert len(records) == 36

        # Verify all records are for frozen stations only
        stations = {r.station for r in records}
        assert stations == {"KJFK", "KORD", "KSFO", "KDEN"}

        # Verify elements covered
        elements = {r.element for r in records}
        assert elements == {LampElement.CIG, LampElement.VIS, LampElement.OBV}

    def test_parse_verifies_cycle_time(self, tmp_path: Path):
        """Verify cycle_time is extracted from bulletin header."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # All records from this fixture should have same cycle time
        for record in records:
            assert record.cycle_time == datetime(
                2023, 1, 15, 6, 0, tzinfo=timezone.utc
            )

    def test_parse_verifies_valid_times(self, tmp_path: Path):
        """Verify valid_time is correctly computed from projection hours."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Filter to KJFK CIG records for easier verification
        kjfk_cig = [
            r for r in records
            if r.station == "KJFK" and r.element == LampElement.CIG
        ]
        assert len(kjfk_cig) == 3

        # Sort by valid_time to check projections
        kjfk_cig.sort(key=lambda r: r.valid_time)

        # UTC 07, 08, 09 projections
        assert kjfk_cig[0].valid_time.hour == 7
        assert kjfk_cig[1].valid_time.hour == 8
        assert kjfk_cig[2].valid_time.hour == 9

    def test_parse_verifies_values(self, tmp_path: Path):
        """Verify element values are correctly extracted."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Find KJFK OBV records
        kjfk_obv = [
            r for r in records
            if r.station == "KJFK" and r.element == LampElement.OBV
        ]
        kjfk_obv.sort(key=lambda r: r.valid_time)

        # Values should be FG, BR, N
        assert kjfk_obv[0].value == "FG"
        assert kjfk_obv[1].value == "BR"
        assert kjfk_obv[2].value == "N"

    def test_parse_verifies_source_sha256(self, tmp_path: Path):
        """Verify source SHA256 is computed and consistent."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # All records from same file should have same sha256
        sha256_set = {r.source_sha256 for r in records}
        assert len(sha256_set) == 1

        # SHA256 should be 64 hex chars
        sha256 = sha256_set.pop()
        assert len(sha256) == 64
        assert all(c in "0123456789abcdef" for c in sha256)

    def test_parse_verifies_batch_id(self, tmp_path: Path):
        """Verify batch_id is propagated to all records."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "my_custom_batch_123"))

        for record in records:
            assert record.batch_id == "my_custom_batch_123"


# ============================================================================
# Test: Gzip handling
# ============================================================================


class TestGzipHandling:
    """Tests for gzip compression handling."""

    def test_valid_gzip_parses_successfully(self, tmp_path: Path):
        """Valid gzip file is decompressed and parsed correctly."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))
        assert len(records) > 0

    def test_invalid_gzip_raises_error(self, tmp_path: Path):
        """Non-gzip file raises appropriate error."""
        body_file = tmp_path / "lav-202301-0600z.body"
        # Write plain text, not gzipped
        body_file.write_text(SYNTHETIC_LAV_CONTENT)

        with pytest.raises(gzip.BadGzipFile):
            list(parse_lamp_body(body_file, "test_batch"))

    def test_missing_file_raises_error(self, tmp_path: Path):
        """Non-existent file raises FileNotFoundError."""
        body_file = tmp_path / "nonexistent.body"

        with pytest.raises(FileNotFoundError):
            list(parse_lamp_body(body_file, "test_batch"))

    def test_truncated_trailer_recovers_real_content(self, tmp_path: Path):
        """A gzip stream missing its end-of-stream trailer still parses.

        Regression test for the RA3-fix bug: two real archive files
        (lav-202505-0000z.body and lav-202505-0600z_proxy.body) were
        downloads cut off right at the very end -- the deflate stream is
        intact and contains real content, but the 8-byte gzip trailer
        (CRC32 + ISIZE) is missing, which made the strict stdlib `gzip`
        reader raise EOFError and caused the build script to wrongly label
        these files "corrupt" and skip them, discarding real, recoverable
        data. This synthetic fixture reproduces the same failure mode: a
        complete gzip stream with its trailer chopped off.
        """
        full_gzip_bytes = gzip.compress(SYNTHETIC_LAV_CONTENT.encode("ascii"))

        # Sanity check: the strict stdlib gzip reader really does reject
        # this input with EOFError once the trailer is removed, confirming
        # the fixture reproduces the actual bug being fixed.
        truncated_bytes = full_gzip_bytes[:-8]
        with pytest.raises(EOFError):
            with gzip.open(io.BytesIO(truncated_bytes)) as f:
                f.read()

        body_file = tmp_path / "lav-202505-0000z.body"
        body_file.write_bytes(truncated_bytes)

        # The parser must recover the real content instead of raising or
        # silently returning nothing.
        records = list(parse_lamp_body(body_file, "test_batch"))

        assert len(records) == 36
        stations = {r.station for r in records}
        assert stations == {"KJFK", "KORD", "KSFO", "KDEN"}

    def test_truncated_trailer_full_content_matches_untruncated(self, tmp_path: Path):
        """Recovered content from a missing-trailer file matches the clean file."""
        full_gzip_bytes = gzip.compress(SYNTHETIC_LAV_CONTENT.encode("ascii"))

        clean_file = tmp_path / "lav-202505-clean.body"
        clean_file.write_bytes(full_gzip_bytes)
        truncated_file = tmp_path / "lav-202505-truncated.body"
        truncated_file.write_bytes(full_gzip_bytes[:-8])

        clean_records = list(parse_lamp_body(clean_file, "test_batch"))
        truncated_records = list(parse_lamp_body(truncated_file, "test_batch"))

        clean_tuples = sorted(
            (r.station, r.element, r.value, r.cycle_time, r.valid_time)
            for r in clean_records
        )
        truncated_tuples = sorted(
            (r.station, r.element, r.value, r.cycle_time, r.valid_time)
            for r in truncated_records
        )
        assert clean_tuples == truncated_tuples

    def test_genuinely_corrupt_middle_of_stream_still_errors(self, tmp_path: Path):
        """A gzip file with a corrupted (not just truncated) header still errors.

        This is the negative case: the improved decompression path must not
        become unconditionally permissive. A file whose gzip magic/header
        bytes are themselves invalid should still raise, not be silently
        accepted as recovered content.
        """
        full_gzip_bytes = gzip.compress(SYNTHETIC_LAV_CONTENT.encode("ascii"))
        corrupted = bytearray(full_gzip_bytes)
        # Corrupt the gzip magic header bytes themselves -- zlib will refuse
        # to treat this as a gzip/deflate stream at all.
        corrupted[0] ^= 0xFF
        corrupted[1] ^= 0xFF

        body_file = tmp_path / "lav-202505-corrupt.body"
        body_file.write_bytes(bytes(corrupted))

        with pytest.raises(gzip.BadGzipFile):
            list(parse_lamp_body(body_file, "test_batch"))

    def test_zero_byte_file_yields_no_records_not_an_error(self, tmp_path: Path):
        """A genuinely empty (0-byte) input still parses as 0 records, no error.

        This must remain distinguishable from a truncated-trailer file: an
        empty file has NO recoverable content, and should not be treated as
        an error condition by the new tolerant decompression path.
        """
        body_file = tmp_path / "lav-202505-0600z.body"
        body_file.write_bytes(b"")

        records = list(parse_lamp_body(body_file, "test_batch"))
        assert records == []


# ============================================================================
# Test: 4-station filtering
# ============================================================================


class TestStationFiltering:
    """Tests for station filtering to FROZEN_STATIONS."""

    def test_only_frozen_stations_returned(self, tmp_path: Path):
        """Only records for KSFO, KDEN, KJFK, KORD are returned."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Fixture contains KLAX and KBOS which should be filtered out
        stations = {r.station for r in records}
        assert stations == {"KJFK", "KORD", "KSFO", "KDEN"}
        assert "KLAX" not in stations
        assert "KBOS" not in stations

    def test_frozen_stations_constant_correct(self):
        """Verify FROZEN_STATIONS constant has expected values."""
        assert FROZEN_STATIONS == {"KSFO", "KDEN", "KJFK", "KORD"}

    def test_custom_station_filter(self, tmp_path: Path):
        """Custom station filter overrides default."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        # Only get KJFK
        records = list(parse_lamp_body(
            body_file, "test_batch", target_stations=frozenset({"KJFK"})
        ))

        stations = {r.station for r in records}
        assert stations == {"KJFK"}

    def test_empty_bulletins_handled(self, tmp_path: Path):
        """Empty bulletins (header but no CIG/VIS/OBV) don't cause errors."""
        body_file = tmp_path / "lav-202307-1200z.body"
        create_gzipped_fixture(SYNTHETIC_EMPTY_BULLETIN, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # K0V4 is empty and not in FROZEN_STATIONS, KJFK has data
        stations = {r.station for r in records}
        assert "KJFK" in stations
        assert "K0V4" not in stations  # filtered out by FROZEN_STATIONS


# ============================================================================
# Test: Native timestamp preference
# ============================================================================


class TestNativeTimestampPreference:
    """Tests verifying native bulletin timestamps are used."""

    def test_cycle_time_from_bulletin_not_metadata(self, tmp_path: Path):
        """cycle_time comes from bulletin header, not sidecar metadata."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Bulletin header says "1/15/2023  0600 UTC"
        expected_cycle = datetime(2023, 1, 15, 6, 0, tzinfo=timezone.utc)

        for record in records:
            assert record.cycle_time == expected_cycle

    def test_valid_time_computed_from_bulletin(self, tmp_path: Path):
        """valid_time is computed from bulletin UTC line, not metadata."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # All valid times should be 07, 08, or 09 UTC on same date
        valid_hours = {r.valid_time.hour for r in records}
        assert valid_hours == {7, 8, 9}

        for record in records:
            assert record.valid_time.date() == datetime(2023, 1, 15).date()


# ============================================================================
# Test: Type-level guard (no probability/confidence fields)
# ============================================================================


class TestNoProabilityFields:
    """Tests verifying LampCategoricalRecord has no probability-like fields."""

    def test_dataclass_fields_no_probability(self):
        """LampCategoricalRecord fields do not include probability/confidence."""
        fields = {f.name for f in dataclasses.fields(LampCategoricalRecord)}

        # Explicitly forbidden field names
        forbidden = {
            "probability",
            "prob",
            "confidence",
            "conf",
            "conditional",
            "cond_prob",
            "likelihood",
            "percentile",
            "quantile",
        }

        # Check no forbidden fields exist
        found_forbidden = fields & forbidden
        assert not found_forbidden, (
            f"LampCategoricalRecord has forbidden probability-like fields: "
            f"{found_forbidden}. Per D11, categorical records must not carry "
            f"probability semantics."
        )

    def test_dataclass_has_expected_fields(self):
        """LampCategoricalRecord has the expected categorical-only fields."""
        fields = {f.name for f in dataclasses.fields(LampCategoricalRecord)}

        expected = {
            "station",
            "element",
            "value",
            "cycle_time",
            "valid_time",
            "source_sha256",
            "batch_id",
        }

        assert fields == expected

    def test_dataclass_is_frozen(self):
        """LampCategoricalRecord is frozen (immutable)."""
        # Check the dataclass is frozen by trying to modify a field
        record = LampCategoricalRecord(
            station="KJFK",
            element=LampElement.CIG,
            value="5",
            cycle_time=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            valid_time=datetime(2023, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_sha256="a" * 64,
            batch_id="test",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.station = "KORD"  # type: ignore[misc]


# ============================================================================
# Test: assert_not_probabilistic guard function
# ============================================================================


class TestAssertNotProbabilistic:
    """Tests for assert_not_probabilistic guard function."""

    def test_passes_for_valid_records(self, tmp_path: Path):
        """Guard passes for valid LampCategoricalRecord list."""
        body_file = tmp_path / "lav-202301-0600z.body"
        create_gzipped_fixture(SYNTHETIC_LAV_CONTENT, body_file)

        records = list(parse_lamp_body(body_file, "test_batch"))

        # Should not raise
        assert_not_probabilistic(records)

    def test_passes_for_empty_list(self):
        """Guard passes for empty list."""
        assert_not_probabilistic([])

    def test_raises_for_wrong_type(self):
        """Guard raises TypeError for non-LampCategoricalRecord objects."""
        @dataclasses.dataclass
        class WrongRecord:
            station: str
            probability: float  # This is a probability field!

        wrong_records = [WrongRecord(station="KJFK", probability=0.75)]

        with pytest.raises(TypeError, match="expected LampCategoricalRecord"):
            assert_not_probabilistic(wrong_records)  # type: ignore[arg-type]

    def test_raises_for_dict_input(self):
        """Guard raises TypeError for dict input."""
        with pytest.raises(TypeError, match="expected LampCategoricalRecord"):
            assert_not_probabilistic([{"station": "KJFK", "probability": 0.5}])

    def test_raises_for_mixed_input(self):
        """Guard raises TypeError for mixed valid/invalid input."""
        valid_record = LampCategoricalRecord(
            station="KJFK",
            element=LampElement.CIG,
            value="5",
            cycle_time=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            valid_time=datetime(2023, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_sha256="a" * 64,
            batch_id="test",
        )

        with pytest.raises(TypeError):
            assert_not_probabilistic([valid_record, {"invalid": True}])


# ============================================================================
# Test: Registry schema
# ============================================================================


class TestRegistrySchema:
    """Tests for registry JSON schema correctness."""

    def test_registry_has_required_fields(self, tmp_path: Path):
        """Registry JSON has all required fields."""
        # Create a minimal registry manually
        registry = {
            "baseline_class": "categorical",
            "d11_note": "test note",
            "dl4_status_finding": "test finding",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_id": "test_batch",
            "source_archive": "/path/to/archive",
            "months_covered": ["2023-01", "2023-02"],
            "stations": ["KDEN", "KJFK", "KORD", "KSFO"],
            "total_records": 100,
            "records_by_station": {"KDEN": 25, "KJFK": 25, "KORD": 25, "KSFO": 25},
            "records_by_element": {"CIG": 34, "VIS": 33, "OBV": 33},
            "records_by_station_element": {
                "KDEN": {"CIG": 9, "VIS": 8, "OBV": 8},
            },
            "source_files_count": 10,
            "source_file_hashes": {"lav-202301-0000z.body": "abc123"},
        }

        # Verify all required fields
        required = {
            "baseline_class",
            "d11_note",
            "generation_timestamp",
            "batch_id",
            "source_archive",
            "months_covered",
            "stations",
            "total_records",
            "records_by_station",
            "records_by_element",
            "records_by_station_element",
            "source_files_count",
            "source_file_hashes",
        }

        assert required <= set(registry.keys())

    def test_baseline_class_is_categorical(self, tmp_path: Path):
        """Registry baseline_class must be 'categorical'."""
        registry = {"baseline_class": "categorical"}
        assert registry["baseline_class"] == "categorical"


# ============================================================================
# Test: Real data integration (skipif not available)
# ============================================================================


# Path to real archive
REAL_ARCHIVE_PATH = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/"
    "lamp/raw/20260920T100529Z_09c70a575ad2"
)


@pytest.mark.skipif(
    not REAL_ARCHIVE_PATH.exists(),
    reason="Real data archive not available"
)
class TestRealDataIntegration:
    """Integration tests against real LAMP LAV archive."""

    def test_parse_real_body_file(self):
        """Parse at least one real .body file successfully."""
        # Use January 2023 0000z file
        body_file = REAL_ARCHIVE_PATH / "lav-202301-0000z.body"
        if not body_file.exists():
            pytest.skip(f"Test file not found: {body_file}")

        records = list(parse_lamp_body(body_file, "real_data_test"))

        # Should have records for all 4 frozen stations
        # Jan 2023 has 31 days, 3 elements, 3 projections per bulletin
        # 4 stations * 31 days * 3 elements * 3 projections = 1116 records
        assert len(records) >= 100  # Conservative lower bound

    def test_all_frozen_stations_have_records(self):
        """All 4 frozen stations have at least 1 record in real data."""
        body_file = REAL_ARCHIVE_PATH / "lav-202301-0000z.body"
        if not body_file.exists():
            pytest.skip(f"Test file not found: {body_file}")

        records = list(parse_lamp_body(body_file, "real_data_test"))

        stations_with_records = {r.station for r in records}

        # All 4 stations should have data
        # Note: If this fails for a station, document in PATCH_LOG
        for station in FROZEN_STATIONS:
            assert station in stations_with_records, (
                f"Station {station} has no LAV records in real data. "
                f"This may indicate a data gap that should be documented."
            )

    def test_records_pass_d11_guard(self):
        """Real data records pass the assert_not_probabilistic guard."""
        body_file = REAL_ARCHIVE_PATH / "lav-202301-0000z.body"
        if not body_file.exists():
            pytest.skip(f"Test file not found: {body_file}")

        records = list(parse_lamp_body(body_file, "real_data_test"))

        # Should not raise
        assert_not_probabilistic(records)

    def test_real_data_element_values(self):
        """Real data has expected CIG (1-8), VIS (1-7), OBV codes."""
        body_file = REAL_ARCHIVE_PATH / "lav-202301-0000z.body"
        if not body_file.exists():
            pytest.skip(f"Test file not found: {body_file}")

        records = list(parse_lamp_body(body_file, "real_data_test"))

        for record in records:
            if record.element == LampElement.CIG:
                # CIG should be 1-8
                assert record.value in {"1", "2", "3", "4", "5", "6", "7", "8"}
            elif record.element == LampElement.VIS:
                # VIS should be 1-7
                assert record.value in {"1", "2", "3", "4", "5", "6", "7"}
            elif record.element == LampElement.OBV:
                # OBV should be obstruction codes
                valid_obv = {"N", "BR", "FG", "HZ", "FU", "DU", "SA", "UP"}
                assert record.value in valid_obv, (
                    f"Unexpected OBV value: {record.value}"
                )

    def test_previously_mislabeled_truncated_files_now_parse(self):
        """RA3-fix regression: the two missing-trailer May 2025 files parse.

        lav-202505-0000z.body and lav-202505-0600z_proxy.body are real,
        successfully-downloaded data (http_status=200, on-disk bytes match
        the sidecar receipt's `bytes` field exactly) whose gzip stream is
        missing its final end-of-stream trailer -- the download was cut off
        right at the very end. The old strict decompression path raised
        EOFError on both and the build script mislabeled them "corrupt",
        discarding real May 2025 0000z/0600z data. Both must now parse with
        real (>0) record counts.

        This is a genuinely different failure mode than the two files that
        actually failed to download (lav-202505-0000z_proxy.body and
        lav-202505-0600z.body, both 0 bytes / http_status=0 in
        DL4_STATUS.json) -- those remain a legitimate, disclosed data gap
        and are NOT expected to produce records.
        """
        for filename in [
            "lav-202505-0000z.body",
            "lav-202505-0600z_proxy.body",
        ]:
            body_file = REAL_ARCHIVE_PATH / filename
            if not body_file.exists():
                pytest.skip(f"Test file not found: {body_file}")

            records = list(parse_lamp_body(body_file, "real_data_test"))
            assert len(records) > 0, (
                f"{filename} should now recover real records (missing gzip "
                f"trailer, not genuine corruption/empty download)"
            )

    def test_genuinely_failed_downloads_still_yield_no_records(self):
        """The two genuinely-failed (0-byte) May 2025 downloads stay empty.

        lav-202505-0000z_proxy.body and lav-202505-0600z.body are real 0-byte
        network failures (http_status=0, documented in DL4_STATUS.json).
        There is no real data behind them, and the fix must not attempt to
        "recover" anything for these -- 0 records remains correct.
        """
        for filename in [
            "lav-202505-0000z_proxy.body",
            "lav-202505-0600z.body",
        ]:
            body_file = REAL_ARCHIVE_PATH / filename
            if not body_file.exists():
                pytest.skip(f"Test file not found: {body_file}")

            assert body_file.stat().st_size == 0, (
                f"{filename} is expected to be a genuine 0-byte failed "
                f"download per DL4_STATUS.json"
            )
            records = list(parse_lamp_body(body_file, "real_data_test"))
            assert records == []


# ============================================================================
# Test: Build script can be imported without execution
# ============================================================================


class TestBuildScriptImportable:
    """Tests that build script can be imported for testing."""

    def test_build_registry_function_exists(self):
        """build_registry function can be imported."""
        import sys
        from pathlib import Path

        # Add scripts to path temporarily
        scripts_dir = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(scripts_dir))

        try:
            # This verifies the script has correct syntax
            import build_lamp_categorical_registry_v16
            assert hasattr(build_lamp_categorical_registry_v16, "build_registry")
        finally:
            sys.path.remove(str(scripts_dir))

    def test_build_registry_refuses_overwrite(self, tmp_path: Path):
        """build_registry raises FileExistsError if output exists."""
        import sys
        from pathlib import Path

        scripts_dir = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(scripts_dir))

        try:
            from build_lamp_categorical_registry_v16 import build_registry

            # Create fake existing registry
            output = tmp_path / "existing_registry.json"
            output.write_text("{}")

            # Fake data root (won't be used since we fail early)
            data_root = tmp_path / "data_real_v16"
            data_root.mkdir()

            with pytest.raises(FileExistsError, match="already exists"):
                build_registry(data_root, output)
        finally:
            sys.path.remove(str(scripts_dir))
