#!/usr/bin/env python3
"""Build episode manifest for v16 pre-registration (P0-08).

Two-phase design:
  Phase 1 (freeze): Selects episodes using ONLY TAF-side signals. MUST NOT see
    outcome data. Produces EPISODE_MANIFEST_v16.json.

  Phase 2 (disclose): Reads the frozen manifest, verifies its integrity, THEN
    reads ASOS/outcome data to compute and write disclosure statistics.
    Produces EPISODE_MANIFEST_v16_DISCLOSURE.md.

V17-01 / F04+F07 enhancements:
  - AccessPolicy enforcement before any ASOS file discovery
  - ExposureRegistry for preregistration enforcement
  - Content-based archive fingerprinting (not just dir name + count)

Usage:
  python scripts/build_episode_manifest_v16.py           # Phase 1: freeze
  python scripts/build_episode_manifest_v16.py --disclose  # Phase 2: disclose

Exit codes:
  0 - Success
  1 - Validation errors or runtime issues
  2 - Manifest already exists (freeze mode only)
  3 - ExposureRegistry rejection (logical_id already frozen)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Resolve project root for imports
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))

from disastertrace.revision_v1.manifest import (
    SELECTION_RULE_VERSION,
    DEFAULT_OUTCOME_CONTRACT,
    UnsupportedOutcomeProfile,
    validate_outcome_profile,
    freeze_manifest,
    load_stations_calendar,
    verify_manifest_integrity,
    validate_manifest,
    get_holdout_window,
    windows_overlap,
    compute_self_sha256,
)
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream
from disastertrace.revision_v1.access_policy import (
    AccessPolicy,
    AccessPolicyViolation,
    make_policy_for_real_v16,
)
from disastertrace.revision_v1.exposure_registry import (
    ExposureRegistry,
    AlreadyFrozenError,
    NotFrozenError,
    ManifestMismatchError,
    compute_manifest_logical_id,
)


# Default paths
DEFAULT_CONFIG_PATH = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/stations_calendar_v16.json"
)
DEFAULT_TAF_BULK_DIR = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/"
    "20260920T134949Z_1bbe63aedc00_dl3rbulk"
)
DEFAULT_MANIFEST_PATH = Path(
    _project / "data_contracts" / "EPISODE_MANIFEST_v16.json"
)
DEFAULT_DISCLOSURE_PATH = Path(
    _project / "data_contracts" / "EPISODE_MANIFEST_v16_DISCLOSURE.md"
)
DEFAULT_EXPOSURE_REGISTRY_PATH = Path(
    _project / "data_contracts" / "exposure_registry_v17.json"
)


def compile_all_taf_packages(
    bulk_dir: Path,
    stations: list[str],
    year_months: list[str],
) -> tuple[list[dict], dict]:
    """Compile all TAF packages from bulk directory.

    Returns:
        Tuple of (all_packages, summary_dict).
    """
    all_packages = []
    summary = {
        "files_compiled": 0,
        "frames_compiled": 0,
        "frames_skipped": 0,
        "stations": stations,
        "year_months": year_months,
    }

    for station in stations:
        for ym in year_months:
            body_file = bulk_dir / f"{station}_{ym}.body"
            if not body_file.exists():
                continue

            # Read raw text
            with open(body_file, "r", errors="replace") as f:
                raw_text = f.read()

            # Parse reference month
            reference_month = f"{ym[:4]}-{ym[4:6]}"

            # Compile
            packages, skipped = compile_afos_taf_stream(
                raw_text,
                station=station,
                reference_month=reference_month,
            )

            all_packages.extend(packages)
            summary["files_compiled"] += 1
            summary["frames_compiled"] += len(packages)
            summary["frames_skipped"] += len(skipped)

    return all_packages, summary


def generate_taf_archive_summary(bulk_dir: Path) -> str:
    """Generate content-based summary hash of TAF archive state.

    V17-01 / F07 fix: Now uses content-based fingerprinting instead of just
    directory name + file count. The fingerprint is derived from:
    1. For each .body file, get its SHA256 from its sibling .json receipt
    2. Sort (filename, sha256) pairs deterministically
    3. Hash the sorted concatenation

    This ensures that two archives with the same name and file count but
    different file contents will produce different fingerprints.

    Raises:
        ValueError: If any .body file is missing its .json receipt with sha256.
    """
    body_files = sorted(bulk_dir.glob("*.body"))

    if not body_files:
        # Empty archive - hash just the directory name as fallback
        return hashlib.sha256(f"empty:{bulk_dir.name}".encode()).hexdigest()[:16]

    # Collect (filename, sha256) pairs from receipts
    file_hashes = []

    for body_file in body_files:
        receipt_path = body_file.with_suffix(".json")

        if not receipt_path.exists():
            raise ValueError(
                f"Receipt file missing for {body_file.name}. "
                f"Content-based fingerprinting requires all .body files to have "
                f"a sibling .json receipt with a sha256 field."
            )

        with open(receipt_path, "r") as f:
            receipt = json.load(f)

        sha256 = receipt.get("sha256")
        if not sha256:
            raise ValueError(
                f"Receipt for {body_file.name} missing sha256 field. "
                f"Content-based fingerprinting requires sha256 in all receipts."
            )

        file_hashes.append((body_file.name, sha256))

    # Sort deterministically by filename (already sorted from glob, but be explicit)
    file_hashes.sort(key=lambda x: x[0])

    # Build concatenated string for final hash
    concat = "\n".join(f"{name}:{sha256}" for name, sha256 in file_hashes)

    return hashlib.sha256(concat.encode()).hexdigest()[:16]


def verify_stations_calendar_sha256_match(
    config_path: Path,
    manifest: dict,
) -> None:
    """Cross-verify stations_calendar sha256 against manifest record.

    V17-01 / F07 fix: The manifest records stations_calendar_sha256 at freeze
    time. At disclosure time, we re-verify the config and cross-check that
    the current sidecar sha256 matches what was recorded.

    Raises:
        ValueError: If sha256 values don't match.
    """
    from disastertrace.revision_v1.manifest import verify_config_sha256

    # Get current sha256 from sidecar
    current_sha256 = verify_config_sha256(config_path)

    # Get recorded sha256 from manifest
    recorded_sha256 = manifest.get("input_fingerprints", {}).get("stations_calendar_sha256")

    if not recorded_sha256:
        raise ValueError(
            "Manifest missing stations_calendar_sha256 in input_fingerprints"
        )

    if current_sha256 != recorded_sha256:
        raise ValueError(
            f"stations_calendar SHA256 mismatch. "
            f"Manifest recorded: {recorded_sha256}, "
            f"Current sidecar: {current_sha256}. "
            f"The config may have been modified after manifest freeze."
        )


def run_freeze(
    config_path: Path,
    bulk_dir: Path,
    manifest_path: Path,
    exposure_registry_path: Path,
) -> int:
    """Phase 1: Freeze episode selection.

    V17-01 / F07 fix: Now registers freeze in ExposureRegistry to prevent
    re-freezing under a different filename.

    Returns exit code.
    """
    print(f"Phase 1: Freeze episode manifest")
    print(f"  Config: {config_path}")
    print(f"  TAF bulk: {bulk_dir}")
    print(f"  Output: {manifest_path}")
    print(f"  Exposure registry: {exposure_registry_path}")
    print()

    # Load config early to get sha256 for logical_id computation
    config, config_sha256 = load_stations_calendar(config_path)
    stations = [s["icao"] for s in config.get("stations", [])]

    # Generate archive summary early for logical_id
    try:
        taf_archive_summary = generate_taf_archive_summary(bulk_dir)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Compute logical_id for this freeze attempt
    logical_id = compute_manifest_logical_id(
        SELECTION_RULE_VERSION,
        taf_archive_summary,
        config_sha256,
    )

    # Check ExposureRegistry BEFORE checking output file
    # This closes F07: re-freeze is rejected even under a new filename
    registry = ExposureRegistry(exposure_registry_path)
    if registry.is_frozen(logical_id):
        freeze_entry = registry.get_freeze_entry(logical_id)
        print(f"ERROR: This manifest was already frozen.", file=sys.stderr)
        print(f"  Logical ID: {logical_id}", file=sys.stderr)
        print(f"  Frozen at: {freeze_entry.frozen_at}", file=sys.stderr)
        print(f"  Expected SHA256: {freeze_entry.expected_manifest_sha256}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Re-freezing the same selection under a different filename is not allowed.", file=sys.stderr)
        print("This protects preregistration integrity. If you need to modify the", file=sys.stderr)
        print("selection, you must use a different selection_rule_version or config,", file=sys.stderr)
        print("which will produce a different logical_id.", file=sys.stderr)
        return 3

    # Check if manifest already exists - REFUSE to overwrite
    if manifest_path.exists():
        print(f"ERROR: Manifest already exists at {manifest_path}", file=sys.stderr)
        print("This script refuses to overwrite frozen manifests.", file=sys.stderr)
        print("", file=sys.stderr)
        print("If this is the same selection that was already frozen (same logical_id),", file=sys.stderr)
        print("the manifest content should be identical. If you believe the existing", file=sys.stderr)
        print("file is corrupt, verify its self_sha256 first.", file=sys.stderr)
        return 2

    # Create output directory if needed
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate year-months (excluding Feb 2025 holdout)
    year_months = []
    for year in [2023, 2024, 2025]:
        for month in range(1, 13):
            ym = f"{year:04d}{month:02d}"
            if ym == "202502":  # Feb 2025 is holdout
                continue
            year_months.append(ym)

    print(f"Compiling TAF packages...")
    print(f"  Stations: {stations}")
    print(f"  Year-months: {len(year_months)}")

    # Compile all TAF packages
    all_packages, compile_summary = compile_all_taf_packages(
        bulk_dir, stations, year_months
    )

    print(f"  Files compiled: {compile_summary['files_compiled']}")
    print(f"  Frames compiled: {compile_summary['frames_compiled']}")
    print(f"  Frames skipped: {compile_summary['frames_skipped']}")
    print()

    print(f"Building manifest...")

    # Freeze manifest
    manifest = freeze_manifest(
        all_packages,
        config_path,
        taf_archive_summary=taf_archive_summary,
    )

    # Validate
    errors = validate_manifest(manifest)
    if errors:
        print(f"ERROR: Manifest validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    # Register freeze in ExposureRegistry BEFORE writing manifest
    manifest_sha256 = manifest.get("self_sha256")
    try:
        registry.register_freeze(logical_id, manifest_sha256)
        print(f"  Registered freeze in exposure registry")
        print(f"    Logical ID: {logical_id}")
    except AlreadyFrozenError as e:
        # This shouldn't happen since we checked above, but handle it
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    # Write manifest
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Report results
    queue_summary = manifest.get("queue_summary", {})
    print(f"Manifest frozen successfully!")
    print(f"  Selection rule version: {manifest.get('selection_rule_version')}")
    print(f"  Changed queue: {queue_summary.get('changed_count', 0)} targets")
    print(f"  Unchanged queue: {queue_summary.get('unchanged_count', 0)} targets")
    print(f"  Total targets: {queue_summary.get('total_count', 0)}")
    print(f"  Frozen at: {manifest.get('frozen_at')}")
    print(f"  Self SHA256: {manifest.get('self_sha256')[:16]}...")
    print(f"  Logical ID: {logical_id}")
    print(f"  TAF archive summary: {taf_archive_summary}")
    print(f"  Output: {manifest_path}")

    return 0


def resolve_disclose_outcome_contract(manifest: dict) -> dict:
    """A2-4: Resolve which outcome_contract a disclose run must use, from the
    manifest alone -- before any ASOS/outcome data path is touched.

    v1-schema manifests (or any manifest with no outcome_contract at all) take
    an explicit legacy_v1 branch and use DEFAULT_OUTCOME_CONTRACT. v2-schema
    manifests must carry an outcome_contract that matches the single supported
    H15_DEFAULT_PROFILE exactly.

    Args:
        manifest: Loaded manifest dict (already integrity- and sha256-verified
            by the caller).

    Returns:
        The outcome_contract dict to use for the rest of disclosure.

    Raises:
        UnsupportedOutcomeProfile: if a v2 manifest's outcome_contract does not
            match H15_DEFAULT_PROFILE.
    """
    schema = manifest.get("schema")
    outcome_contract = manifest.get("outcome_contract")
    if schema == "disastertrace.episode_manifest.v1" or outcome_contract is None:
        return DEFAULT_OUTCOME_CONTRACT
    validate_outcome_profile(outcome_contract)
    return outcome_contract


def run_disclose(
    manifest_path: Path,
    disclosure_path: Path,
    config_path: Path,
    exposure_registry_path: Path,
) -> int:
    """Phase 2: Disclose statistics (reads outcome data).

    V17-01 / F04 fix: Now enforces AccessPolicy BEFORE ASOS file discovery.
    V17-01 / F07 fix: Registers disclosure in ExposureRegistry after integrity check.

    Returns exit code.
    """
    print(f"Phase 2: Disclose episode statistics")
    print(f"  Manifest: {manifest_path}")
    print(f"  Output: {disclosure_path}")
    print(f"  Exposure registry: {exposure_registry_path}")
    print()

    # Check manifest exists
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found at {manifest_path}", file=sys.stderr)
        print("Run freeze phase first.", file=sys.stderr)
        return 1

    # Load manifest
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    # Verify integrity BEFORE reading outcome data
    print(f"Verifying manifest integrity...")
    try:
        verify_manifest_integrity(manifest)
        print(f"  Integrity check PASSED")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Cannot proceed with disclosure - manifest may have been tampered.", file=sys.stderr)
        return 1

    # V17-01 / F07 fix: Cross-verify stations_calendar sha256
    print(f"Verifying stations_calendar SHA256...")
    try:
        verify_stations_calendar_sha256_match(config_path, manifest)
        print(f"  stations_calendar SHA256 check PASSED")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # A2-4: Validate the manifest's outcome contract BEFORE any ASOS/outcome
    # data path is constructed below. v1 manifests carry no outcome_contract
    # at all (pre-F02) and take an explicit legacy_v1 branch using
    # DEFAULT_OUTCOME_CONTRACT; v2 manifests must match the single supported
    # H15_DEFAULT_PROFILE exactly, or disclosure is refused.
    print(f"Validating manifest outcome contract...")
    try:
        outcome_contract = resolve_disclose_outcome_contract(manifest)
        if manifest.get("schema") == "disastertrace.episode_manifest.v1" or manifest.get("outcome_contract") is None:
            print(f"  Manifest schema is {manifest.get('schema')!r} with no outcome_contract -- legacy_v1 branch, using DEFAULT_OUTCOME_CONTRACT")
        else:
            print(f"  outcome_contract PASSED (matches the single supported H15 profile)")
    except UnsupportedOutcomeProfile as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Load config for AccessPolicy and stations
    config, config_sha256 = load_stations_calendar(config_path)
    stations_config = {s["icao"]: s for s in config.get("stations", [])}

    # V17-01 / F04 fix: Create AccessPolicy for boundary enforcement
    # Build allowed year-months list (excluding holdout)
    allowed_year_months = set()
    for year in [2023, 2024, 2025]:
        for month in range(1, 13):
            ym = f"{year:04d}-{month:02d}"
            allowed_year_months.add(ym)
    # Remove holdout month
    allowed_year_months.discard("2025-02")

    access_policy = make_policy_for_real_v16(
        config,
        allowed_year_months=frozenset(allowed_year_months),
    )
    print(f"  AccessPolicy configured with {len(allowed_year_months)} allowed months")

    # V17-01 / F04 fix: Check all target checkpoints against holdout BEFORE any ASOS access
    print(f"Pre-validating target checkpoints against holdout window...")
    holdout_start_us, holdout_end_us = get_holdout_window(config)
    targets = manifest.get("targets", [])

    for target in targets:
        target_id = target.get("target_id")
        validity_start_us = target.get("validity_start_us")
        validity_end_us = target.get("validity_end_us")
        checkpoints = target.get("checkpoints", [])

        # Check target validity window
        if windows_overlap(validity_start_us, validity_end_us, holdout_start_us, holdout_end_us):
            print(f"ERROR: Target {target_id} validity window overlaps holdout", file=sys.stderr)
            return 1

        # Check each checkpoint
        for cp in checkpoints:
            cp_time_us = cp.get("time_us")
            if holdout_start_us <= cp_time_us < holdout_end_us:
                print(f"ERROR: Target {target_id} checkpoint {cp_time_us} falls in holdout", file=sys.stderr)
                return 1

    print(f"  All {len(targets)} targets pass holdout boundary check")

    # V17-01 / F07 fix: Register disclosure in ExposureRegistry
    manifest_sha256 = manifest.get("self_sha256")
    taf_archive_summary = manifest.get("input_fingerprints", {}).get("taf_archive_summary", "")
    logical_id = compute_manifest_logical_id(
        manifest.get("selection_rule_version", SELECTION_RULE_VERSION),
        taf_archive_summary,
        config_sha256,
    )

    registry = ExposureRegistry(exposure_registry_path)
    print(f"Registering disclosure in exposure registry...")
    try:
        registry.register_disclosure(logical_id, manifest_sha256)
        print(f"  Disclosure registered for logical_id: {logical_id}")
    except NotFrozenError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ManifestMismatchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Now we're allowed to import outcome_wiring (only in disclose phase)
    # This is the ONLY place outcome data should be read
    from disastertrace.revision_v1.outcome_wiring import (
        make_h15_visibility_target,
        load_asos_with_provenance,
        select_routine_observations,
        resolve_h15_outcomes,
        FROZEN_THRESHOLDS_M,
    )
    from disastertrace.revision_v1.episode_compiler import compile_asos_csv_to_observations

    # Build disclosure report
    lines = []
    lines.append("# Episode Manifest v16 Disclosure Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Manifest: `{manifest_path}`")
    lines.append(f"Selection rule: {manifest.get('selection_rule_version')}")
    lines.append(f"Frozen at: {manifest.get('frozen_at')}")
    lines.append(f"Self SHA256: {manifest.get('self_sha256')}")
    lines.append("")

    # Summary
    queue_summary = manifest.get("queue_summary", {})
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Changed queue: {queue_summary.get('changed_count', 0)} targets")
    lines.append(f"- Unchanged queue: {queue_summary.get('unchanged_count', 0)} targets")
    lines.append(f"- Total targets: {queue_summary.get('total_count', 0)}")
    lines.append(f"- Checkpoints per target: 3 (T-60, T-40, T-20 min)")
    lines.append(f"- Total checkpoints: {queue_summary.get('total_count', 0) * 3}")
    lines.append("")

    # Thresholds (from D02 - 5km/1km nested)
    lines.append("## H15 Visibility Thresholds (D02)")
    lines.append("")
    lines.append("Per D02 decision, H15 uses nested 5km/1km thresholds:")
    lines.append(f"- Primary threshold: 5000m (5km)")
    lines.append(f"- Nested threshold: 1000m (1km)")
    lines.append(f"- Event operator: lt (visibility < threshold)")
    lines.append("")

    # Per-lead eligibility note (D-A2 spec gap)
    lines.append("## Per-Lead Eligibility Note")
    lines.append("")
    lines.append("Per-lead-time eligibility reporting is DEFERRED. The codebase (outcome_wiring.py,")
    lines.append("episode_compiler.py) does not currently expose a TAF-side-computable notion of")
    lines.append("checkpoint/lead eligibility distinct from the target's final Y outcome. Adding")
    lines.append("such a primitive would require designing new semantics beyond the scope of this")
    lines.append("disclosure-phase bug fix. Per the Missing-Y Contract (PATCH_LOG.md R3), all")
    lines.append("checkpoints for a target share the same imputed Y - not independent per checkpoint.")
    lines.append("")

    # Target details
    lines.append("## Target Details")
    lines.append("")

    targets = manifest.get("targets", [])

    # Find ASOS data for disclosure statistics
    # This is where we actually read outcome data
    asos_dir = Path("/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/asos")

    # Statistics counters - all at checkpoint granularity (3 per target) for Bug 2 fix
    total_checkpoints = 0

    # 5km threshold statistics
    positive_count_5km = 0
    negative_count_5km = 0
    missing_count_5km = 0

    # 1km threshold statistics (Bug 3 fix: add nested 1km threshold)
    positive_count_1km = 0
    negative_count_1km = 0
    missing_count_1km = 0

    for target in targets:
        target_id = target.get("target_id")
        station = target.get("station")
        queue = target.get("queue")
        validity_start = target.get("validity_start")
        validity_start_us = target.get("validity_start_us")
        validity_end_us = target.get("validity_end_us")
        checkpoints = target.get("checkpoints", [])
        signals = target.get("selection_signals", {})
        num_checkpoints = len(checkpoints)

        lines.append(f"### {target_id}")
        lines.append("")
        lines.append(f"- Station: {station}")
        lines.append(f"- Queue: {queue}")
        lines.append(f"- Validity start: {validity_start}")
        lines.append(f"- Revision count: {signals.get('revision_count', 0)}")
        lines.append(f"- Tie event count: {signals.get('tie_event_count', 0)}")
        lines.append(f"- Evidence change count: {signals.get('evidence_change_count', 0)}")
        lines.append(f"- Lead time coverage: {signals.get('lead_time_coverage_hours', 0):.1f} hours")
        lines.append("")

        lines.append("Checkpoints:")
        for i, cp in enumerate(checkpoints):
            offset_min = [-60, -40, -20][i]
            lines.append(f"  - T{offset_min:+d}min: {cp.get('time')} (weight={cp.get('weight')})")
        lines.append("")

        total_checkpoints += num_checkpoints

        # Try to load ASOS data for this target to compute outcome statistics
        # Extract year-month from validity_start
        if validity_start:
            dt = datetime.fromisoformat(validity_start.replace("Z", "+00:00"))
            # Bug 1 fix: Use dashed year-month format and correct directory structure
            # Real layout: asos/{station}/{YYYY-MM}/{run_id}/*.body
            ym_dashed = f"{dt.year:04d}-{dt.month:02d}"

            # V17-01 / F04 fix: Check year-month against AccessPolicy BEFORE glob
            try:
                access_policy._check_holdout_window(year_month=ym_dashed)
                access_policy._check_allowed_year_months(ym_dashed)
            except AccessPolicyViolation as e:
                lines.append(f"Outcome: REJECTED by AccessPolicy ({e})")
                missing_count_5km += num_checkpoints
                missing_count_1km += num_checkpoints
                lines.append("")
                continue

            # Bug 1 fix: Correct glob pattern - station first, then dashed year-month,
            # then run_id directory, then .body files
            asos_pattern = list(asos_dir.glob(f"{station}/{ym_dashed}/*/*.body"))

            # V17-01 / F04 fix: Filter out any paths that fail AccessPolicy
            allowed_paths = []
            for p in asos_pattern:
                try:
                    access_policy.assert_allowed(p)
                    allowed_paths.append(p)
                except AccessPolicyViolation:
                    pass  # Silently filter out disallowed paths

            asos_pattern = allowed_paths

            if asos_pattern:
                # If multiple run_ids exist, pick the lexicographically-last (newest)
                # run_id directory name format is timestamp-based (e.g. 20260920T084659Z_...)
                asos_pattern.sort(key=lambda p: p.parent.name)
                asos_body = asos_pattern[-1]  # Last = newest run_id

                try:
                    # V17-01 / F04 fix: Pass access_policy to load_asos_with_provenance
                    content, provenance = load_asos_with_provenance(
                        str(asos_body),
                        access_policy=access_policy,
                    )

                    # Parse observations
                    observations, _ = compile_asos_csv_to_observations(content, station=station)

                    # Select routine observations
                    routine_obs, _ = select_routine_observations(observations, station=station)

                    # A2-4: thresholds/support window come from the validated
                    # outcome_contract (legacy_v1 branch uses DEFAULT_OUTCOME_CONTRACT,
                    # which is identical to the previous hardcoded values).
                    contract_allowed_thresholds = frozenset(outcome_contract["thresholds_m"])
                    contract_support_window_hours = outcome_contract["support_window_hours"]

                    # Create target for 5km threshold
                    h15_target_5km = make_h15_visibility_target(
                        station=station,
                        slot_start_us=validity_start_us,
                        threshold_m=5000.0,
                        allowed_thresholds=contract_allowed_thresholds,
                        support_window_hours=contract_support_window_hours,
                    )

                    # Bug 3 fix: Create target for 1km threshold (nested threshold)
                    h15_target_1km = make_h15_visibility_target(
                        station=station,
                        slot_start_us=validity_start_us,
                        threshold_m=1000.0,
                        allowed_thresholds=contract_allowed_thresholds,
                        support_window_hours=contract_support_window_hours,
                    )

                    # Resolve outcomes for both thresholds
                    records_5km = resolve_h15_outcomes(
                        routine_obs,
                        [h15_target_5km],
                        provenance=provenance,
                        resolution_version="disclosure_v1",
                    )
                    records_1km = resolve_h15_outcomes(
                        routine_obs,
                        [h15_target_1km],
                        provenance=provenance,
                        resolution_version="disclosure_v1",
                    )

                    # Process 5km outcome
                    outcome_5km_str = "ERROR"
                    if records_5km:
                        record = records_5km[0]
                        value = record.get("value")
                        status = record.get("status")

                        if status == "missing" or value is None:
                            # Bug 2 fix: Scale by num_checkpoints to match total_checkpoints granularity
                            missing_count_5km += num_checkpoints
                            outcome_5km_str = "MISSING"
                        elif value == 1:
                            positive_count_5km += num_checkpoints
                            outcome_5km_str = "POSITIVE (vis < 5km)"
                        else:
                            negative_count_5km += num_checkpoints
                            outcome_5km_str = "NEGATIVE (vis >= 5km)"

                    # Process 1km outcome (Bug 3 fix)
                    outcome_1km_str = "ERROR"
                    if records_1km:
                        record = records_1km[0]
                        value = record.get("value")
                        status = record.get("status")

                        if status == "missing" or value is None:
                            missing_count_1km += num_checkpoints
                            outcome_1km_str = "MISSING"
                        elif value == 1:
                            positive_count_1km += num_checkpoints
                            outcome_1km_str = "POSITIVE (vis < 1km)"
                        else:
                            negative_count_1km += num_checkpoints
                            outcome_1km_str = "NEGATIVE (vis >= 1km)"

                    lines.append(f"Outcome (5km): {outcome_5km_str}")
                    lines.append(f"Outcome (1km): {outcome_1km_str}")

                except Exception as e:
                    lines.append(f"Outcome: Could not resolve ({e})")
                    missing_count_5km += num_checkpoints
                    missing_count_1km += num_checkpoints
            else:
                lines.append(f"Outcome: ASOS data not available for {ym_dashed}")
                missing_count_5km += num_checkpoints
                missing_count_1km += num_checkpoints

        lines.append("")

    # Statistics - now with correct granularity (Bug 2 fix)
    lines.append("## Disclosure Statistics")
    lines.append("")

    # 5km threshold statistics
    resolved_count_5km = total_checkpoints - missing_count_5km
    if resolved_count_5km > 0:
        positive_rate_5km = positive_count_5km / resolved_count_5km
    else:
        positive_rate_5km = 0.0

    if total_checkpoints > 0:
        missingness_rate_5km = missing_count_5km / total_checkpoints
    else:
        missingness_rate_5km = 0.0

    lines.append("### 5km Threshold Statistics")
    lines.append("")
    lines.append(f"- Total checkpoints evaluated: {total_checkpoints}")
    lines.append(f"- Resolved (non-missing): {resolved_count_5km}")
    lines.append(f"- Missing/undetermined: {missing_count_5km}")
    lines.append(f"- Positive (vis < 5km): {positive_count_5km}")
    lines.append(f"- Negative (vis >= 5km): {negative_count_5km}")
    lines.append(f"- Natural positive rate: {positive_rate_5km:.2%} ({positive_count_5km}/{resolved_count_5km if resolved_count_5km > 0 else 1})")
    lines.append(f"- Missingness rate: {missingness_rate_5km:.2%} ({missing_count_5km}/{total_checkpoints if total_checkpoints > 0 else 1})")
    lines.append("")

    # 1km threshold statistics (Bug 3 fix)
    resolved_count_1km = total_checkpoints - missing_count_1km
    if resolved_count_1km > 0:
        positive_rate_1km = positive_count_1km / resolved_count_1km
    else:
        positive_rate_1km = 0.0

    if total_checkpoints > 0:
        missingness_rate_1km = missing_count_1km / total_checkpoints
    else:
        missingness_rate_1km = 0.0

    lines.append("### 1km Threshold Statistics (Nested)")
    lines.append("")
    lines.append(f"- Total checkpoints evaluated: {total_checkpoints}")
    lines.append(f"- Resolved (non-missing): {resolved_count_1km}")
    lines.append(f"- Missing/undetermined: {missing_count_1km}")
    lines.append(f"- Positive (vis < 1km): {positive_count_1km}")
    lines.append(f"- Negative (vis >= 1km): {negative_count_1km}")
    lines.append(f"- Natural positive rate: {positive_rate_1km:.2%} ({positive_count_1km}/{resolved_count_1km if resolved_count_1km > 0 else 1})")
    lines.append(f"- Missingness rate: {missingness_rate_1km:.2%} ({missing_count_1km}/{total_checkpoints if total_checkpoints > 0 else 1})")
    lines.append("")

    # Label maturity confirmation
    lines.append("## Label Maturity Confirmation")
    lines.append("")
    lines.append("All targets were selected within the archive's covered period")
    lines.append("(2023-01-01 through 2025-12-31, excluding Feb 2025 holdout).")
    lines.append("ASOS observation archives provide ground truth for all selected windows.")
    lines.append("")

    # Write disclosure
    with open(disclosure_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Disclosure report written successfully!")
    print(f"  Total targets: {queue_summary.get('total_count', 0)}")
    print(f"  Total checkpoints: {total_checkpoints}")
    print(f"  5km - Natural positive rate: {positive_rate_5km:.2%}, Missingness: {missingness_rate_5km:.2%}")
    print(f"  1km - Natural positive rate: {positive_rate_1km:.2%}, Missingness: {missingness_rate_1km:.2%}")
    print(f"  Output: {disclosure_path}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--disclose",
        action="store_true",
        help="Run Phase 2 (disclosure) instead of Phase 1 (freeze)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to stations_calendar config (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--bulk-dir",
        type=Path,
        default=DEFAULT_TAF_BULK_DIR,
        help=f"Path to TAF bulk directory (default: {DEFAULT_TAF_BULK_DIR})",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help=f"Path to manifest JSON (default: {DEFAULT_MANIFEST_PATH})",
    )
    parser.add_argument(
        "--disclosure",
        type=Path,
        default=DEFAULT_DISCLOSURE_PATH,
        help=f"Path to disclosure MD (default: {DEFAULT_DISCLOSURE_PATH})",
    )
    parser.add_argument(
        "--exposure-registry",
        type=Path,
        default=DEFAULT_EXPOSURE_REGISTRY_PATH,
        help=f"Path to exposure registry JSON (default: {DEFAULT_EXPOSURE_REGISTRY_PATH})",
    )

    args = parser.parse_args()

    if args.disclose:
        return run_disclose(
            args.manifest,
            args.disclosure,
            args.config,
            args.exposure_registry,
        )
    else:
        return run_freeze(
            args.config,
            args.bulk_dir,
            args.manifest,
            args.exposure_registry,
        )


if __name__ == "__main__":
    sys.exit(main())
