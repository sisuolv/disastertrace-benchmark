#!/usr/bin/env python3
"""V17-03: Evidence transition census for H15 data qualification.

This script performs a Y-blind (no ASOS/outcome reading) census of verifiable
target-relevant evidence changes in the TAF development material.

CRITICAL Y-ISOLATION BOUNDARIES:
- This script MUST NOT import any outcome_wiring symbols
- This script MUST NOT import compile_asos_csv_to_observations
- This script MUST NOT import load_asos_with_provenance
- This script MUST NOT import resolve_h15_outcomes
- This script MUST NOT import register_h15_outcomes
- This script MUST NOT read any file under asos/ directories
- This script MUST NOT access quarantine_holdout/

The census answers: Before prediction deadlines on fixed weather-risk targets,
do verifiable target-relevant evidence changes genuinely exist, in enough
volume/quality to support state-maintenance-vs-revision evaluation (H15)?

Exit codes:
  0 - Census completed successfully
  1 - Census found issues but completed
  2 - Hard gate failure (missing/mismatched files)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Resolve project root for imports
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))

# TAF-side imports only - NO outcome_wiring, NO ASOS
from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream
from disastertrace.revision_v1.ledger import (
    compile_ledger,
    Provenance,
    ProductLineage,
    _validity_windows_overlap_or_adjacent,
)
from disastertrace.revision_v1.tie_resolution import resolve_receipt_tie_strict
from disastertrace.monitoring_v1.providers.versions import latest_issuance
from disastertrace.monitoring_v1.targets import utc_us


# =============================================================================
# Explicit 140-file allow list (mirroring validate_dl3r_semantics.py)
# =============================================================================

STATIONS = ["KSFO", "KDEN", "KJFK", "KORD"]

# Build YEAR_MONTHS: 2023-01 through 2025-12, excluding 2025-02 (holdout)
YEAR_MONTHS = []
for year in [2023, 2024, 2025]:
    for month in range(1, 13):
        ym = f"{year:04d}{month:02d}"
        # Feb 2025 is holdout - NEVER read it
        if ym == "202502":
            continue
        YEAR_MONTHS.append(ym)

# Explicit expected files: 4 stations x 35 months = 140
EXPECTED_FILES = [(st, ym) for st in STATIONS for ym in YEAR_MONTHS]
assert len(EXPECTED_FILES) == 140, f"Expected 140 files, got {len(EXPECTED_FILES)}"


# =============================================================================
# Process grouping rule - DEFINED BEFORE RUNNING STATS
# =============================================================================

PROCESS_GROUPING_VERSION = "process_grouping.v1"
PROCESS_GROUPING_RULE = """
Process Grouping Rule (v1):
---------------------------
Evidence changes belong to the SAME weather process group if ALL of:
1. Same station (ICAO code)
2. Same UTC calendar day (defined by day-of-year at 00:00:00Z)

This rule means each station-day pair is ONE independent weather process.

Justification:
- TAF products are issued routinely every 6 hours (00Z, 06Z, 12Z, 18Z)
- A single weather system (front, storm) typically affects a station for 6-24 hours
- Calendar-day grouping is the standard unit for meteorological verification
- Same-day amendments/corrections are typically responses to the same weather evolution
- Cross-day boundaries represent synoptic breaks (new 00Z issuance cycle)
- This rule is simple, unambiguous, and verifiable from UTC timestamps

Count semantics:
- Total process groups = number of distinct (station, calendar_day) pairs
- Not "number of distinct synoptic events" which would require meteorological expertise
- Represents UPPER BOUND on independent weather-driven decisions

This rule is VERSION-LOCKED: the same rule version produces the same grouping.
Any changes to the rule require a new version (v2, v3, etc.).
"""

# Day in microseconds for calendar-day grouping
DAY_US = 24 * 3600 * 1_000_000


# =============================================================================
# Change classification types
# =============================================================================

@dataclass
class EvidenceChange:
    """Represents a single evidence change event."""
    target_station: str
    target_validity_start_us: int
    target_validity_end_us: int
    change_type: str  # AMD, COR, CNL, supply_gap, tie_conflict, mirror_duplicate
    predecessor_source_id: str | None
    current_source_id: str
    original_text_sha256: str
    issued_at_us: int
    dispute_status: str  # resolved, unresolved, none
    process_group_id: str | None = None


@dataclass
class CandidateSlot:
    """Represents a continuous-calendar candidate slot."""
    station: str
    validity_start_us: int
    validity_end_us: int
    checkpoint_t60_us: int
    checkpoint_t40_us: int
    checkpoint_t20_us: int
    changes_before_deadline: list[EvidenceChange] = field(default_factory=list)
    has_any_evidence: bool = False  # whether any TAF evidence exists for this slot


@dataclass
class CensusResult:
    """Complete census result."""
    # File integrity
    files_checked: int
    files_ok: int
    files_missing: list[str]
    files_hash_mismatch: list[dict]

    # Continuous calendar
    total_continuous_calendar_slots: int
    slots_with_evidence: int
    slots_without_evidence: int

    # Revision-enriched counts
    slots_with_pre_deadline_changes: int
    total_pre_deadline_changes: int
    changes_by_type: dict[str, int]

    # Process groups
    total_process_groups: int
    process_groups_by_station: dict[str, int]

    # Dispute/conflict rate
    unresolved_conflicts: int
    disputed_changes: int

    # Package stats
    total_packages_compiled: int
    skipped_frames: int


# =============================================================================
# File integrity verification
# =============================================================================

def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_140_files(bulk_dir: Path) -> tuple[list[tuple[str, str, Path, Path]], list[str], list[dict]]:
    """Verify all 140 expected files exist with correct SHA256.

    Returns:
        Tuple of (verified_files, missing, hash_mismatches) where:
        - verified_files: list of (station, year_month, body_path, json_path) for valid files
        - missing: list of missing file descriptions
        - hash_mismatches: list of mismatch dicts
    """
    verified = []
    missing = []
    mismatches = []

    # Hard boundary check - NEVER access quarantine_holdout
    if "quarantine_holdout" in str(bulk_dir):
        raise RuntimeError(f"BOUNDARY VIOLATION: bulk_dir contains quarantine_holdout: {bulk_dir}")

    for station, year_month in EXPECTED_FILES:
        # Additional boundary check for 202502 (should never be in list, but defense in depth)
        if year_month == "202502":
            raise RuntimeError("BOUNDARY VIOLATION: 202502 should not be in EXPECTED_FILES")

        body_file = bulk_dir / f"{station}_{year_month}.body"
        json_file = bulk_dir / f"{station}_{year_month}.json"

        if not body_file.exists():
            missing.append(f"{station}_{year_month}.body")
            continue
        if not json_file.exists():
            missing.append(f"{station}_{year_month}.json")
            continue

        # Verify SHA256
        with open(json_file, "r") as f:
            receipt = json.load(f)
        expected_sha = receipt.get("sha256", "")
        actual_sha = sha256_file(body_file)

        if expected_sha != actual_sha:
            mismatches.append({
                "file": f"{station}_{year_month}.body",
                "expected": expected_sha,
                "actual": actual_sha,
            })
            continue

        verified.append((station, year_month, body_file, json_file))

    return verified, missing, mismatches


# =============================================================================
# Continuous calendar enumeration
# =============================================================================

def generate_continuous_calendar_slots(
    calendar_start_us: int,
    calendar_end_us: int,
    holdout_start_us: int,
    holdout_end_us: int,
) -> list[CandidateSlot]:
    """Generate all routine-hour slots across the full calendar for all stations.

    Per the H15 contract: every station x day x hour routine slot across the
    35-month calendar, per the stations_calendar config.

    Routine TAF hours are: 00Z, 06Z, 12Z, 18Z (every 6 hours).
    """
    hour_us = 3600 * 1_000_000
    day_us = 24 * hour_us

    # Routine issuance hours (UTC)
    ROUTINE_HOURS = [0, 6, 12, 18]

    slots = []

    # Iterate through each day
    current_day_start = calendar_start_us
    while current_day_start < calendar_end_us:
        for station in STATIONS:
            for routine_hour in ROUTINE_HOURS:
                # Target window: the hour starting at routine_hour
                validity_start = current_day_start + routine_hour * hour_us
                validity_end = validity_start + hour_us

                # Skip if outside calendar
                if validity_end > calendar_end_us:
                    continue

                # Skip if overlaps holdout
                if (validity_start < holdout_end_us and validity_end > holdout_start_us):
                    continue

                # Checkpoints: T-60, T-40, T-20 before validity_start
                t60 = validity_start - 60 * 60 * 1_000_000  # 60 minutes
                t40 = validity_start - 40 * 60 * 1_000_000  # 40 minutes
                t20 = validity_start - 20 * 60 * 1_000_000  # 20 minutes

                # Skip if checkpoints would fall in holdout
                if any(holdout_start_us <= cp < holdout_end_us for cp in [t60, t40, t20]):
                    continue

                slot = CandidateSlot(
                    station=station,
                    validity_start_us=validity_start,
                    validity_end_us=validity_end,
                    checkpoint_t60_us=t60,
                    checkpoint_t40_us=t40,
                    checkpoint_t20_us=t20,
                )
                slots.append(slot)

        current_day_start += day_us

    return slots


# =============================================================================
# Evidence change classification
# =============================================================================

def classify_changes_for_slot(
    slot: CandidateSlot,
    packages_by_station: dict[str, list[dict]],
) -> list[EvidenceChange]:
    """Classify all evidence changes relevant to a candidate slot.

    Returns changes that:
    1. Are from the same station
    2. Have validity windows overlapping/adjacent with the target
    3. Were issued BEFORE the target's validity_start (pre-deadline)
    """
    changes = []
    station_packages = packages_by_station.get(slot.station, [])

    if not station_packages:
        return changes

    # Filter to relevant packages: same station, overlapping/adjacent validity,
    # issued BEFORE target validity start
    relevant = []
    for pkg in station_packages:
        # Must be issued before deadline (validity_start)
        if pkg["issued_at"] >= slot.validity_start_us:
            continue

        # Must overlap or be adjacent to target validity
        pkg_valid_start = pkg.get("valid_start", 0)
        pkg_valid_end = pkg.get("valid_end", 0)

        # Check overlap/adjacency
        if pkg_valid_start <= slot.validity_end_us and pkg_valid_end >= slot.validity_start_us:
            relevant.append(pkg)
        elif pkg_valid_end == slot.validity_start_us:  # Adjacent
            relevant.append(pkg)
        elif pkg_valid_start == slot.validity_end_us:  # Adjacent
            relevant.append(pkg)

    if not relevant:
        return changes

    slot.has_any_evidence = True

    # Build index from source_id to package for lookups
    pkg_by_source_id = {pkg["source_id"]: pkg for pkg in relevant}

    # Compile ledger for these packages to get classification
    try:
        ledger = compile_ledger(relevant)
    except Exception:
        # If ledger compilation fails, record as unresolved
        for pkg in relevant:
            changes.append(EvidenceChange(
                target_station=slot.station,
                target_validity_start_us=slot.validity_start_us,
                target_validity_end_us=slot.validity_end_us,
                change_type="compilation_error",
                predecessor_source_id=None,
                current_source_id=pkg["source_id"],
                original_text_sha256=pkg.get("native_semantics_sha256", "unknown"),
                issued_at_us=pkg["issued_at"],
                dispute_status="unresolved",
            ))
        return changes

    # Classify each ledger entry
    for entry in ledger:
        kind = entry.get("kind", "unknown")
        source_id = entry.get("source_id", "unknown")
        supersedes = entry.get("supersedes", [])
        superseded_by = entry.get("superseded_by", [])

        # Look up issued_at from original package
        orig_pkg = pkg_by_source_id.get(source_id, {})
        issued_at_us = orig_pkg.get("issued_at", 0)
        semantic_hash = orig_pkg.get("native_semantics_sha256", "unknown")

        # Determine change type
        change_type: str
        predecessor_id: str | None = None
        dispute_status = "none"

        if kind == "amendment_supersedes":
            change_type = "AMD"
            predecessor_id = supersedes[0] if supersedes else None
        elif kind == "correction":
            change_type = "COR"
            predecessor_id = supersedes[0] if supersedes else None
        elif kind == "cancellation":
            change_type = "CNL"
            predecessor_id = supersedes[0] if supersedes else None
        elif kind == "mirror":
            change_type = "mirror_duplicate"
        elif kind == "lossless_duplicate":
            change_type = "mirror_duplicate"
        elif kind == "new_observation":
            # Not a change, skip
            continue
        elif kind == "no_change_reissue":
            # Not a meaningful change for transition census
            continue
        elif kind == "baseline_update":
            # Not a change, skip
            continue
        elif kind == "late_superseded":
            # This is superseded BY something, not a new change
            continue
        else:
            # Unknown kind - record for investigation
            change_type = f"unknown_{kind}"

        # Check for unresolved ties/conflicts in the entry
        if entry.get("tie_unresolved"):
            dispute_status = "unresolved"
            change_type = "tie_conflict"

        changes.append(EvidenceChange(
            target_station=slot.station,
            target_validity_start_us=slot.validity_start_us,
            target_validity_end_us=slot.validity_end_us,
            change_type=change_type,
            predecessor_source_id=predecessor_id,
            current_source_id=source_id,
            original_text_sha256=semantic_hash,
            issued_at_us=issued_at_us,
            dispute_status=dispute_status,
        ))

    return changes


# =============================================================================
# Process grouping
# =============================================================================

def assign_process_groups(changes: list[EvidenceChange]) -> dict[str, list[EvidenceChange]]:
    """Assign changes to weather process groups per the v1 rule.

    Groups changes by:
    1. Same station
    2. Same UTC calendar day (issued_at timestamp)

    Each (station, calendar_day) pair is one process group.
    """
    if not changes:
        return {}

    groups: dict[str, list[EvidenceChange]] = {}

    # Group by (station, calendar_day) where calendar_day = issued_at_us // DAY_US
    for change in changes:
        # Compute calendar day (days since epoch)
        calendar_day = change.issued_at_us // DAY_US
        group_id = f"{change.target_station}_{calendar_day}"

        if group_id not in groups:
            groups[group_id] = []
        groups[group_id].append(change)
        change.process_group_id = group_id

    return groups


# =============================================================================
# Main census logic
# =============================================================================

def run_census(
    bulk_dir: Path,
    config_path: Path,
    artifacts_dir: Path | None = None,
) -> CensusResult:
    """Run the complete transition census.

    Args:
        bulk_dir: Path to DL-3R bulk archive
        config_path: Path to stations_calendar_v16.json
        artifacts_dir: Optional path for detailed output

    Returns:
        CensusResult with all census statistics
    """
    # Load calendar config
    with open(config_path, "r") as f:
        config = json.load(f)

    calendar_start_us = utc_us(config["calendar_start"])
    calendar_end_us = utc_us(config["calendar_end"])
    holdout_start_us = utc_us(config["holdout_exclusion"]["window_start"])
    holdout_end_us = utc_us(config["holdout_exclusion"]["window_end"])

    # Step 1: Verify 140 files
    print("Step 1: Verifying 140 expected files...")
    verified, missing, mismatches = verify_140_files(bulk_dir)
    print(f"  Verified: {len(verified)}, Missing: {len(missing)}, Mismatched: {len(mismatches)}")

    if missing or mismatches:
        print("WARNING: File integrity issues found")
        for m in missing[:5]:
            print(f"  Missing: {m}")
        for mm in mismatches[:5]:
            print(f"  Mismatch: {mm['file']}")

    # Step 2: Compile all TAF packages
    print("\nStep 2: Compiling TAF packages from verified files...")
    all_packages: list[dict] = []
    total_skipped = 0

    for station, year_month, body_path, json_path in verified:
        with open(body_path, "r", errors="replace") as f:
            raw_text = f.read()

        reference_month = f"{year_month[:4]}-{year_month[4:6]}"
        packages, skipped = compile_afos_taf_stream(
            raw_text,
            station=station,
            reference_month=reference_month,
        )
        all_packages.extend(packages)
        total_skipped += len(skipped)

    print(f"  Total packages compiled: {len(all_packages)}")
    print(f"  Skipped frames: {total_skipped}")

    # Index packages by station
    packages_by_station: dict[str, list[dict]] = defaultdict(list)
    for pkg in all_packages:
        packages_by_station[pkg["station"]].append(pkg)

    # Step 3: Generate continuous calendar slots
    print("\nStep 3: Generating continuous calendar slots...")
    slots = generate_continuous_calendar_slots(
        calendar_start_us,
        calendar_end_us,
        holdout_start_us,
        holdout_end_us,
    )
    print(f"  Total slots: {len(slots)}")

    # Step 4: Classify changes for each slot
    print("\nStep 4: Classifying evidence changes for each slot...")
    all_changes: list[EvidenceChange] = []
    slots_with_changes = 0
    slots_with_evidence = 0

    for i, slot in enumerate(slots):
        if i % 10000 == 0:
            print(f"  Processing slot {i}/{len(slots)}...")

        changes = classify_changes_for_slot(slot, packages_by_station)
        slot.changes_before_deadline = changes

        if slot.has_any_evidence:
            slots_with_evidence += 1

        if changes:
            slots_with_changes += 1
            all_changes.extend(changes)

    print(f"  Slots with evidence: {slots_with_evidence}")
    print(f"  Slots with pre-deadline changes: {slots_with_changes}")
    print(f"  Total pre-deadline changes: {len(all_changes)}")

    # Step 5: Assign process groups
    print("\nStep 5: Assigning process groups...")
    process_groups = assign_process_groups(all_changes)
    print(f"  Total process groups: {len(process_groups)}")

    # Count by station
    groups_by_station: dict[str, int] = defaultdict(int)
    for group_id in process_groups:
        station = group_id.split("_")[0]
        groups_by_station[station] += 1

    # Step 6: Compute statistics
    print("\nStep 6: Computing statistics...")

    changes_by_type: dict[str, int] = defaultdict(int)
    unresolved = 0
    disputed = 0

    for change in all_changes:
        changes_by_type[change.change_type] += 1
        if change.dispute_status == "unresolved":
            unresolved += 1
        if change.dispute_status != "none":
            disputed += 1

    # Write detailed output if requested
    if artifacts_dir:
        print(f"\nWriting detailed output to {artifacts_dir}...")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Write changes JSONL
        changes_path = artifacts_dir / "all_changes.jsonl"
        with open(changes_path, "w") as f:
            for change in all_changes:
                record = {
                    "target_station": change.target_station,
                    "target_validity_start_us": change.target_validity_start_us,
                    "target_validity_end_us": change.target_validity_end_us,
                    "change_type": change.change_type,
                    "predecessor_source_id": change.predecessor_source_id,
                    "current_source_id": change.current_source_id,
                    "original_text_sha256": change.original_text_sha256,
                    "issued_at_us": change.issued_at_us,
                    "dispute_status": change.dispute_status,
                    "process_group_id": change.process_group_id,
                }
                f.write(json.dumps(record) + "\n")

        # Write process groups summary
        groups_path = artifacts_dir / "process_groups.json"
        with open(groups_path, "w") as f:
            groups_summary = {
                gid: [c.current_source_id for c in changes]
                for gid, changes in process_groups.items()
            }
            json.dump(groups_summary, f, indent=2)

        # Write slot summary
        slots_path = artifacts_dir / "slot_summary.jsonl"
        with open(slots_path, "w") as f:
            for slot in slots:
                if slot.changes_before_deadline:
                    record = {
                        "station": slot.station,
                        "validity_start_us": slot.validity_start_us,
                        "validity_end_us": slot.validity_end_us,
                        "num_changes": len(slot.changes_before_deadline),
                        "change_types": [c.change_type for c in slot.changes_before_deadline],
                    }
                    f.write(json.dumps(record) + "\n")

    return CensusResult(
        files_checked=len(EXPECTED_FILES),
        files_ok=len(verified),
        files_missing=missing,
        files_hash_mismatch=mismatches,
        total_continuous_calendar_slots=len(slots),
        slots_with_evidence=slots_with_evidence,
        slots_without_evidence=len(slots) - slots_with_evidence,
        slots_with_pre_deadline_changes=slots_with_changes,
        total_pre_deadline_changes=len(all_changes),
        changes_by_type=dict(changes_by_type),
        total_process_groups=len(process_groups),
        process_groups_by_station=dict(groups_by_station),
        unresolved_conflicts=unresolved,
        disputed_changes=disputed,
        total_packages_compiled=len(all_packages),
        skipped_frames=total_skipped,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bulk-dir",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/"
            "20260920T134949Z_1bbe63aedc00_dl3rbulk"
        ),
        help="Path to bulk DL-3R directory",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/"
            "stations_calendar_v16.json"
        ),
        help="Path to stations calendar config",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Optional path for detailed JSONL output",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for census summary JSON",
    )
    args = parser.parse_args()

    # Run census
    result = run_census(args.bulk_dir, args.config, args.artifacts_dir)

    # Print summary
    print("\n" + "=" * 70)
    print("TRANSITION CENSUS V17 SUMMARY")
    print("=" * 70)
    print(f"\nProcess Grouping Rule Version: {PROCESS_GROUPING_VERSION}")
    print(f"\nFile Integrity:")
    print(f"  Expected files: {result.files_checked}")
    print(f"  Verified OK: {result.files_ok}")
    print(f"  Missing: {len(result.files_missing)}")
    print(f"  Hash mismatches: {len(result.files_hash_mismatch)}")

    print(f"\nContinuous Calendar:")
    print(f"  Total slots: {result.total_continuous_calendar_slots}")
    print(f"  With evidence: {result.slots_with_evidence}")
    print(f"  Without evidence: {result.slots_without_evidence}")

    print(f"\nRevision-Enriched Statistics:")
    print(f"  Slots with pre-deadline changes: {result.slots_with_pre_deadline_changes}")
    print(f"  Total pre-deadline changes: {result.total_pre_deadline_changes}")
    print(f"  Changes by type:")
    for ctype, count in sorted(result.changes_by_type.items()):
        print(f"    {ctype}: {count}")

    print(f"\nProcess Groups (independent weather processes):")
    print(f"  Total groups: {result.total_process_groups}")
    for station, count in sorted(result.process_groups_by_station.items()):
        print(f"    {station}: {count}")

    print(f"\nDispute/Conflict Rate:")
    print(f"  Unresolved conflicts: {result.unresolved_conflicts}")
    print(f"  Disputed changes: {result.disputed_changes}")
    if result.total_pre_deadline_changes > 0:
        rate = result.disputed_changes / result.total_pre_deadline_changes * 100
        print(f"  Dispute rate: {rate:.2f}%")

    print(f"\nCompilation Statistics:")
    print(f"  Total packages compiled: {result.total_packages_compiled}")
    print(f"  Skipped frames: {result.skipped_frames}")

    # Write summary JSON if requested
    if args.out:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "process_grouping_version": PROCESS_GROUPING_VERSION,
            "process_grouping_rule": "calendar_day",
            "file_integrity": {
                "expected": result.files_checked,
                "verified_ok": result.files_ok,
                "missing": result.files_missing,
                "hash_mismatches": result.files_hash_mismatch,
            },
            "continuous_calendar": {
                "total_slots": result.total_continuous_calendar_slots,
                "with_evidence": result.slots_with_evidence,
                "without_evidence": result.slots_without_evidence,
            },
            "revision_enriched": {
                "slots_with_changes": result.slots_with_pre_deadline_changes,
                "total_changes": result.total_pre_deadline_changes,
                "by_type": result.changes_by_type,
            },
            "process_groups": {
                "total": result.total_process_groups,
                "by_station": result.process_groups_by_station,
            },
            "disputes": {
                "unresolved_conflicts": result.unresolved_conflicts,
                "disputed_changes": result.disputed_changes,
            },
            "compilation": {
                "total_packages": result.total_packages_compiled,
                "skipped_frames": result.skipped_frames,
            },
        }
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary written to: {args.out}")

    # Determine exit code
    if result.files_missing or result.files_hash_mismatch:
        return 2  # Hard gate failure
    elif result.unresolved_conflicts > 0:
        return 1  # Issues found
    else:
        return 0  # Success


if __name__ == "__main__":
    sys.exit(main())
