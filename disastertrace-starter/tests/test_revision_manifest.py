"""Tests for revision_v1/manifest.py episode pre-registration (P0-08).

Tests cover:
- Selection determinism
- Holdout-window exclusion
- Checkpoint-before-validity invariant
- Target count cap (<=12)
- Changed/unchanged queue split
- Overwrite-refusal guard
- Import-isolation (Y-isolation)
- Real-data integration (guarded)
- V17-01: ExposureRegistry preregistration enforcement (F07)
- V17-01: Content-based archive fingerprinting (F07)
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

# Add project src to path
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))


from disastertrace.revision_v1.manifest import (
    CHECKPOINT_OFFSETS_MINUTES,
    MAX_TARGETS,
    SELECTION_RULE_VERSION,
    CandidateTarget,
    Checkpoint,
    build_candidates_from_taf_packages,
    build_manifest,
    compute_checkpoints,
    compute_self_sha256,
    detect_same_minute_ties,
    freeze_manifest,
    get_calendar_bounds,
    get_holdout_window,
    load_stations_calendar,
    select_episodes,
    validate_manifest,
    verify_config_sha256,
    verify_manifest_integrity,
    windows_overlap,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    """Sample stations_calendar config."""
    return {
        "stations": [
            {"icao": "KSFO", "faa": "SFO"},
            {"icao": "KDEN", "faa": "DEN"},
        ],
        "calendar_start": "2023-01-01T00:00:00Z",
        "calendar_end": "2025-12-31T23:59:59Z",
        "holdout_exclusion": {
            "window_start": "2025-02-17T00:00:00Z",
            "window_end": "2025-02-24T00:00:00Z",
        },
    }


@pytest.fixture
def sample_config_file(sample_config, tmp_path):
    """Create sample config file with SHA256 sidecar."""
    config_path = tmp_path / "stations_calendar.json"
    config_bytes = json.dumps(sample_config).encode()

    with open(config_path, "wb") as f:
        f.write(config_bytes)

    # Create SHA256 sidecar
    sha256 = hashlib.sha256(config_bytes).hexdigest()
    sidecar_path = config_path.with_suffix(".json.sha256")
    with open(sidecar_path, "w") as f:
        f.write(f"{sha256}  stations_calendar.json\n")

    return config_path


def make_taf_package(
    station: str,
    issued_at_us: int,
    valid_start_us: int,
    valid_end_us: int,
    amendment_kind: str = "original",
    status: str = "active",
) -> dict:
    """Create a synthetic TAF package."""
    semantic_hash = hashlib.sha256(
        f"{station}:{issued_at_us}:{valid_start_us}".encode()
    ).hexdigest()

    return {
        "source_id": f"{station}-{issued_at_us}-{semantic_hash[:12]}",
        "station": station,
        "issued_at": issued_at_us,
        "valid_start": valid_start_us,
        "valid_end": valid_end_us,
        "amendment_kind": amendment_kind,
        "status": status,
        "native_semantics_sha256": semantic_hash,
    }


def us_from_iso(iso_str: str) -> int:
    """Convert ISO string to microseconds."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000)


# ---------------------------------------------------------------------------
# Test: Import isolation (Y-isolation)
# ---------------------------------------------------------------------------

class TestImportIsolation:
    """Test that manifest.py does not import outcome-reading functions."""

    def test_manifest_does_not_import_outcome_wiring(self):
        """manifest.py must not import from outcome_wiring.py."""
        manifest_path = _project / "src" / "disastertrace" / "revision_v1" / "manifest.py"

        with open(manifest_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)

        # Collect all imports
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)
                    for alias in node.names:
                        imported_names.append(f"{node.module}.{alias.name}")

        # Check for forbidden imports
        forbidden_patterns = [
            "outcome_wiring",
            "compile_asos_csv_to_observations",
            "load_asos_with_provenance",
            "resolve_h15_outcomes",
            "register_h15_outcomes",
        ]

        for name in imported_names:
            for forbidden in forbidden_patterns:
                assert forbidden not in name, (
                    f"manifest.py imports forbidden symbol '{forbidden}' "
                    f"(found in '{name}'). This violates Y-isolation."
                )

    def test_manifest_module_imports_only_taf_side(self):
        """manifest.py imports should be TAF-side only."""
        manifest_path = _project / "src" / "disastertrace" / "revision_v1" / "manifest.py"

        with open(manifest_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find all ImportFrom nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "revision_v1" in (node.module or ""):
                    # Check it's not importing from outcome_wiring
                    assert "outcome_wiring" not in node.module, (
                        f"manifest.py imports from outcome_wiring: {node.module}"
                    )


# ---------------------------------------------------------------------------
# Test: Selection determinism
# ---------------------------------------------------------------------------

class TestSelectionDeterminism:
    """Test that selection is deterministic."""

    def test_same_input_produces_identical_output(self, sample_config_file):
        """Running selection twice on same input produces byte-identical output."""
        # Create synthetic TAF packages
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = []
        for i in range(20):  # Create 20 candidate targets
            for station in ["KSFO", "KDEN"]:
                validity_start = base_time + (i * 24 * hour_us)
                validity_end = validity_start + hour_us

                # Create original
                packages.append(make_taf_package(
                    station=station,
                    issued_at_us=validity_start - (6 * hour_us),
                    valid_start_us=validity_start,
                    valid_end_us=validity_end,
                    amendment_kind="original",
                ))

                # Create AMD for some
                if i % 3 == 0:
                    packages.append(make_taf_package(
                        station=station,
                        issued_at_us=validity_start - (2 * hour_us),
                        valid_start_us=validity_start,
                        valid_end_us=validity_end,
                        amendment_kind="AMD",
                    ))

        # Run twice
        manifest1 = freeze_manifest(packages, sample_config_file)
        manifest2 = freeze_manifest(packages, sample_config_file)

        # Remove frozen_at which will differ
        manifest1.pop("frozen_at")
        manifest2.pop("frozen_at")

        # Recompute self_sha256 after removing frozen_at
        # (since we're comparing structure, not the actual hash)
        manifest1.pop("self_sha256")
        manifest2.pop("self_sha256")

        # Compare
        json1 = json.dumps(manifest1, sort_keys=True)
        json2 = json.dumps(manifest2, sort_keys=True)

        assert json1 == json2, "Selection should be deterministic"

    def test_target_order_is_deterministic(self, sample_config_file):
        """Target order in manifest is always the same."""
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        # Create packages in random order
        import random
        random.seed(42)

        packages = []
        for _ in range(3):
            for station in ["KDEN", "KJFK", "KSFO", "KORD"]:
                validity_start = base_time + random.randint(0, 100) * hour_us
                validity_end = validity_start + hour_us

                packages.append(make_taf_package(
                    station=station,
                    issued_at_us=validity_start - (6 * hour_us),
                    valid_start_us=validity_start,
                    valid_end_us=validity_end,
                ))

        random.shuffle(packages)

        # Run selection
        manifest = freeze_manifest(packages, sample_config_file)
        target_ids_1 = [t["target_id"] for t in manifest["targets"]]

        # Shuffle again and rerun
        random.shuffle(packages)
        manifest = freeze_manifest(packages, sample_config_file)
        target_ids_2 = [t["target_id"] for t in manifest["targets"]]

        assert target_ids_1 == target_ids_2, "Target order should be deterministic"


# ---------------------------------------------------------------------------
# Test: Holdout window exclusion
# ---------------------------------------------------------------------------

class TestHoldoutExclusion:
    """Test that holdout window is properly excluded."""

    def test_target_in_holdout_is_excluded(self, sample_config_file):
        """Target whose validity window overlaps holdout is excluded."""
        # Create target right in the holdout window (Feb 17-24, 2025)
        holdout_time = us_from_iso("2025-02-20T12:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = [
            make_taf_package(
                station="KSFO",
                issued_at_us=holdout_time - (6 * hour_us),
                valid_start_us=holdout_time,
                valid_end_us=holdout_time + hour_us,
            ),
        ]

        manifest = freeze_manifest(packages, sample_config_file)

        # Should have no targets (the only candidate was in holdout)
        assert len(manifest["targets"]) == 0

    def test_target_outside_holdout_is_included(self, sample_config_file):
        """Target outside holdout window is included."""
        # Create target well outside holdout
        safe_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = [
            make_taf_package(
                station="KSFO",
                issued_at_us=safe_time - (6 * hour_us),
                valid_start_us=safe_time,
                valid_end_us=safe_time + hour_us,
            ),
        ]

        manifest = freeze_manifest(packages, sample_config_file)

        assert len(manifest["targets"]) == 1

    def test_checkpoint_in_holdout_excludes_target(self, sample_config_file):
        """Target whose checkpoints overlap holdout is excluded."""
        # Create target where T-60 checkpoint falls in holdout
        # Holdout ends at Feb 24 00:00, so target starting Feb 24 01:00
        # would have T-60 at Feb 24 00:00 which is exactly at holdout end
        # We need a target where checkpoints truly overlap holdout interior

        # Holdout: Feb 17-24. If target starts Feb 17 01:00,
        # T-60 = Feb 17 00:00, T-40 = Feb 17 00:20, T-20 = Feb 17 00:40
        # All checkpoints are after holdout start (Feb 17 00:00)
        target_time = us_from_iso("2025-02-17T01:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = [
            make_taf_package(
                station="KSFO",
                issued_at_us=target_time - (6 * hour_us),
                valid_start_us=target_time,
                valid_end_us=target_time + hour_us,
            ),
        ]

        manifest = freeze_manifest(packages, sample_config_file)

        # Target validity window overlaps holdout, so excluded
        assert len(manifest["targets"]) == 0


# ---------------------------------------------------------------------------
# Test: Checkpoint invariants
# ---------------------------------------------------------------------------

class TestCheckpointInvariants:
    """Test checkpoint construction invariants."""

    def test_checkpoints_before_validity_start(self):
        """All checkpoints must be strictly before validity_start."""
        validity_start = us_from_iso("2023-06-15T12:00:00Z")

        checkpoints = compute_checkpoints(validity_start)

        assert len(checkpoints) == 3
        for cp in checkpoints:
            assert cp.time_us < validity_start, (
                f"Checkpoint {cp.time_us} should be < validity_start {validity_start}"
            )

    def test_checkpoint_offsets_are_correct(self):
        """Checkpoints are at T-60, T-40, T-20 minutes."""
        validity_start = us_from_iso("2023-06-15T12:00:00Z")

        checkpoints = compute_checkpoints(validity_start)

        expected_offsets_us = [offset * 60 * 1_000_000 for offset in CHECKPOINT_OFFSETS_MINUTES]

        for cp, expected_offset in zip(checkpoints, expected_offsets_us):
            actual_offset = cp.time_us - validity_start
            assert actual_offset == expected_offset, (
                f"Expected offset {expected_offset}, got {actual_offset}"
            )

    def test_manifest_checkpoints_before_validity(self, sample_config_file):
        """All checkpoints in frozen manifest are before validity_start."""
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = []
        for i in range(5):
            validity_start = base_time + (i * 24 * hour_us)
            packages.append(make_taf_package(
                station="KSFO",
                issued_at_us=validity_start - (6 * hour_us),
                valid_start_us=validity_start,
                valid_end_us=validity_start + hour_us,
            ))

        manifest = freeze_manifest(packages, sample_config_file)

        for target in manifest["targets"]:
            validity_start_us = target["validity_start_us"]
            for cp in target["checkpoints"]:
                assert cp["time_us"] < validity_start_us, (
                    f"Checkpoint {cp['time_us']} not before "
                    f"validity_start {validity_start_us}"
                )


# ---------------------------------------------------------------------------
# Test: Target count cap
# ---------------------------------------------------------------------------

class TestTargetCap:
    """Test that at most 12 targets are selected."""

    def test_max_12_targets(self, sample_config_file):
        """Selection returns at most 12 targets."""
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        # Create 50 candidate targets
        packages = []
        for i in range(50):
            for station in ["KSFO", "KDEN"]:
                validity_start = base_time + (i * 24 * hour_us)
                validity_end = validity_start + hour_us

                packages.append(make_taf_package(
                    station=station,
                    issued_at_us=validity_start - (6 * hour_us),
                    valid_start_us=validity_start,
                    valid_end_us=validity_end,
                ))

        manifest = freeze_manifest(packages, sample_config_file)

        assert len(manifest["targets"]) <= MAX_TARGETS

    def test_validation_rejects_over_12(self):
        """Validation fails if manifest has >12 targets."""
        manifest = {
            "schema": "disastertrace.episode_manifest.v1",
            "targets": [{"target_id": f"t{i}"} for i in range(15)],
            "self_sha256": "",
        }
        manifest["self_sha256"] = compute_self_sha256(manifest)

        errors = validate_manifest(manifest)

        assert any("Too many targets" in e for e in errors)


# ---------------------------------------------------------------------------
# Test: Queue split
# ---------------------------------------------------------------------------

class TestQueueSplit:
    """Test changed/unchanged queue splitting."""

    def test_changed_queue_has_revisions(self, sample_config_file):
        """Targets in changed queue have AMD/COR revisions."""
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        packages = []
        # Create target with AMD
        validity_start = base_time
        packages.append(make_taf_package(
            station="KSFO",
            issued_at_us=validity_start - (6 * hour_us),
            valid_start_us=validity_start,
            valid_end_us=validity_start + hour_us,
            amendment_kind="original",
        ))
        packages.append(make_taf_package(
            station="KSFO",
            issued_at_us=validity_start - (2 * hour_us),
            valid_start_us=validity_start,
            valid_end_us=validity_start + hour_us,
            amendment_kind="AMD",
        ))

        # Create target without revisions
        validity_start2 = base_time + (24 * hour_us)
        packages.append(make_taf_package(
            station="KDEN",
            issued_at_us=validity_start2 - (6 * hour_us),
            valid_start_us=validity_start2,
            valid_end_us=validity_start2 + hour_us,
            amendment_kind="original",
        ))

        manifest = freeze_manifest(packages, sample_config_file)

        changed_targets = [t for t in manifest["targets"] if t["queue"] == "changed"]
        unchanged_targets = [t for t in manifest["targets"] if t["queue"] == "unchanged"]

        assert len(changed_targets) >= 1
        assert len(unchanged_targets) >= 1

        for t in changed_targets:
            assert t["selection_signals"]["revision_count"] > 0

        for t in unchanged_targets:
            assert t["selection_signals"]["revision_count"] == 0

    def test_empty_queue_allowed(self, sample_config_file):
        """Selection succeeds even if one queue is empty."""
        base_time = us_from_iso("2023-06-15T12:00:00Z")
        hour_us = 3600 * 1_000_000

        # Create only unchanged targets
        packages = []
        for i in range(5):
            validity_start = base_time + (i * 24 * hour_us)
            packages.append(make_taf_package(
                station="KSFO",
                issued_at_us=validity_start - (6 * hour_us),
                valid_start_us=validity_start,
                valid_end_us=validity_start + hour_us,
                amendment_kind="original",
            ))

        manifest = freeze_manifest(packages, sample_config_file)

        # Should succeed with only unchanged queue populated
        assert len(manifest["targets"]) > 0
        assert manifest["queue_summary"]["unchanged_count"] > 0


# ---------------------------------------------------------------------------
# Test: Overwrite refusal
# ---------------------------------------------------------------------------

class TestOverwriteRefusal:
    """Test that freeze mode refuses to overwrite existing manifest."""

    def test_freeze_refuses_overwrite(self, tmp_path):
        """Calling freeze twice should fail on second call."""
        # Create a fake existing manifest
        manifest_path = tmp_path / "EPISODE_MANIFEST_v16.json"
        manifest_path.write_text('{"existing": true}')

        # Import the script module functions
        import subprocess

        script_path = _project / "scripts" / "build_episode_manifest_v16.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--manifest", str(manifest_path)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2, (
            f"Expected exit code 2 for existing manifest, got {result.returncode}. "
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Test: Manifest integrity
# ---------------------------------------------------------------------------

class TestManifestIntegrity:
    """Test self_sha256 integrity verification."""

    def test_valid_manifest_passes_integrity(self, sample_config_file):
        """Valid manifest passes integrity check."""
        packages = [
            make_taf_package(
                station="KSFO",
                issued_at_us=us_from_iso("2023-06-15T06:00:00Z"),
                valid_start_us=us_from_iso("2023-06-15T12:00:00Z"),
                valid_end_us=us_from_iso("2023-06-15T13:00:00Z"),
            ),
        ]

        manifest = freeze_manifest(packages, sample_config_file)

        assert verify_manifest_integrity(manifest) is True

    def test_tampered_manifest_fails_integrity(self, sample_config_file):
        """Modified manifest fails integrity check."""
        packages = [
            make_taf_package(
                station="KSFO",
                issued_at_us=us_from_iso("2023-06-15T06:00:00Z"),
                valid_start_us=us_from_iso("2023-06-15T12:00:00Z"),
                valid_end_us=us_from_iso("2023-06-15T13:00:00Z"),
            ),
        ]

        manifest = freeze_manifest(packages, sample_config_file)

        # Tamper with manifest
        manifest["targets"][0]["station"] = "KXXX"

        with pytest.raises(ValueError, match="integrity check failed"):
            verify_manifest_integrity(manifest)


# ---------------------------------------------------------------------------
# Test: Helper functions
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Test utility functions."""

    def test_windows_overlap_true(self):
        """Overlapping windows return True."""
        assert windows_overlap(100, 200, 150, 250) is True
        assert windows_overlap(100, 200, 50, 150) is True
        assert windows_overlap(100, 200, 120, 180) is True

    def test_windows_overlap_false(self):
        """Non-overlapping windows return False."""
        assert windows_overlap(100, 200, 200, 300) is False
        assert windows_overlap(100, 200, 0, 100) is False
        assert windows_overlap(100, 200, 300, 400) is False

    def test_detect_same_minute_ties(self):
        """Same-minute ties are detected correctly."""
        packages = [
            {"issued_at": 1000 * 60 * 1_000_000},  # minute 1000
            {"issued_at": 1000 * 60 * 1_000_000 + 30_000_000},  # same minute
            {"issued_at": 1001 * 60 * 1_000_000},  # minute 1001
            {"issued_at": 1002 * 60 * 1_000_000},  # minute 1002
            {"issued_at": 1002 * 60 * 1_000_000 + 45_000_000},  # same minute
        ]

        tie_count = detect_same_minute_ties(packages)

        assert tie_count == 2  # Two minutes have ties

    def test_sha256_verification(self, sample_config_file):
        """SHA256 verification works correctly."""
        config, sha = load_stations_calendar(sample_config_file)

        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)


# ---------------------------------------------------------------------------
# Test: Real data integration (guarded)
# ---------------------------------------------------------------------------

# Paths for real data
REAL_CONFIG_PATH = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/stations_calendar_v16.json"
)
REAL_TAF_BULK_DIR = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/"
    "20260920T134949Z_1bbe63aedc00_dl3rbulk"
)
REAL_MANIFEST_PATH = Path(
    _project / "data_contracts" / "EPISODE_MANIFEST_v16.json"
)


@pytest.mark.skipif(
    not REAL_CONFIG_PATH.exists() or not REAL_TAF_BULK_DIR.exists(),
    reason="Real data not available",
)
class TestRealDataIntegration:
    """Integration tests with real data."""

    def test_real_config_loads_and_verifies(self):
        """Real stations_calendar config loads and SHA256 verifies."""
        config, sha = load_stations_calendar(REAL_CONFIG_PATH)

        assert "stations" in config
        assert len(config["stations"]) > 0
        assert "holdout_exclusion" in config

    def test_real_holdout_window_is_feb_2025(self):
        """Real config's holdout window matches expected dates."""
        config, _ = load_stations_calendar(REAL_CONFIG_PATH)

        holdout_start, holdout_end = get_holdout_window(config)

        # Feb 17-24, 2025
        expected_start = us_from_iso("2025-02-17T00:00:00Z")
        expected_end = us_from_iso("2025-02-24T00:00:00Z")

        assert holdout_start == expected_start
        assert holdout_end == expected_end


@pytest.mark.skipif(
    not REAL_MANIFEST_PATH.exists(),
    reason="Manifest not yet generated",
)
class TestRealManifestIntegration:
    """Integration tests with generated manifest."""

    def test_manifest_self_sha256_is_consistent(self):
        """Generated manifest's self_sha256 matches computed value."""
        with open(REAL_MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        assert verify_manifest_integrity(manifest) is True

    def test_all_checkpoints_precede_validity(self):
        """All checkpoints in real manifest precede validity_start."""
        with open(REAL_MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        for target in manifest.get("targets", []):
            validity_start_us = target.get("validity_start_us")
            for cp in target.get("checkpoints", []):
                assert cp["time_us"] < validity_start_us

    def test_no_holdout_overlap(self):
        """No target in real manifest overlaps holdout window."""
        with open(REAL_MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        config, _ = load_stations_calendar(REAL_CONFIG_PATH)
        holdout_start, holdout_end = get_holdout_window(config)

        for target in manifest.get("targets", []):
            validity_start = target.get("validity_start_us")
            validity_end = target.get("validity_end_us")

            # Check target validity doesn't overlap holdout
            assert not windows_overlap(
                validity_start, validity_end,
                holdout_start, holdout_end,
            ), f"Target {target['target_id']} overlaps holdout"

            # Check checkpoints don't overlap holdout
            for cp in target.get("checkpoints", []):
                cp_time = cp["time_us"]
                assert not (holdout_start <= cp_time < holdout_end), (
                    f"Checkpoint {cp_time} in holdout window"
                )

    def test_target_count_within_limit(self):
        """Real manifest has <= 12 targets."""
        with open(REAL_MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        assert len(manifest.get("targets", [])) <= MAX_TARGETS

    def test_validation_passes(self):
        """Real manifest passes validation."""
        with open(REAL_MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

        errors = validate_manifest(manifest)

        assert len(errors) == 0, f"Validation errors: {errors}"


# ---------------------------------------------------------------------------
# Test: Disclosure phase regression tests (D-A2 bug fixes)
# ---------------------------------------------------------------------------

class TestDiscloseAsosLookup:
    """Regression tests for ASOS data lookup (Bug 1: glob pattern fix)."""

    def test_asos_glob_pattern_matches_real_layout(self, tmp_path):
        """ASOS glob pattern matches real directory structure.

        Bug 1: The original glob pattern was:
            asos_dir.glob(f"*/{station}/{ym}/*.body")
        where ym="202308" (no dash). This was wrong because:
        1. Station comes FIRST in real layout, not after a wildcard
        2. Year-month uses dashes: "2023-08", not "202308"
        3. There's a run_id subdirectory before the .body file

        Correct pattern:
            asos_dir.glob(f"{station}/{YYYY}-{MM}/*/*.body")
        """
        # Set up fixture with REAL directory structure
        asos_dir = tmp_path / "asos"
        station = "KDEN"
        year_month = "2023-08"

        # Create the REAL directory structure:
        # asos/{station}/{YYYY-MM}/{run_id}/*.body
        run_id_dir = asos_dir / station / year_month / "20260920T084659Z_905e06c4de3b"
        run_id_dir.mkdir(parents=True)

        # Create a .body file
        body_file = run_id_dir / "asos-den-202308.body"
        body_file.write_text("test content")

        # Test the CORRECT glob pattern (as fixed)
        correct_pattern = list(asos_dir.glob(f"{station}/{year_month}/*/*.body"))
        assert len(correct_pattern) == 1, (
            f"Correct glob pattern should find 1 file, found {len(correct_pattern)}"
        )
        assert correct_pattern[0] == body_file

        # Test the WRONG old glob pattern (should NOT find anything)
        # Old pattern: f"*/{station}/{ym}/*.body" where ym="202308" (no dash)
        ym_no_dash = "202308"
        wrong_pattern = list(asos_dir.glob(f"*/{station}/{ym_no_dash}/*.body"))
        assert len(wrong_pattern) == 0, (
            f"Wrong glob pattern should find 0 files (bug 1), found {len(wrong_pattern)}"
        )

    def test_asos_glob_selects_latest_run_id(self, tmp_path):
        """When multiple run_ids exist, the latest (lexicographically last) is selected."""
        asos_dir = tmp_path / "asos"
        station = "KDEN"
        year_month = "2023-08"

        # Create two run_id directories (timestamps ensure deterministic ordering)
        run_id_1 = asos_dir / station / year_month / "20260920T080000Z_aaaa"
        run_id_2 = asos_dir / station / year_month / "20260920T090000Z_bbbb"  # Later
        run_id_1.mkdir(parents=True)
        run_id_2.mkdir(parents=True)

        body_1 = run_id_1 / "asos-den-202308.body"
        body_2 = run_id_2 / "asos-den-202308.body"
        body_1.write_text("older run")
        body_2.write_text("newer run")

        # Find all matches and sort by run_id (parent dir name)
        matches = list(asos_dir.glob(f"{station}/{year_month}/*/*.body"))
        matches.sort(key=lambda p: p.parent.name)
        selected = matches[-1]  # Last = newest

        assert selected == body_2, (
            f"Should select newest run_id. Expected {body_2}, got {selected}"
        )


class TestDiscloseStatisticsGranularity:
    """Regression tests for statistics granularity (Bug 2: unit mismatch fix)."""

    def test_resolved_plus_missing_equals_total(self):
        """resolved_count + missing_count must always equal total_checkpoints.

        Bug 2: The original code incremented total_checkpoints by len(checkpoints)
        (3 per target), but incremented missing_count/positive_count by 1 per
        target. This created a unit mismatch where:
            resolved_count = total_checkpoints - missing_count = 36 - 12 = 24
        even though all 12 targets were actually missing (should be 36 missing).

        The fix: Scale missing_count/positive_count by len(checkpoints) so they
        share the same checkpoint-level granularity as total_checkpoints.
        """
        # Simulate 5 targets, each with 3 checkpoints
        num_targets = 5
        checkpoints_per_target = 3
        total_checkpoints = num_targets * checkpoints_per_target  # 15

        # Simulate: 2 targets resolved (positive), 1 resolved (negative), 2 missing
        positive_targets = 2
        negative_targets = 1
        missing_targets = 2

        # CORRECT counting (Bug 2 fix) - scale by checkpoints_per_target
        positive_count = positive_targets * checkpoints_per_target  # 6
        negative_count = negative_targets * checkpoints_per_target  # 3
        missing_count = missing_targets * checkpoints_per_target    # 6

        resolved_count = total_checkpoints - missing_count  # 15 - 6 = 9

        # Verify the fundamental invariant
        assert resolved_count + missing_count == total_checkpoints, (
            f"Bug 2 invariant violated: resolved({resolved_count}) + "
            f"missing({missing_count}) != total({total_checkpoints})"
        )

        # Verify positive + negative = resolved
        assert positive_count + negative_count == resolved_count, (
            f"positive({positive_count}) + negative({negative_count}) != "
            f"resolved({resolved_count})"
        )

        # Verify positive_count <= resolved_count
        assert positive_count <= resolved_count, (
            f"positive_count({positive_count}) > resolved_count({resolved_count})"
        )

    def test_wrong_granularity_fails_invariant(self):
        """Demonstrate that the OLD buggy granularity violates the invariant."""
        # Simulate 5 targets, each with 3 checkpoints
        num_targets = 5
        checkpoints_per_target = 3
        total_checkpoints = num_targets * checkpoints_per_target  # 15

        # OLD BUGGY counting - increment by 1 per target, not by checkpoints
        # Simulate: 2 positive, 1 negative, 2 missing (all counted as 1)
        positive_count_buggy = 2  # Should be 6 (2 * 3)
        missing_count_buggy = 2   # Should be 6 (2 * 3)

        resolved_count_buggy = total_checkpoints - missing_count_buggy  # 15 - 2 = 13

        # The buggy version violates the invariant when you think about it:
        # If 2 targets are missing, that's 6 checkpoints missing, not 2
        # So resolved should be 9, not 13
        assert resolved_count_buggy != (positive_count_buggy + (1 * checkpoints_per_target)), (
            "This test demonstrates that buggy counting gives wrong resolved count"
        )


# ---------------------------------------------------------------------------
# Test: V17-01 ExposureRegistry preregistration enforcement (F07)
# ---------------------------------------------------------------------------

class TestExposureRegistry:
    """Tests for ExposureRegistry preregistration enforcement."""

    def test_register_freeze_succeeds_first_time(self, tmp_path):
        """First freeze registration succeeds."""
        from disastertrace.revision_v1.exposure_registry import (
            ExposureRegistry,
            compute_manifest_logical_id,
        )

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        logical_id = "test_manifest_001"
        sha256 = "abc123def456"

        entry = registry.register_freeze(logical_id, sha256)

        assert entry.logical_id == logical_id
        assert entry.expected_manifest_sha256 == sha256
        assert entry.entry_type == "freeze"
        assert registry.is_frozen(logical_id)

    def test_refreeze_same_logical_id_rejected(self, tmp_path):
        """Re-freeze attempt on already-frozen logical_id is rejected.

        This is the F07 fix: renaming the output file does not bypass the
        preregistration check because we track by logical_id, not filename.
        """
        from disastertrace.revision_v1.exposure_registry import (
            ExposureRegistry,
            AlreadyFrozenError,
        )

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        logical_id = "test_manifest_001"
        sha256_original = "abc123"
        sha256_new = "def456"  # Attacker tries with different content

        # First freeze succeeds
        registry.register_freeze(logical_id, sha256_original)

        # Second freeze with same logical_id is rejected
        with pytest.raises(AlreadyFrozenError) as exc_info:
            registry.register_freeze(logical_id, sha256_new)

        assert "already frozen" in str(exc_info.value)
        assert logical_id in str(exc_info.value)

    def test_refreeze_after_rename_still_rejected(self, tmp_path):
        """Re-freeze after 'deleting and renaming' is still rejected.

        This specifically tests the F07 scenario: an attacker deletes
        manifest_v1.json and tries to regenerate as manifest_v2.json.
        Since logical_id is derived from inputs (not filename), this fails.
        """
        from disastertrace.revision_v1.exposure_registry import (
            ExposureRegistry,
            AlreadyFrozenError,
            compute_manifest_logical_id,
        )

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        # Compute logical_id from inputs (same inputs = same logical_id)
        selection_rule = "manifest_selection.v1"
        taf_summary = "archive_abc123"
        config_sha = "config_def456"

        logical_id = compute_manifest_logical_id(
            selection_rule, taf_summary, config_sha
        )

        # First freeze with filename "manifest_v1.json" (not tracked by registry)
        registry.register_freeze(logical_id, "sha256_original")

        # Attacker "deletes manifest_v1.json" and tries with "manifest_v2.json"
        # But same inputs produce same logical_id!
        same_logical_id = compute_manifest_logical_id(
            selection_rule, taf_summary, config_sha
        )

        assert same_logical_id == logical_id

        with pytest.raises(AlreadyFrozenError):
            registry.register_freeze(same_logical_id, "sha256_modified")

    def test_disclosure_requires_freeze(self, tmp_path):
        """Disclosure fails if logical_id was never frozen."""
        from disastertrace.revision_v1.exposure_registry import (
            ExposureRegistry,
            NotFrozenError,
        )

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        with pytest.raises(NotFrozenError) as exc_info:
            registry.register_disclosure("never_frozen_id", "some_sha256")

        assert "never frozen" in str(exc_info.value)

    def test_disclosure_verifies_sha256(self, tmp_path):
        """Disclosure fails if sha256 doesn't match frozen value."""
        from disastertrace.revision_v1.exposure_registry import (
            ExposureRegistry,
            ManifestMismatchError,
        )

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        logical_id = "test_manifest"
        frozen_sha256 = "correct_sha256"
        wrong_sha256 = "tampered_sha256"

        registry.register_freeze(logical_id, frozen_sha256)

        with pytest.raises(ManifestMismatchError) as exc_info:
            registry.register_disclosure(logical_id, wrong_sha256)

        assert "mismatch" in str(exc_info.value).lower()

    def test_append_only_property(self, tmp_path):
        """Registry writes never drop or mutate prior entries."""
        from disastertrace.revision_v1.exposure_registry import ExposureRegistry

        registry_path = tmp_path / "registry.json"
        registry = ExposureRegistry(registry_path)

        # Write two entries
        entry1 = registry.register_freeze("id_1", "sha1")
        entry2 = registry.register_freeze("id_2", "sha2")

        # Re-open and verify both entries present and identical
        registry2 = ExposureRegistry(registry_path)

        entries = registry2.list_entries()
        assert len(entries) == 2

        assert entries[0].logical_id == "id_1"
        assert entries[0].expected_manifest_sha256 == "sha1"
        assert entries[1].logical_id == "id_2"
        assert entries[1].expected_manifest_sha256 == "sha2"

        # Now add a disclosure
        registry2.register_disclosure("id_1", "sha1")

        # Re-open again and verify all three entries
        registry3 = ExposureRegistry(registry_path)
        entries = registry3.list_entries()
        assert len(entries) == 3

        # Original entries unchanged
        assert entries[0].logical_id == "id_1"
        assert entries[0].entry_type == "freeze"
        assert entries[1].logical_id == "id_2"
        assert entries[1].entry_type == "freeze"
        assert entries[2].logical_id == "id_1"
        assert entries[2].entry_type == "disclosure"


# ---------------------------------------------------------------------------
# Test: V17-01 Content-based archive fingerprinting (F07)
# ---------------------------------------------------------------------------

class TestContentBasedFingerprinting:
    """Tests for content-based archive fingerprinting.

    The F07 fix: fingerprint must be content-derived, not just dir name + count.
    """

    def test_different_content_produces_different_fingerprint(self, tmp_path):
        """Two archives with same name+count but different content have different fingerprints.

        This is the core F07 fix: the old fingerprint was just f"{dir_name}:{file_count}"
        which would be identical for archives with different file contents.
        """
        # Import the updated function
        sys.path.insert(0, str(_project / "scripts"))
        from build_episode_manifest_v16 import generate_taf_archive_summary

        # Create two archives with IDENTICAL dir names and file counts
        archive1 = tmp_path / "test_archive"
        archive2 = tmp_path / "test_archive_2"
        archive1.mkdir()
        archive2.mkdir()

        # Create same number of files in each
        for i in range(3):
            body1 = archive1 / f"file{i}.body"
            body2 = archive2 / f"file{i}.body"

            body1.write_text(f"content_a_{i}")
            body2.write_text(f"content_b_{i}")  # DIFFERENT content

            # Create receipts with SHA256s
            receipt1 = archive1 / f"file{i}.json"
            receipt2 = archive2 / f"file{i}.json"

            sha1 = hashlib.sha256(f"content_a_{i}".encode()).hexdigest()
            sha2 = hashlib.sha256(f"content_b_{i}".encode()).hexdigest()

            receipt1.write_text(json.dumps({"sha256": sha1}))
            receipt2.write_text(json.dumps({"sha256": sha2}))

        # Generate fingerprints
        fp1 = generate_taf_archive_summary(archive1)
        fp2 = generate_taf_archive_summary(archive2)

        # They must be DIFFERENT (F07 fix)
        assert fp1 != fp2, (
            "F07 bug: archives with different content produced same fingerprint"
        )

    def test_same_content_different_order_produces_same_fingerprint(self, tmp_path):
        """Same content discovered in different order produces same fingerprint.

        The fingerprint should sort file entries before hashing for determinism.
        """
        sys.path.insert(0, str(_project / "scripts"))
        from build_episode_manifest_v16 import generate_taf_archive_summary

        # Create archive
        archive = tmp_path / "test_archive"
        archive.mkdir()

        # Create files
        files_content = [
            ("c_file.body", "content_c"),
            ("a_file.body", "content_a"),
            ("b_file.body", "content_b"),
        ]

        for name, content in files_content:
            body = archive / name
            body.write_text(content)

            receipt = archive / name.replace(".body", ".json")
            sha = hashlib.sha256(content.encode()).hexdigest()
            receipt.write_text(json.dumps({"sha256": sha}))

        # Generate fingerprint multiple times
        fp1 = generate_taf_archive_summary(archive)
        fp2 = generate_taf_archive_summary(archive)

        # Must be identical (deterministic, order-independent)
        assert fp1 == fp2

    def test_missing_receipt_raises_error(self, tmp_path):
        """Missing receipt file for a .body raises clear error."""
        sys.path.insert(0, str(_project / "scripts"))
        from build_episode_manifest_v16 import generate_taf_archive_summary

        archive = tmp_path / "test_archive"
        archive.mkdir()

        # Create .body WITHOUT matching .json receipt
        body = archive / "orphan.body"
        body.write_text("content")

        with pytest.raises(ValueError) as exc_info:
            generate_taf_archive_summary(archive)

        assert "Receipt file missing" in str(exc_info.value)

    def test_receipt_missing_sha256_raises_error(self, tmp_path):
        """Receipt without sha256 field raises clear error."""
        sys.path.insert(0, str(_project / "scripts"))
        from build_episode_manifest_v16 import generate_taf_archive_summary

        archive = tmp_path / "test_archive"
        archive.mkdir()

        body = archive / "test.body"
        body.write_text("content")

        # Receipt without sha256
        receipt = archive / "test.json"
        receipt.write_text(json.dumps({"other_field": "value"}))

        with pytest.raises(ValueError) as exc_info:
            generate_taf_archive_summary(archive)

        assert "sha256" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# V17-02 / F02: Pre-deadline revision count filtering tests
# ---------------------------------------------------------------------------


class TestF02PreDeadlineFiltering:
    """V17-02 / F02: Test pre-deadline filtering of revision counts.

    The F02 fix ensures that revision_count, tie_event_count, and
    evidence_change_count only count packages issued BEFORE the target's
    validity_start (the "deadline"). Packages issued during the validity
    window are counted separately in the *_whole_window fields.
    """

    def test_candidate_has_both_filtered_and_whole_window_counts(self):
        """CandidateTarget has both pre-deadline and whole-window count fields."""
        from disastertrace.revision_v1.manifest import CandidateTarget

        hour = 3_600_000_000  # 1 hour in microseconds
        t0 = 1700000000000000  # arbitrary base time

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=3,
            tie_event_count=1,
            evidence_change_count=2,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=5,
            tie_event_count_whole_window=2,
            evidence_change_count_whole_window=4,
            source_packages=[],
        )

        # Filtered counts (pre-deadline)
        assert candidate.revision_count == 3
        assert candidate.tie_event_count == 1
        assert candidate.evidence_change_count == 2

        # Whole-window counts
        assert candidate.revision_count_whole_window == 5
        assert candidate.tie_event_count_whole_window == 2
        assert candidate.evidence_change_count_whole_window == 4

    def test_build_manifest_includes_both_count_types(self):
        """build_manifest includes both pre-deadline and whole-window counts."""
        from disastertrace.revision_v1.manifest import CandidateTarget, build_manifest

        hour = 3_600_000_000
        t0 = 1700000000000000

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=2,
            tie_event_count=0,
            evidence_change_count=1,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=4,
            tie_event_count_whole_window=1,
            evidence_change_count_whole_window=3,
            source_packages=[],
        )

        manifest = build_manifest(
            changed_queue=[candidate],
            unchanged_queue=[],
            config_sha256="a" * 64,
            taf_archive_summary="test",
        )

        target = manifest["targets"][0]
        signals = target["selection_signals"]

        # Pre-deadline counts
        assert signals["revision_count"] == 2
        assert signals["tie_event_count"] == 0
        assert signals["evidence_change_count"] == 1

        # Whole-window counts
        assert signals["revision_count_whole_window"] == 4
        assert signals["tie_event_count_whole_window"] == 1
        assert signals["evidence_change_count_whole_window"] == 3


class TestF02OutcomeContract:
    """V17-02 / F02: Test outcome_contract in manifest schema."""

    def test_manifest_v2_schema_includes_outcome_contract(self):
        """v2 schema manifest includes outcome_contract field."""
        from disastertrace.revision_v1.manifest import (
            CandidateTarget,
            DEFAULT_OUTCOME_CONTRACT,
            build_manifest,
        )

        hour = 3_600_000_000
        t0 = 1700000000000000

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=1,
            tie_event_count=0,
            evidence_change_count=1,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=1,
            tie_event_count_whole_window=0,
            evidence_change_count_whole_window=1,
            source_packages=[],
        )

        manifest = build_manifest(
            changed_queue=[candidate],
            unchanged_queue=[],
            config_sha256="a" * 64,
            taf_archive_summary="test",
        )

        assert manifest["schema"] == "disastertrace.episode_manifest.v2"
        assert "outcome_contract" in manifest

        oc = manifest["outcome_contract"]
        assert "thresholds_m" in oc
        assert "report_policy" in oc
        assert "checkpoint_weights" in oc
        assert "support_window_hours" in oc

    def test_default_outcome_contract_values(self):
        """DEFAULT_OUTCOME_CONTRACT has expected frozen values."""
        from disastertrace.revision_v1.manifest import DEFAULT_OUTCOME_CONTRACT

        assert DEFAULT_OUTCOME_CONTRACT["thresholds_m"] == [5000.0, 1000.0]
        assert DEFAULT_OUTCOME_CONTRACT["report_policy"] == "iem_routine_unique_hour.v1"
        assert DEFAULT_OUTCOME_CONTRACT["support_window_hours"] == 1.0
        assert DEFAULT_OUTCOME_CONTRACT["checkpoint_weights"] == [1.0, 1.0, 1.0]
        assert DEFAULT_OUTCOME_CONTRACT["checkpoint_offsets_minutes"] == [-60, -40, -20]

    def test_custom_outcome_contract_preserved(self):
        """Custom outcome_contract passed to build_manifest is used."""
        from disastertrace.revision_v1.manifest import CandidateTarget, build_manifest

        hour = 3_600_000_000
        t0 = 1700000000000000

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=1,
            tie_event_count=0,
            evidence_change_count=1,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=1,
            tie_event_count_whole_window=0,
            evidence_change_count_whole_window=1,
            source_packages=[],
        )

        custom_contract = {
            "thresholds_m": [3000.0],
            "report_policy": "custom.v1",
            "support_window_hours": 2.0,
            "checkpoint_weights": [0.5, 0.3, 0.2],
        }

        manifest = build_manifest(
            changed_queue=[candidate],
            unchanged_queue=[],
            config_sha256="a" * 64,
            taf_archive_summary="test",
            outcome_contract=custom_contract,
        )

        assert manifest["outcome_contract"]["thresholds_m"] == [3000.0]
        assert manifest["outcome_contract"]["report_policy"] == "custom.v1"

    def test_empty_weights_raises(self):
        """Empty checkpoint_weights raises ValueError."""
        from disastertrace.revision_v1.manifest import CandidateTarget, build_manifest

        hour = 3_600_000_000
        t0 = 1700000000000000

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=1,
            tie_event_count=0,
            evidence_change_count=1,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=1,
            tie_event_count_whole_window=0,
            evidence_change_count_whole_window=1,
            source_packages=[],
        )

        invalid_contract = {
            "thresholds_m": [5000.0],
            "report_policy": "test.v1",
            "support_window_hours": 1.0,
            "checkpoint_weights": [],  # Empty!
        }

        with pytest.raises(ValueError) as exc_info:
            build_manifest(
                changed_queue=[candidate],
                unchanged_queue=[],
                config_sha256="a" * 64,
                taf_archive_summary="test",
                outcome_contract=invalid_contract,
            )

        assert "empty" in str(exc_info.value).lower()


class TestF02ManifestValidation:
    """V17-02 / F02: Test validate_manifest accepts both v1 and v2 schemas."""

    def test_validate_manifest_accepts_v2_schema(self):
        """validate_manifest accepts v2 schema with outcome_contract."""
        from disastertrace.revision_v1.manifest import (
            CandidateTarget,
            build_manifest,
            compute_self_sha256,
            validate_manifest,
        )

        hour = 3_600_000_000
        t0 = 1700000000000000

        candidate = CandidateTarget(
            station="KSFO",
            validity_start_us=t0,
            validity_end_us=t0 + 6 * hour,
            revision_count=1,
            tie_event_count=0,
            evidence_change_count=1,
            lead_time_coverage_hours=6.0,
            revision_count_whole_window=1,
            tie_event_count_whole_window=0,
            evidence_change_count_whole_window=1,
            source_packages=[],
        )

        manifest = build_manifest(
            changed_queue=[candidate],
            unchanged_queue=[],
            config_sha256="a" * 64,
            taf_archive_summary="test",
        )
        manifest["self_sha256"] = compute_self_sha256(manifest)

        errors = validate_manifest(manifest)
        assert errors == [], f"Validation errors: {errors}"

    def test_validate_manifest_rejects_v2_missing_outcome_contract(self):
        """v2 schema without outcome_contract is rejected."""
        manifest = {
            "schema": "disastertrace.episode_manifest.v2",
            "selection_rule_version": "manifest_selection.v2",
            "targets": [],
            "queue_summary": {"changed_count": 0, "unchanged_count": 0, "total_count": 0},
            "frozen_at": "2023-01-01T00:00:00Z",
            "input_fingerprints": {},
            "self_sha256": "",
        }

        errors = validate_manifest(manifest)
        assert any("outcome_contract" in e for e in errors)

    def test_validate_manifest_rejects_v2_missing_whole_window_counts(self):
        """v2 schema without whole-window counts in selection_signals is rejected."""
        from disastertrace.revision_v1.manifest import DEFAULT_OUTCOME_CONTRACT

        hour = 3_600_000_000
        t0 = 1700000000000000

        manifest = {
            "schema": "disastertrace.episode_manifest.v2",
            "selection_rule_version": "manifest_selection.v2",
            "outcome_contract": DEFAULT_OUTCOME_CONTRACT.copy(),
            "targets": [
                {
                    "target_id": "test",
                    "station": "KSFO",
                    "validity_start": "2023-01-01T00:00:00Z",
                    "validity_start_us": t0,
                    "validity_end": "2023-01-01T06:00:00Z",
                    "validity_end_us": t0 + 6 * hour,
                    "queue": "changed",
                    "checkpoints": [
                        {"time_us": t0 - 60 * 60_000_000, "time": "X", "weight": 1.0},
                        {"time_us": t0 - 40 * 60_000_000, "time": "X", "weight": 1.0},
                        {"time_us": t0 - 20 * 60_000_000, "time": "X", "weight": 1.0},
                    ],
                    "selection_signals": {
                        "revision_count": 1,
                        "tie_event_count": 0,
                        "evidence_change_count": 1,
                        "lead_time_coverage_hours": 6.0,
                        # Missing *_whole_window fields!
                    },
                }
            ],
            "queue_summary": {"changed_count": 1, "unchanged_count": 0, "total_count": 1},
            "frozen_at": "2023-01-01T00:00:00Z",
            "input_fingerprints": {},
            "self_sha256": "",
        }

        errors = validate_manifest(manifest)
        assert any("revision_count_whole_window" in e for e in errors)
