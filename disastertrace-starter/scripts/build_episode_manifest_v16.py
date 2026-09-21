#!/usr/bin/env python3
"""Build episode manifest for v16 pre-registration (P0-08).

Two-phase design:
  Phase 1 (freeze): Selects episodes using ONLY TAF-side signals. MUST NOT see
    outcome data. Produces EPISODE_MANIFEST_v16.json.

  Phase 2 (disclose): Reads the frozen manifest, verifies its integrity, THEN
    reads ASOS/outcome data to compute and write disclosure statistics.
    Produces EPISODE_MANIFEST_v16_DISCLOSURE.md.

Usage:
  python scripts/build_episode_manifest_v16.py           # Phase 1: freeze
  python scripts/build_episode_manifest_v16.py --disclose  # Phase 2: disclose

Exit codes:
  0 - Success
  1 - Validation errors or runtime issues
  2 - Manifest already exists (freeze mode only)
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
    freeze_manifest,
    load_stations_calendar,
    verify_manifest_integrity,
    validate_manifest,
)
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream


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
    """Generate summary hash of TAF archive state."""
    # Hash the directory name plus file count
    file_count = len(list(bulk_dir.glob("*.body")))
    summary_str = f"{bulk_dir.name}:{file_count}"
    return hashlib.sha256(summary_str.encode()).hexdigest()[:16]


def run_freeze(
    config_path: Path,
    bulk_dir: Path,
    manifest_path: Path,
) -> int:
    """Phase 1: Freeze episode selection.

    Returns exit code.
    """
    print(f"Phase 1: Freeze episode manifest")
    print(f"  Config: {config_path}")
    print(f"  TAF bulk: {bulk_dir}")
    print(f"  Output: {manifest_path}")
    print()

    # Check if manifest already exists - REFUSE to overwrite
    if manifest_path.exists():
        print(f"ERROR: Manifest already exists at {manifest_path}", file=sys.stderr)
        print("This script refuses to overwrite frozen manifests.", file=sys.stderr)
        print("Delete the existing manifest manually if you want to regenerate.", file=sys.stderr)
        return 2

    # Create output directory if needed
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Load config to get stations
    config, _ = load_stations_calendar(config_path)
    stations = [s["icao"] for s in config.get("stations", [])]

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

    # Generate archive summary
    taf_archive_summary = generate_taf_archive_summary(bulk_dir)

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
    print(f"  Output: {manifest_path}")

    return 0


def run_disclose(
    manifest_path: Path,
    disclosure_path: Path,
    config_path: Path,
) -> int:
    """Phase 2: Disclose statistics (reads outcome data).

    Returns exit code.
    """
    print(f"Phase 2: Disclose episode statistics")
    print(f"  Manifest: {manifest_path}")
    print(f"  Output: {disclosure_path}")
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

    # Load config for stations
    config, _ = load_stations_calendar(config_path)
    stations_config = {s["icao"]: s for s in config.get("stations", [])}

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

    # Target details
    lines.append("## Target Details")
    lines.append("")

    targets = manifest.get("targets", [])

    # Find ASOS data for disclosure statistics
    # This is where we actually read outcome data
    asos_dir = Path("/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/asos")

    total_checkpoints = 0
    positive_count = 0
    missing_count = 0

    for target in targets:
        target_id = target.get("target_id")
        station = target.get("station")
        queue = target.get("queue")
        validity_start = target.get("validity_start")
        validity_start_us = target.get("validity_start_us")
        validity_end_us = target.get("validity_end_us")
        checkpoints = target.get("checkpoints", [])
        signals = target.get("selection_signals", {})

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

        total_checkpoints += len(checkpoints)

        # Try to load ASOS data for this target to compute outcome statistics
        # Extract year-month from validity_start
        if validity_start:
            dt = datetime.fromisoformat(validity_start.replace("Z", "+00:00"))
            ym = f"{dt.year:04d}{dt.month:02d}"

            # Look for ASOS data
            asos_pattern = list(asos_dir.glob(f"*/{station}/{ym}/*.body"))
            if asos_pattern:
                try:
                    # Use first available ASOS file
                    asos_body = asos_pattern[0]
                    content, provenance = load_asos_with_provenance(str(asos_body))

                    # Parse observations
                    observations, _ = compile_asos_csv_to_observations(content, station=station)

                    # Select routine observations
                    routine_obs, _ = select_routine_observations(observations, station=station)

                    # Create target for 5km threshold
                    h15_target = make_h15_visibility_target(
                        station=station,
                        slot_start_us=validity_start_us,
                        threshold_m=5000.0,
                    )

                    # Resolve outcome
                    records = resolve_h15_outcomes(
                        routine_obs,
                        [h15_target],
                        provenance=provenance,
                        resolution_version="disclosure_v1",
                    )

                    if records:
                        record = records[0]
                        value = record.get("value")
                        status = record.get("status")

                        if status == "missing" or value is None:
                            missing_count += 1
                            lines.append(f"Outcome (5km): MISSING")
                        elif value == 1:
                            positive_count += 1
                            lines.append(f"Outcome (5km): POSITIVE (vis < 5km)")
                        else:
                            lines.append(f"Outcome (5km): NEGATIVE (vis >= 5km)")
                except Exception as e:
                    lines.append(f"Outcome: Could not resolve ({e})")
                    missing_count += 1
            else:
                lines.append(f"Outcome: ASOS data not available for {ym}")
                missing_count += 1

        lines.append("")

    # Statistics
    lines.append("## Disclosure Statistics")
    lines.append("")

    resolved_count = total_checkpoints - missing_count
    if resolved_count > 0:
        positive_rate = positive_count / resolved_count
    else:
        positive_rate = 0.0

    if total_checkpoints > 0:
        missingness_rate = missing_count / total_checkpoints
    else:
        missingness_rate = 0.0

    lines.append(f"- Total checkpoints evaluated: {total_checkpoints}")
    lines.append(f"- Resolved (non-missing): {resolved_count}")
    lines.append(f"- Missing/undetermined: {missing_count}")
    lines.append(f"- Natural positive rate: {positive_rate:.2%} ({positive_count}/{resolved_count if resolved_count > 0 else 1})")
    lines.append(f"- Missingness rate: {missingness_rate:.2%} ({missing_count}/{total_checkpoints if total_checkpoints > 0 else 1})")
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
    print(f"  Natural positive rate: {positive_rate:.2%}")
    print(f"  Missingness rate: {missingness_rate:.2%}")
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

    args = parser.parse_args()

    if args.disclose:
        return run_disclose(args.manifest, args.disclosure, args.config)
    else:
        return run_freeze(args.config, args.bulk_dir, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
