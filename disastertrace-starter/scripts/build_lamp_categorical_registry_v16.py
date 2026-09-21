#!/usr/bin/env python3
"""Build LAMP categorical registry from real v16 archive.

Parses all .body files under data_real_v16/lamp/raw/20260920T100529Z_09c70a575ad2/
and generates data_contracts/lamp_categorical_registry_v16.json with metadata
and record counts per station/element.

This script:
- Reads from data_real_v16/ (read-only)
- Writes to data_contracts/ (inside git repo)
- Refuses to overwrite an existing registry file
- Includes DL4_STATUS.json finding that archive is categorical-only

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


# Default paths
DEFAULT_DATA_ROOT = REPO_ROOT.parent.parent.parent / "data_real_v16"
RAW_ARCHIVE_SUBDIR = "lamp/raw/20260920T100529Z_09c70a575ad2"
OUTPUT_PATH = REPO_ROOT / "data_contracts" / "lamp_categorical_registry_v16.json"
DL4_STATUS_SUBPATH = "lamp/DL4_STATUS.json"


def build_registry(data_root: Path, output_path: Path) -> dict:
    """Build the LAMP categorical registry from the real archive.

    Args:
        data_root: Path to data_real_v16 directory
        output_path: Path where registry JSON will be written

    Returns:
        Registry dict that was written

    Raises:
        FileExistsError: If output_path already exists
        FileNotFoundError: If archive directory doesn't exist
    """
    # Check output doesn't exist (refuse to overwrite)
    if output_path.exists():
        raise FileExistsError(
            f"Registry file already exists at {output_path}. "
            f"This script refuses to overwrite existing registry files to "
            f"preserve historical artifacts. Remove the file manually if you "
            f"need to regenerate."
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
    body_files = sorted(archive_dir.glob("lav-*.body"))
    if not body_files:
        raise FileNotFoundError(
            f"No .body files found in {archive_dir}"
        )

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

    # Track skipped files (corrupt/truncated from failed downloads)
    skipped_files: list[tuple[str, str]] = []

    print(f"Processing {len(body_files)} .body files from {archive_dir}")

    for i, body_file in enumerate(body_files, 1):
        if i % 20 == 0 or i == len(body_files):
            print(f"  Processed {i}/{len(body_files)} files...")

        # Extract month from filename (lav-YYYYMM-HHHHz.body)
        parts = body_file.stem.split("-")
        if len(parts) >= 2:
            month_str = parts[1][:6]  # YYYYMM
            months_covered.add(f"{month_str[:4]}-{month_str[4:]}")

        # Parse file (skip corrupt/truncated files from failed downloads)
        try:
            records = list(parse_lamp_body(body_file, batch_id, FROZEN_STATIONS))
        except (EOFError, gzip.BadGzipFile) as e:
            # Skip corrupt files - these are documented failed downloads in DL4_STATUS.json
            skipped_files.append((body_file.name, str(e)))
            print(f"  SKIPPED (corrupt): {body_file.name}")
            continue
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
        "source_files_parsed": len(body_files) - len(skipped_files),
        "source_files_skipped": len(skipped_files),
        "skipped_files_detail": [
            {"file": name, "reason": reason} for name, reason in skipped_files
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
    print(f"  Source files: {len(body_files)} ({len(body_files) - len(skipped_files)} parsed, {len(skipped_files)} skipped)")
    if skipped_files:
        print(f"  Skipped files: {[f[0] for f in skipped_files]}")
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

    args = parser.parse_args()

    try:
        build_registry(args.data_root, args.output)
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
