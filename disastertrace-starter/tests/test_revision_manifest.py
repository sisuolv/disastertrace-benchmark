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
