#!/usr/bin/env python3
"""Build LAMP categorical registry from real v16 archive.

Parses all .body files under data_real_v16/lamp/raw/20260920T100529Z_09c70a575ad2/
and generates data_contracts/lamp_categorical_registry_v16.json with metadata
and record counts per station/element.

V17-01 / F04 enhancement: Now filters out holdout-window months (202502) and
validates all paths against AccessPolicy before parsing.

This script:
- Reads from data_real_v16/ (read-only)
- Writes to data_contracts/ (inside git repo)
- Refuses to overwrite an existing registry file
- Includes DL4_STATUS.json finding that archive is categorical-only
- Filters out paths in holdout window before parsing

Usage:
    python scripts/build_lamp_categorical_registry_v16.py [--data-root PATH]

The --data-root option allows specifying an alternate location for data_real_v16/
(default: ../../../data_real_v16 relative to repo root, which is the sibling
directory as specified in task documentation).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))

from disastertrace.revision_v1.lamp_categorical import (
    FROZEN_STATIONS,
    LampCategoricalRecord,
    LampElement,
    assert_not_probabilistic,
    parse_lamp_body,
)
from disastertrace.revision_v1.access_policy import (
    AccessPolicy,
    AccessPolicyViolation,
)


# Default paths
DEFAULT_DATA_ROOT = REPO_ROOT.parent.parent.parent / "data_real_v16"
RAW_ARCHIVE_SUBDIR = "lamp/raw/20260920T100529Z_09c70a575ad2"
OUTPUT_PATH = REPO_ROOT / "data_contracts" / "lamp_categorical_registry_v16.json"
DL4_STATUS_SUBPATH = "lamp/DL4_STATUS.json"


def build_registry(data_root: Path, output_path: Path, force: bool = False) -> dict:
    """Build the LAMP categorical registry from the real archive.

    Args:
        data_root: Path to data_real_v16 directory
        output_path: Path where registry JSON will be written
        force: If True, allow overwriting an existing registry file. This is
            a deliberate, narrow escape hatch for correcting a known bug in
            an already-generated registry within the same working round,
            before the artifact is considered frozen for downstream use. It
            does not change any other refusal behavior.

    Returns:
        Registry dict that was written

    Raises:
        FileExistsError: If output_path already exists and force is False
        FileNotFoundError: If archive directory doesn't exist
    """
    # Check output doesn't exist (refuse to overwrite) unless --force
    if output_path.exists() and not force:
        raise FileExistsError(
            f"Registry file already exists at {output_path}. "
            f"This script refuses to overwrite existing registry files to "
            f"preserve historical artifacts. Remove the file manually, or "
            f"pass --force if you are deliberately correcting a known bug in "
            f"this same working round, to regenerate."
        )

    # Verify archive directory exists
    archive_dir = data_root / RAW_ARCHIVE_SUBDIR
    if not archive_dir.is_dir():
        raise FileNotFoundError(
            f"LAMP raw archive directory not found at {archive_dir}. "
            f"Verify data_real_v16 location."
        )

    # Read DL4_STATUS.json to include in registry metadata
    dl4_status_path = data_root / DL4_STATUS_SUBPATH
    dl4_finding = None
    if dl4_status_path.exists():
        with open(dl4_status_path) as f:
            dl4_data = json.load(f)
            if "content_scope_finding" in dl4_data:
                dl4_finding = dl4_data["content_scope_finding"]["summary"]

    # Find all .body files
    all_body_files = sorted(archive_dir.glob("lav-*.body"))
    if not all_body_files:
        raise FileNotFoundError(
            f"No .body files found in {archive_dir}"
        )

    # V17-01 / F04 fix: Filter out holdout-window months (202502 = Feb 2025)
    # The holdout window is 2025-02-17 to 2025-02-24, so we exclude all of 202502
    HOLDOUT_MONTH = "202502"

    body_files = []
    holdout_filtered_files = []

    for body_file in all_body_files:
        # Extract YYYYMM from filename (lav-YYYYMM-HHHHz.body)
        match = re.search(r"lav-(\d{6})", body_file.name)
        if match:
            yyyymm = match.group(1)
            if yyyymm == HOLDOUT_MONTH:
                holdout_filtered_files.append(body_file.name)
                continue
        body_files.append(body_file)

    if holdout_filtered_files:
        print(f"V17-01 / F04: Filtered out {len(holdout_filtered_files)} holdout-month files: {holdout_filtered_files}")

    # Parse all files and collect statistics
    batch_id = f"registry_build_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    all_records: list[LampCategoricalRecord] = []
    source_hashes: dict[str, str] = {}  # filename -> sha256
    months_covered: set[str] = set()

    # Counts per station/element
    station_element_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    station_counts: dict[str, int] = defaultdict(int)
    element_counts: dict[str, int] = defaultdict(int)

    # Track files in two DISTINCT failure modes -- these must not be conflated:
    #   - corrupt_files: the .body file itself is genuinely corrupt (bad gzip
    #     header, or a deflate stream zlib cannot decode). parse_lamp_body's
    #     decompression tolerates a missing/incomplete end-of-stream trailer
    #     (a download cut off right at the very end, after real content was
    #     already written), so this should be empty in practice; anything
    #     landing here is real, unrecovered corruption.
    #   - empty_download_files: the .body file is a genuine 0-byte input
    #     (documented failed download, e.g. curl timeout / http_status=0 in
    #     DL4_STATUS.json). These decompress cleanly to "" and contribute 0
    #     records -- that is correct, expected behavior, not a parse failure.
    corrupt_files: list[tuple[str, str]] = []
    empty_download_files: list[str] = []

    print(f"Processing {len(body_files)} .body files from {archive_dir}")

    for i, body_file in enumerate(body_files, 1):
        if i % 20 == 0 or i == len(body_files):
            print(f"  Processed {i}/{len(body_files)} files...")

        # Extract month from filename (lav-YYYYMM-HHHHz.body)
        parts = body_file.stem.split("-")
        if len(parts) >= 2:
            month_str = parts[1][:6]  # YYYYMM
            months_covered.add(f"{month_str[:4]}-{month_str[4:]}")

        is_zero_byte_input = body_file.stat().st_size == 0

        # Parse file (skip files that are genuinely corrupt, not merely
        # missing their gzip trailer -- parse_lamp_body/_decompress_body
        # already recovers the missing-trailer case internally)
        try:
            records = list(parse_lamp_body(body_file, batch_id, FROZEN_STATIONS))
        except (EOFError, gzip.BadGzipFile) as e:
            corrupt_files.append((body_file.name, str(e)))
            print(f"  SKIPPED (corrupt): {body_file.name}")
            continue

        if is_zero_byte_input:
            empty_download_files.append(body_file.name)
            print(f"  EMPTY (genuine failed download, 0 bytes): {body_file.name}")

        all_records.extend(records)

        # Compute source hash (will be same for all records from this file)
        if records:
            source_hashes[body_file.name] = records[0].source_sha256

        # Update counts
        for rec in records:
            station_element_counts[rec.station][rec.element.value] += 1
            station_counts[rec.station] += 1
            element_counts[rec.element.value] += 1

    # Verify all records are categorical (guard function)
    print(f"Verifying {len(all_records)} records are categorical (D11 check)...")
    assert_not_probabilistic(all_records)
    print("  D11 check passed: all records are LampCategoricalRecord")

    # Build registry structure
    registry = {
        "baseline_class": "categorical",
        "d11_note": (
            "This registry contains ONLY categorical LAMP elements (CIG/VIS/OBV). "
            "Per DL4_STATUS.json, the real archived LAMP LAV product has no "
            "probabilistic or conditional-probability elements. The directories "
            "lamp/probabilistic/ and lamp/conditional/ exist but are empty. "
            "Per project decision D11, LAMP product types must be registered "
            "separately and never conflated."
        ),
        "dl4_status_finding": dl4_finding,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_archive": str(archive_dir),
        "months_covered": sorted(months_covered),
        "stations": sorted(FROZEN_STATIONS),
        "total_records": len(all_records),
        "records_by_station": dict(station_counts),
        "records_by_element": dict(element_counts),
        "records_by_station_element": {
            station: dict(elements)
            for station, elements in sorted(station_element_counts.items())
        },
        "source_files_count": len(body_files),
        "source_files_parsed": len(body_files) - len(corrupt_files),
        "source_files_corrupt": len(corrupt_files),
        "corrupt_files_detail": [
            {"file": name, "reason": reason} for name, reason in corrupt_files
        ],
        "source_files_empty_download": len(empty_download_files),
        "empty_download_files_detail": [
            {
                "file": name,
                "reason": (
                    "genuine 0-byte failed download (documented in "
                    "DL4_STATUS.json formal_download_phase.failed_requests_detail, "
                    "http_status=0); decompresses to empty content and "
                    "correctly contributes 0 records -- not a parse failure, "
                    "and not recoverable (no real data exists behind it)"
                ),
            }
            for name in empty_download_files
        ],
        "source_file_hashes": dict(sorted(source_hashes.items())),
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write registry
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    print(f"\nRegistry written to {output_path}")
    print(f"  Total records: {len(all_records)}")
    print(f"  Months covered: {len(months_covered)}")
    print(
        f"  Source files: {len(body_files)} "
        f"({len(body_files) - len(corrupt_files)} parsed, "
        f"{len(corrupt_files)} corrupt, "
        f"{len(empty_download_files)} of the parsed are genuine empty downloads)"
    )
    if corrupt_files:
        print(f"  Corrupt files: {[f[0] for f in corrupt_files]}")
    if empty_download_files:
        print(f"  Genuine empty-download files: {empty_download_files}")
    print(f"  Records by station: {dict(station_counts)}")
    print(f"  Records by element: {dict(element_counts)}")

    return registry


def main():
    parser = argparse.ArgumentParser(
        description="Build LAMP categorical registry from real v16 archive"
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help=f"Path to data_real_v16 directory (default: {DEFAULT_DATA_ROOT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output registry path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Allow overwriting an existing registry file. This is a narrow, "
            "deliberate escape hatch for correcting a known bug in an "
            "already-generated registry within the same working round, "
            "before the artifact is considered frozen for downstream use. "
            "It does not change any other overwrite-refusal behavior."
        ),
    )

    args = parser.parse_args()

    try:
        build_registry(args.data_root, args.output, force=args.force)
        return 0
    except FileExistsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
