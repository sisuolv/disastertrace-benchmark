#!/usr/bin/env python3
"""Validate DL-3R raw TAF data semantics against CSV reference and reconciliation.

This script performs comprehensive validation of the DL-3R bulk download:
- Hard gate: verify all 140 expected files exist with correct SHA256
- Compile each station-month using episode_compiler.py
- Check semantic consistency: amendment kind, status, latest_issuance uniqueness
- Cross-check issued_at timestamps against CSV product_ids

Exit codes:
  0 - All checks passed
  1 - Semantic issues found (report written)
  2 - Hard gate failure (report NOT written)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# Resolve project root for imports
_project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project / "src"))

from disastertrace.revision_v1.episode_compiler import compile_afos_taf_stream
from disastertrace.monitoring_v1.providers.versions import latest_issuance, resolve_receipt_tie
from disastertrace.revision_v1.tie_resolution import (
    check_receipt_premise as _shared_check_receipt_premise,
    check_bbb_order_vs_receipt_order as _shared_check_bbb_order_vs_receipt_order,
    resolve_receipt_tie_strict,
)


# Expected station-month combinations (35 months x 4 stations = 140)
# Feb 2025 is excluded (holdout)
STATIONS = ["KSFO", "KDEN", "KJFK", "KORD"]
YEAR_MONTHS = []
for year in [2023, 2024, 2025]:
    for month in range(1, 13):
        if year == 2025 and month > 12:
            break
        # Exclude Feb 2025 (holdout)
        if year == 2025 and month == 2:
            continue
        YEAR_MONTHS.append(f"{year:04d}{month:02d}")

# Filter to 35 months: Jan 2023 through Dec 2025, excluding Feb 2025
# Actually from the data, we have: 2023-01 through 2025-12, excluding 2025-02
# That's 3*12 - 1 = 35 months
YEAR_MONTHS = []
for year in [2023, 2024, 2025]:
    for month in range(1, 13):
        ym = f"{year:04d}{month:02d}"
        # Feb 2025 is holdout
        if ym == "202502":
            continue
        YEAR_MONTHS.append(ym)

EXPECTED_FILES = [(st, ym) for st in STATIONS for ym in YEAR_MONTHS]
assert len(EXPECTED_FILES) == 140, f"Expected 140 files, got {len(EXPECTED_FILES)}"


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def count_soh_etx(text: str) -> tuple[int, int]:
    """Count SOH (\\x01) and ETX (\\x03) characters in text."""
    return text.count("\x01"), text.count("\x03")


def parse_reconciliation_table(path: Path) -> dict[tuple[str, str], dict]:
    """Parse RECONCILIATION_DL3R.md into a lookup table.

    Returns:
        Dict mapping (station, year_month) -> row data dict with keys:
        csv_product_id_count, raw_frame_count, diff_pct, backfill_count,
        final_coverage_count, final_coverage_pct, notes
    """
    result = {}
    with open(path, "r") as f:
        content = f.read()

    # Find the table section
    in_table = False
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("| Station"):
            in_table = True
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|") or not in_table:
            continue

        # Parse table row
        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty, parts[1] is Station, etc.
        if len(parts) < 10:
            continue
        try:
            station = parts[1]
            year_month = parts[2]
            csv_count = int(parts[3])
            raw_count = int(parts[4])
            diff_pct = parts[5]
            backfill = int(parts[6])
            final_count = int(parts[7])
            final_pct = parts[8]
            notes = parts[9] if len(parts) > 9 else "-"

            result[(station, year_month)] = {
                "csv_product_id_count": csv_count,
                "raw_frame_count": raw_count,
                "diff_pct": diff_pct,
                "backfill_count": backfill,
                "final_coverage_count": final_count,
                "final_coverage_pct": final_pct,
                "notes": notes,
            }
        except (ValueError, IndexError):
            continue

    return result


def extract_csv_product_ids(csv_path: Path) -> set[str]:
    """Extract unique product_ids from a pyIEM TAF CSV file.

    Handles the special case of 0-byte files by trying _proxy sibling.
    """
    if csv_path.stat().st_size == 0:
        # Try proxy file
        proxy_path = csv_path.with_suffix(".body").parent / (
            csv_path.stem + "_proxy.body"
        )
        if proxy_path.exists():
            csv_path = proxy_path
        else:
            return set()

    product_ids = set()
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("product_id", "")
            if pid and pid.strip():
                product_ids.add(pid.strip())
    return product_ids


def extract_issued_yyyymmddhhmm(product_id: str) -> str | None:
    """Extract YYYYMMDDHHmm prefix from product_id.

    Format: YYYYMMDDHHmm-{office}-{TTAAII}-{PIL}[-{BBB}]
    Returns the YYYYMMDDHHmm prefix or None if invalid.
    """
    parts = product_id.split("-")
    if len(parts) >= 4:
        return parts[0]
    return None


def issued_at_to_yyyymmddhhmm(issued_at_us: int) -> str:
    """Convert microseconds timestamp to YYYYMMDDHHmm string."""
    dt = datetime.fromtimestamp(issued_at_us / 1_000_000, tz=timezone.utc)
    return f"{dt.year:04d}{dt.month:02d}{dt.day:02d}{dt.hour:02d}{dt.minute:02d}"


def validate_wmo_bbb_consistency(packages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Check wmo_bbb <-> amendment_kind consistency.

    Rules:
    - None -> "original"
    - AAx (AAA, AAB, ...) -> "AMD"
    - CCx (CCA, CCB, ...) -> "COR"
    - RRx (RRA, RRB, ...) -> "original" (delayed routine bulletin)

    Returns (violations, rrx_recognized) where:
    - violations: list of violation dicts
    - rrx_recognized: list of packages with RRx codes that were correctly recognized
    """
    violations = []
    rrx_recognized = []

    for pkg in packages:
        wmo_bbb = pkg.get("wmo_bbb")
        kind = pkg.get("amendment_kind")

        expected_kind = None
        if wmo_bbb is None:
            expected_kind = "original"
        elif wmo_bbb.startswith("AA"):
            expected_kind = "AMD"
        elif wmo_bbb.startswith("CC"):
            expected_kind = "COR"
        elif wmo_bbb.startswith("RR"):
            # RRx = delayed/re-sent routine bulletin, expects original
            expected_kind = "original"
            if kind == expected_kind:
                # Correctly recognized RRx with original body
                rrx_recognized.append({
                    "source_id": pkg.get("source_id"),
                    "wmo_bbb": wmo_bbb,
                    "amendment_kind": kind,
                })
            # If kind != expected_kind, fall through to mismatch check below
        else:
            # Unknown BBB suffix
            violations.append({
                "source_id": pkg.get("source_id"),
                "wmo_bbb": wmo_bbb,
                "amendment_kind": kind,
                "error": f"Unknown wmo_bbb pattern: {wmo_bbb}",
            })
            continue

        if kind != expected_kind:
            violations.append({
                "source_id": pkg.get("source_id"),
                "wmo_bbb": wmo_bbb,
                "amendment_kind": kind,
                "error": f"Expected {expected_kind}, got {kind}",
            })

    return violations, rrx_recognized


def _get_bbb_family(wmo_bbb: str | None) -> str | None:
    """Extract the 2-letter BBB family prefix (AA, CC, RR, etc.)."""
    if wmo_bbb is None or len(wmo_bbb) < 2:
        return None
    return wmo_bbb[:2]


def _check_bbb_order_vs_receipt_order(members: list[dict]) -> bool:
    """Check if BBB letter order agrees with receipt_seq order within same family.

    V17-02 / F10 fix: Now uses the shared implementation from tie_resolution.py
    to ensure validator and runtime use identical logic.

    Returns True if no contradiction found (agreement or no comparable pairs).
    Returns False if any same-family pair has BBB order disagreeing with receipt order.
    """
    ok, _ = _shared_check_bbb_order_vs_receipt_order(members)
    return ok


def _check_receipt_premise(members: list[dict]) -> bool:
    """Check the per-station-month receipt-order premise for tied group members.

    V17-02 / F10 fix: Now uses the shared implementation from tie_resolution.py
    to ensure validator and runtime use identical logic.

    Premise holds iff:
    - All members have type(x) is int for receipt_seq (bool rejected)
    - All members share the same receipt_stream
    - Sorting by receipt_seq yields non-decreasing issued_at

    This is intentionally redundant with compile_afos_taf_stream's own premise gate
    as defense in depth.
    """
    ok, _ = _shared_check_receipt_premise(members)
    return ok


def check_latest_issuance_uniqueness(packages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Check that latest_issuance per (station, valid_start, valid_end) has unique semantics.

    Critical design: tie *detection* is computed independently of any resolution/tie-break
    logic, so a conflict can never silently vanish from the report just because it happened
    to become resolvable.

    Returns (conflicts, resolved) where:
    - conflicts: list of residual conflict dicts (unresolved ties) with 'reason' field
    - resolved: list of resolved tie dicts with 'winner_source_id' and 'rule' fields
    """
    conflicts = []
    resolved = []

    # Group by (station, valid_start, valid_end)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for pkg in packages:
        key = (pkg["station"], pkg["valid_start"], pkg["valid_end"])
        groups[key].append(pkg)

    for key, group in groups.items():
        if len(group) < 2:
            continue

        # Step 1: Detect ties INDEPENDENTLY of resolution logic
        # Find max issued_at directly
        max_issued = max(p["issued_at"] for p in group)
        latest_rows = [p for p in group if p["issued_at"] == max_issued]

        if len(latest_rows) < 2:
            # No tie at max issued_at
            continue

        # Check if all latest have the same native_semantics_sha256
        hashes = {p["native_semantics_sha256"] for p in latest_rows}
        if len(hashes) == 1:
            # Same hash = not a genuine conflict (literal duplicates), skip silently
            continue

        # We have a genuine tie: multiple latest with different hashes
        # Now attempt resolution

        # Step 2: Check premise for receipt-order resolution
        premise_ok = _check_receipt_premise(latest_rows)

        if not premise_ok:
            # Check why premise failed
            has_any_seq = any(type(p.get("receipt_seq")) is int for p in latest_rows)
            if not has_any_seq:
                reason = "no_receipt_signal"
            else:
                reason = "premise_violated"

            conflicts.append({
                "group_key": key,
                "latest_count": len(latest_rows),
                "distinct_hashes": len(hashes),
                "issued_at": latest_rows[0]["issued_at"],
                "source_ids": [p["source_id"] for p in latest_rows],
                "reason": reason,
            })
            continue

        # Step 3: Check BBB order vs receipt order
        bbb_agrees = _check_bbb_order_vs_receipt_order(latest_rows)

        if not bbb_agrees:
            conflicts.append({
                "group_key": key,
                "latest_count": len(latest_rows),
                "distinct_hashes": len(hashes),
                "issued_at": latest_rows[0]["issued_at"],
                "source_ids": [p["source_id"] for p in latest_rows],
                "reason": "bbb_contradicts_receipt_order",
            })
            continue

        # Step 4: Attempt resolution via resolve_receipt_tie (imported from versions.py)
        winner = resolve_receipt_tie(latest_rows)

        if winner is None:
            # Should not happen if premise_ok is True, but defensive
            conflicts.append({
                "group_key": key,
                "latest_count": len(latest_rows),
                "distinct_hashes": len(hashes),
                "issued_at": latest_rows[0]["issued_at"],
                "source_ids": [p["source_id"] for p in latest_rows],
                "reason": "no_receipt_signal",
            })
            continue

        # Resolution successful
        # Determine rule based on whether BBB provided cross-validation
        # (check if any same-family pairs existed)
        has_same_family_pairs = False
        by_family = defaultdict(list)
        for m in latest_rows:
            family = _get_bbb_family(m.get("wmo_bbb"))
            if family:
                by_family[family].append(m)
        for family_members in by_family.values():
            if len(family_members) >= 2:
                has_same_family_pairs = True
                break

        rule = "receipt_order+bbb_agree" if has_same_family_pairs else "receipt_order"

        resolved.append({
            "group_key": key,
            "members": [
                {
                    "source_id": p["source_id"],
                    "wmo_bbb": p.get("wmo_bbb"),
                    "amendment_kind": p.get("amendment_kind"),
                    "receipt_seq": p.get("receipt_seq"),
                    "hash_prefix": p["native_semantics_sha256"][:12],
                }
                for p in latest_rows
            ],
            "winner_source_id": winner["source_id"],
            "rule": rule,
        })

    return conflicts, resolved


def cross_check_timestamps(
    packages: list[dict], csv_product_ids: set[str]
) -> dict:
    """Cross-check issued_at timestamps against CSV product_id prefixes.

    Returns a dict with:
    - in_raw_not_csv: timestamps in compiled but not in CSV
    - in_csv_not_raw: timestamps in CSV but not in compiled
    """
    # Extract YYYYMMDDHHmm from compiled packages
    raw_timestamps = set()
    for pkg in packages:
        ts = issued_at_to_yyyymmddhhmm(pkg["issued_at"])
        raw_timestamps.add(ts)

    # Extract YYYYMMDDHHmm from CSV product_ids
    csv_timestamps = set()
    for pid in csv_product_ids:
        ts = extract_issued_yyyymmddhhmm(pid)
        if ts:
            csv_timestamps.add(ts)

    return {
        "in_raw_not_csv": sorted(raw_timestamps - csv_timestamps),
        "in_csv_not_raw": sorted(csv_timestamps - raw_timestamps),
        "raw_count": len(raw_timestamps),
        "csv_count": len(csv_timestamps),
    }


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
        "--csv-dir",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/"
            "20260920T091835Z_5f8988c0e49a"
        ),
        help="Path to CSV batch directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "/mnt/afs/260010168/extreme_weather_benchmark/development/"
            "v14_revision_20260919_01/DL3R_SEMANTIC_VALIDATION_v16r2.md"
        ),
        help="Output report path",
    )
    parser.add_argument(
        "--expected-skips",
        type=int,
        default=0,
        help="Expected number of skipped frames (exact match required for non-blocking)",
    )
    args = parser.parse_args()

    bulk_dir = args.bulk_dir.resolve()
    csv_dir = args.csv_dir.resolve()
    out_path = args.out.resolve()
    expected_skips = args.expected_skips

    # ==========================================================================
    # HARD GATE: Check file presence and integrity
    # ==========================================================================

    gate_failures = []

    # Check for quarantine_holdout in paths (D09 compliance)
    for p in [bulk_dir, csv_dir, out_path]:
        if "quarantine_holdout" in str(p):
            print(f"ERROR: Path contains quarantine_holdout: {p}", file=sys.stderr)
            sys.exit(2)

    # Check reconciliation file
    reconciliation_path = bulk_dir / "RECONCILIATION_DL3R.md"
    if not reconciliation_path.exists():
        gate_failures.append(f"Missing: {reconciliation_path}")

    # Check all 140 expected body + json pairs
    missing_body = []
    missing_json = []
    sha256_mismatches = []

    for station, year_month in EXPECTED_FILES:
        body_file = bulk_dir / f"{station}_{year_month}.body"
        json_file = bulk_dir / f"{station}_{year_month}.json"

        if not body_file.exists():
            missing_body.append(f"{station}_{year_month}.body")
        if not json_file.exists():
            missing_json.append(f"{station}_{year_month}.json")

        if body_file.exists() and json_file.exists():
            # Verify SHA256
            with open(json_file, "r") as f:
                receipt = json.load(f)
            expected_sha = receipt.get("sha256", "")
            actual_sha = sha256_file(body_file)
            if expected_sha != actual_sha:
                sha256_mismatches.append({
                    "file": f"{station}_{year_month}.body",
                    "expected": expected_sha,
                    "actual": actual_sha,
                })

    if missing_body:
        gate_failures.extend([f"Missing body: {f}" for f in missing_body])
    if missing_json:
        gate_failures.extend([f"Missing json: {f}" for f in missing_json])
    if sha256_mismatches:
        gate_failures.extend([
            f"SHA256 mismatch: {m['file']} (expected {m['expected'][:16]}..., "
            f"actual {m['actual'][:16]}...)"
            for m in sha256_mismatches
        ])

    # Check that 202502 is NOT in our working list
    for station, year_month in EXPECTED_FILES:
        if year_month == "202502":
            gate_failures.append(f"202502 should not be in expected files: {station}")

    # List unexpected files in bulk directory
    expected_filenames = set()
    for station, year_month in EXPECTED_FILES:
        expected_filenames.add(f"{station}_{year_month}.body")
        expected_filenames.add(f"{station}_{year_month}.json")
    expected_filenames.add("RECONCILIATION_DL3R.md")
    # Also allow known metadata files
    expected_filenames.add("MANIFEST.json")
    expected_filenames.add("download_summary.json")
    expected_filenames.add("reconciliation_data.json")
    expected_filenames.add("dl3r_structural_anomalies.jsonl")

    unexpected_files = []
    for f in bulk_dir.iterdir():
        if f.name not in expected_filenames:
            unexpected_files.append(f.name)

    # Gate failure if critical items missing
    if gate_failures:
        print("HARD GATE FAILURE - Missing required files:", file=sys.stderr)
        for failure in gate_failures:
            print(f"  - {failure}", file=sys.stderr)
        sys.exit(2)

    print(f"Hard gate passed: 140 body files, 140 json files, RECONCILIATION_DL3R.md")
    if unexpected_files:
        print(f"  Unexpected files found (will be listed in report): {len(unexpected_files)}")

    # ==========================================================================
    # PARSE RECONCILIATION TABLE
    # ==========================================================================

    reconciliation = parse_reconciliation_table(reconciliation_path)
    print(f"Parsed reconciliation table: {len(reconciliation)} rows")

    # ==========================================================================
    # COMPILE AND VALIDATE EACH STATION-MONTH
    # ==========================================================================

    all_results = []
    total_skipped = 0
    total_packages = 0
    total_wmo_bbb_violations = []
    total_rrx_recognized = []
    total_latest_conflicts = []
    total_latest_resolved = []
    total_nil_cnl_count = 0
    total_timestamp_issues = []

    for station, year_month in EXPECTED_FILES:
        body_file = bulk_dir / f"{station}_{year_month}.body"
        json_file = bulk_dir / f"{station}_{year_month}.json"

        # Read receipt
        with open(json_file, "r") as f:
            receipt = json.load(f)

        # Read raw text
        with open(body_file, "r", errors="replace") as f:
            raw_text = f.read()

        # Count frames
        soh_count, etx_count = count_soh_etx(raw_text)
        receipt_frame_count = receipt.get("frame_count_etx", -1)

        # Compile using episode_compiler
        reference_month = f"{year_month[:4]}-{year_month[4:6]}"
        packages, skipped = compile_afos_taf_stream(
            raw_text,
            station=station,
            reference_month=reference_month,
        )

        total_skipped += len(skipped)
        total_packages += len(packages)

        # Count by error class
        skip_by_class = defaultdict(int)
        for s in skipped:
            error = s.get("error", "unknown")
            # Categorize error
            if "wmo_day_outside_reference_month" in error:
                skip_by_class["day_outside_month"] += 1
            elif "WMO header" in error:
                skip_by_class["wmo_header_missing"] += 1
            elif "TAF content not found" in error:
                skip_by_class["taf_content_missing"] += 1
            else:
                skip_by_class["other"] += 1

        # Amendment kind distribution
        amendment_dist = defaultdict(int)
        for pkg in packages:
            amendment_dist[pkg.get("amendment_kind", "unknown")] += 1

        # Status distribution
        status_dist = defaultdict(int)
        for pkg in packages:
            status_dist[pkg.get("status", "unknown")] += 1
            if pkg.get("status") in ("nil", "canceled"):
                total_nil_cnl_count += 1

        # Count duplicate (issued_at, native_semantics_sha256) pairs
        seen_pairs = defaultdict(int)
        for pkg in packages:
            pair = (pkg["issued_at"], pkg["native_semantics_sha256"])
            seen_pairs[pair] += 1
        duplicate_count = sum(1 for c in seen_pairs.values() if c > 1)

        # Check wmo_bbb consistency (now returns violations and rrx_recognized)
        wmo_violations, rrx_recognized = validate_wmo_bbb_consistency(packages)
        if wmo_violations:
            for v in wmo_violations:
                v["station"] = station
                v["year_month"] = year_month
            total_wmo_bbb_violations.extend(wmo_violations)
        if rrx_recognized:
            for r in rrx_recognized:
                r["station"] = station
                r["year_month"] = year_month
            total_rrx_recognized.extend(rrx_recognized)

        # Check latest_issuance uniqueness (now returns conflicts and resolved)
        latest_conflicts, latest_resolved = check_latest_issuance_uniqueness(packages)
        if latest_conflicts:
            for c in latest_conflicts:
                c["station"] = station
                c["year_month"] = year_month
            total_latest_conflicts.extend(latest_conflicts)
        if latest_resolved:
            for r in latest_resolved:
                r["station"] = station
                r["year_month"] = year_month
            total_latest_resolved.extend(latest_resolved)

        # Get CSV product_ids for cross-check
        csv_file = csv_dir / f"{station}_{year_month}.body"
        if csv_file.exists():
            csv_product_ids = extract_csv_product_ids(csv_file)
        else:
            csv_product_ids = set()

        timestamp_check = cross_check_timestamps(packages, csv_product_ids)
        if timestamp_check["in_raw_not_csv"] or timestamp_check["in_csv_not_raw"]:
            total_timestamp_issues.append({
                "station": station,
                "year_month": year_month,
                **timestamp_check,
            })

        # Get reconciliation row
        recon_row = reconciliation.get((station, year_month), {})

        # Determine per-row verdict
        row_verdict = "OK"
        if skipped:
            row_verdict = "SKIP"
        if wmo_violations:
            row_verdict = "BBB_MISMATCH"
        if latest_resolved:
            row_verdict = "TIE_RESOLVED"
        if latest_conflicts:
            row_verdict = "CONFLICT"
        if etx_count != recon_row.get("raw_frame_count", etx_count):
            row_verdict = "FRAME_MISMATCH"

        result = {
            "station": station,
            "year_month": year_month,
            "our_frame_count_soh": soh_count,
            "our_frame_count_etx": etx_count,
            "receipt_frame_count": receipt_frame_count,
            "compiled_count": len(packages),
            "skip_count": len(skipped),
            "skip_by_class": dict(skip_by_class),
            "amendment_dist": dict(amendment_dist),
            "status_dist": dict(status_dist),
            "duplicate_pair_count": duplicate_count,
            "csv_product_id_count": len(csv_product_ids),
            "recon_csv_count": recon_row.get("csv_product_id_count", -1),
            "recon_raw_count": recon_row.get("raw_frame_count", -1),
            "recon_backfill": recon_row.get("backfill_count", 0),
            "recon_notes": recon_row.get("notes", "-"),
            "wmo_violations": len(wmo_violations),
            "rrx_recognized": len(rrx_recognized),
            "latest_conflicts": len(latest_conflicts),
            "latest_resolved": len(latest_resolved),
            "verdict": row_verdict,
        }
        all_results.append(result)

    # ==========================================================================
    # GENERATE REPORT
    # ==========================================================================

    lines = []
    lines.append("# DL-3R Semantic Validation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Bulk directory: `{bulk_dir}`")
    lines.append(f"CSV directory: `{csv_dir}`")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total station-months validated: {len(all_results)}")
    lines.append(f"- Total compiled packages: {total_packages}")
    lines.append(f"- Total skipped frames: {total_skipped}")
    lines.append(f"- Total wmo_bbb/amendment_kind violations: {len(total_wmo_bbb_violations)}")
    lines.append(f"- Total RRx recognized: {len(total_rrx_recognized)}")
    lines.append(f"- Total ties resolved: {len(total_latest_resolved)}")
    lines.append(f"- Total residual conflicts (unresolved): {len(total_latest_conflicts)}")
    lines.append(f"- Total NIL/CNL status records: {total_nil_cnl_count}")
    lines.append(f"- Station-months with timestamp issues: {len(total_timestamp_issues)}")
    lines.append("")

    # Skip handling notice
    if total_skipped > 0:
        if total_skipped == expected_skips:
            lines.append(f"**NOTE**: {total_skipped} skipped frames match --expected-skips={expected_skips} "
                        f"(explicitly confirmed non-blocking).")
        else:
            lines.append(f"**WARNING**: {total_skipped} skipped frames does NOT match --expected-skips={expected_skips}.")
        lines.append("")

    if unexpected_files:
        lines.append("## Unexpected Files in Bulk Directory")
        lines.append("")
        for f in sorted(unexpected_files):
            lines.append(f"- `{f}`")
        lines.append("")

    # 140-row detail table with new columns
    lines.append("## 140-Row Detail Table")
    lines.append("")
    lines.append("| Station | Year-Month | ETX | Receipt | Compiled | Skipped | "
                "AMD | COR | orig | Dup | RRx | TiesResolved | CSV IDs | Recon CSV | Recon Raw | "
                "Backfill | Notes | Verdict |")
    lines.append("|---------|------------|-----|---------|----------|---------|"
                "-----|-----|------|-----|-----|--------------|---------|-----------|-----------|"
                "----------|-------|---------|")

    for r in all_results:
        amd_count = r["amendment_dist"].get("AMD", 0)
        cor_count = r["amendment_dist"].get("COR", 0)
        orig_count = r["amendment_dist"].get("original", 0)

        lines.append(
            f"| {r['station']} | {r['year_month']} | {r['our_frame_count_etx']} | "
            f"{r['receipt_frame_count']} | {r['compiled_count']} | {r['skip_count']} | "
            f"{amd_count} | {cor_count} | {orig_count} | {r['duplicate_pair_count']} | "
            f"{r['rrx_recognized']} | {r['latest_resolved']} | "
            f"{r['csv_product_id_count']} | {r['recon_csv_count']} | {r['recon_raw_count']} | "
            f"{r['recon_backfill']} | {r['recon_notes']} | {r['verdict']} |"
        )

    lines.append("")

    # Check (i): Amendment extraction
    lines.append("## Semantic Check (i): Amendment Extraction")
    lines.append("")

    if total_skipped == 0:
        lines.append("**PASS**: Zero frames skipped across all 140 files.")
    else:
        lines.append(f"**FINDING**: {total_skipped} total frames skipped.")
        lines.append("")
        lines.append("Skip breakdown by station-month:")
        for r in all_results:
            if r["skip_count"] > 0:
                lines.append(f"- {r['station']} {r['year_month']}: {r['skip_count']} skipped - {r['skip_by_class']}")
    lines.append("")

    if not total_wmo_bbb_violations:
        lines.append("**PASS**: wmo_bbb <-> amendment_kind consistency verified for all packages.")
    else:
        lines.append(f"**FINDING**: {len(total_wmo_bbb_violations)} wmo_bbb/amendment_kind mismatches:")
        # Full listing, no truncation
        for v in total_wmo_bbb_violations:
            lines.append(f"- {v['station']} {v['year_month']}: {v}")
    lines.append("")

    # RRx recognized section
    lines.append("### RRx Recognized")
    lines.append("")
    if total_rrx_recognized:
        lines.append(f"**INFO**: {len(total_rrx_recognized)} packages with RRx (delayed routine) codes correctly recognized:")
        # Full listing
        for r in total_rrx_recognized:
            lines.append(f"- {r['station']} {r['year_month']}: source_id={r['source_id']}, "
                        f"wmo_bbb={r['wmo_bbb']}, amendment_kind={r['amendment_kind']}")
    else:
        lines.append("No RRx codes found in archive.")
    lines.append("")

    # Check (ii): NIL/CNL handling
    lines.append("## Semantic Check (ii): NIL/CNL Handling")
    lines.append("")

    if total_nil_cnl_count == 0:
        lines.append("**FINDING**: Zero compiled packages have NIL or canceled status in the real DL-3R data.")
        lines.append("This path is exercised only by unit tests, not by real DL-3R data.")
    else:
        lines.append(f"**FINDING**: {total_nil_cnl_count} packages with NIL/canceled status found:")
        for r in all_results:
            nil_count = r["status_dist"].get("nil", 0)
            cnl_count = r["status_dist"].get("canceled", 0)
            if nil_count > 0 or cnl_count > 0:
                lines.append(f"- {r['station']} {r['year_month']}: nil={nil_count}, canceled={cnl_count}")
    lines.append("")

    # Check (iii): latest_issuance uniqueness
    lines.append("## Semantic Check (iii): latest_issuance Uniqueness")
    lines.append("")

    # Resolved ties section
    lines.append("### Resolved Ties")
    lines.append("")
    if total_latest_resolved:
        lines.append(f"**INFO**: {len(total_latest_resolved)} ties resolved via receipt-order:")
        # Full listing, no truncation
        for r in total_latest_resolved:
            lines.append(f"- {r['station']} {r['year_month']}: group {r['group_key']}")
            lines.append(f"  - Winner: {r['winner_source_id']} (rule: {r['rule']})")
            lines.append(f"  - Members:")
            for m in r["members"]:
                lines.append(f"    - {m['source_id']}: wmo_bbb={m['wmo_bbb']}, "
                            f"kind={m['amendment_kind']}, seq={m['receipt_seq']}, hash={m['hash_prefix']}")
    else:
        lines.append("No ties to resolve.")
    lines.append("")

    # Residual conflicts section
    lines.append("### Residual Conflicts (Unresolved)")
    lines.append("")
    if not total_latest_conflicts:
        lines.append("**PASS**: All (station, valid_start, valid_end) groups have unique semantics in their latest issuance set.")
    else:
        lines.append(f"**FINDING**: {len(total_latest_conflicts)} residual conflicts found:")
        # Full listing, no truncation
        for c in total_latest_conflicts:
            lines.append(f"- {c['station']} {c['year_month']}: group {c.get('group_key', 'N/A')}, "
                        f"{c.get('latest_count', 'N/A')} latest with {c.get('distinct_hashes', 'N/A')} distinct hashes, "
                        f"reason: {c.get('reason', 'unknown')}")
    lines.append("")

    # Check (iv): Cross-check timestamps
    lines.append("## Semantic Check (iv): Timestamp Cross-Check vs CSV")
    lines.append("")

    if not total_timestamp_issues:
        lines.append("**PASS**: All issued_at timestamps match CSV product_id prefixes.")
    else:
        lines.append(f"**FINDING**: {len(total_timestamp_issues)} station-months have timestamp differences:")
        lines.append("")
        for issue in total_timestamp_issues:
            lines.append(f"### {issue['station']} {issue['year_month']}")
            lines.append(f"- Raw timestamp count: {issue['raw_count']}")
            lines.append(f"- CSV timestamp count: {issue['csv_count']}")
            if issue["in_raw_not_csv"]:
                lines.append(f"- In raw not CSV ({len(issue['in_raw_not_csv'])}): {issue['in_raw_not_csv'][:10]}{'...' if len(issue['in_raw_not_csv']) > 10 else ''}")
            if issue["in_csv_not_raw"]:
                lines.append(f"- In CSV not raw ({len(issue['in_csv_not_raw'])}): {issue['in_csv_not_raw'][:10]}{'...' if len(issue['in_csv_not_raw']) > 10 else ''}")
            lines.append("")
    lines.append("")

    # Backfill section
    lines.append("## Backfill Directories (Informational)")
    lines.append("")
    backfill_dir = bulk_dir.parent / (bulk_dir.name + "_backfill")
    backfill_retry_dir = bulk_dir.parent / (bulk_dir.name + "_backfill_retry1")

    if backfill_dir.exists():
        backfill_files = list(backfill_dir.glob("backfill_*.body"))
        lines.append(f"### Backfill directory: `{backfill_dir.name}`")
        lines.append(f"- Contains {len(backfill_files)} .body files")
        lines.append("- File format: `backfill_{STATION}_{YYYYMM}_{N}.body` (per-product_id fragments)")
        lines.append("- These are NOT full station-month files; each contains a single TAF frame")
        lines.append("- Sample filenames:")
        for bf in sorted(backfill_files)[:5]:
            lines.append(f"  - `{bf.name}`")
        lines.append("")

    if backfill_retry_dir.exists():
        retry_files = list(backfill_retry_dir.glob("retry_*.body"))
        lines.append(f"### Backfill retry directory: `{backfill_retry_dir.name}`")
        lines.append(f"- Contains {len(retry_files)} .body files")
        lines.append("- File format: `retry_{N}.body` (individual retry fragments)")
        lines.append("")

    # Overall verdict
    lines.append("## Overall Verdict")
    lines.append("")

    # Exit conditions: wmo_bbb violations, residual conflicts, frame mismatches all block
    # Skips block only if total_skipped != expected_skips
    skips_blocking = (total_skipped != expected_skips)

    has_issues = (
        skips_blocking or
        total_wmo_bbb_violations or
        total_latest_conflicts or
        any(r["verdict"] == "FRAME_MISMATCH" for r in all_results)
    )

    if has_issues:
        reasons = []
        if skips_blocking:
            reasons.append(f"skipped frames ({total_skipped}) != expected ({expected_skips})")
        if total_wmo_bbb_violations:
            reasons.append(f"{len(total_wmo_bbb_violations)} wmo_bbb violations")
        if total_latest_conflicts:
            reasons.append(f"{len(total_latest_conflicts)} residual conflicts")
        if any(r["verdict"] == "FRAME_MISMATCH" for r in all_results):
            reasons.append("frame count mismatches")
        lines.append(f"**EXIT 1**: Semantic issues found: {', '.join(reasons)}.")
        exit_code = 1
    else:
        lines.append("**EXIT 0**: All semantic checks passed.")
        if total_skipped > 0:
            lines.append(f"  - {total_skipped} skipped frames explicitly confirmed via --expected-skips={expected_skips}")
        if total_latest_resolved:
            lines.append(f"  - {len(total_latest_resolved)} ties resolved via receipt-order")
        if total_rrx_recognized:
            lines.append(f"  - {len(total_rrx_recognized)} RRx codes recognized")
        exit_code = 0

    # Write report
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Report written to: {out_path}")
    print(f"Exit code: {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
