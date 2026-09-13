"""Compare source-bound native values with the independently maintained python-metar."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "independent_decoder_libs"))
from disastertrace.monitoring_v1.providers.aviation import parse_metar
from disastertrace.monitoring_v1.support import classify
from metar import Metar


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_outcome(visibility, threshold):
    if visibility is None:
        return "undetermined"
    value = visibility.value("M")
    if visibility._gtlt == ">":
        return "refuted" if value >= threshold else "undetermined"
    if visibility._gtlt == "<":
        return "supported" if value <= threshold else "undetermined"
    # This external parser reports the 9999 lower-limit code as a point.
    # It cannot independently check that particular censoring convention.
    if visibility._units == "M" and value in (0, 9999):
        return "not_independently_supported_censoring"
    return "supported" if value < threshold else "refuted"


def main(args):
    args.output.mkdir(exist_ok=False)
    records, bindings, counts = [], [], Counter()
    for directory in args.captures:
        for receipt_path in sorted(directory.glob("metar-routine-*.json")):
            if receipt_path.name.endswith(".intent.json"):
                continue
            receipt = json.loads(receipt_path.read_text())
            path = directory / receipt["body_file"]
            if not receipt.get("complete") or receipt["http_status"] != 200:
                raise ValueError("Incomplete input capture: " + str(path))
            if (
                digest(path) != receipt["sha256"]
                or path.stat().st_size != receipt["bytes"]
            ):
                raise ValueError("Source binding mismatch: " + str(path))
            bindings.append(
                {
                    "path": str(path.resolve()),
                    "sha256": digest(path),
                    "receipt_sha256": digest(receipt_path),
                }
            )
            reader = csv.DictReader(io.StringIO(path.read_text()))
            for source_row in reader:
                row = {"source": str(path.resolve()), "line": reader.line_num}
                counts["reports"] += 1
                try:
                    valid = datetime.strptime(
                        source_row["valid"], "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone.utc)
                    original = parse_metar(
                        source_row["metar"],
                        observation_time=valid.replace(tzinfo=timezone.utc).isoformat(),
                        report_type="routine",
                    )
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        independent = Metar.Metar(
                            source_row["metar"],
                            month=valid.month,
                            year=valid.year,
                            strict=False,
                        )
                    row["unparsed_groups"] = independent._unparsed_groups
                    row["warning_count"] = len(caught)
                    counts["warning_reports"] += bool(caught)
                    row["station_equal"] = independent.station_id == original.station
                    row["time_equal"] = (
                        independent.time.replace(tzinfo=timezone.utc) == valid
                    )
                    row["by_threshold"] = {}
                    for threshold in (1000, 5000):
                        ours = (
                            "undetermined"
                            if original.visibility is None
                            else classify(original.visibility, "lt", threshold)
                        )
                        theirs = native_outcome(independent.vis, threshold)
                        row["by_threshold"][str(threshold)] = {
                            "original": ours,
                            "independent": theirs,
                        }
                    row["matched"] = (
                        row["station_equal"]
                        and row["time_equal"]
                        and all(
                            v["original"] == v["independent"]
                            for v in row["by_threshold"].values()
                        )
                    )
                    counts["matched"] += row["matched"]
                    counts["different"] += not row["matched"]
                except (
                    ValueError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    Metar.ParserError,
                ) as exc:
                    row.update(
                        error=type(exc).__name__ + ": " + str(exc), matched=False
                    )
                    counts["errors"] += 1
                records.append(row)
    output = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "counts": dict(counts),
        "source_bindings": bindings,
        "records": records,
        "external_library": {
            "name": "metar",
            "version": "1.11.0",
            "repository": "https://github.com/python-metar/python-metar",
            "wheel_sha256": digest(
                BASE / "independent_decoder_downloads/metar-1.11.0-py3-none-any.whl"
            ),
            "files": {
                str(p.relative_to(BASE / "independent_decoder_libs")): digest(p)
                for p in (BASE / "independent_decoder_libs/metar").glob("*.py")
            },
        },
        "our_parser_sha256": digest(Path(parse_metar.__code__.co_filename)),
        "validator_sha256": digest(Path(__file__)),
        "scope": "Independent station, native time and threshold-label decoding; not independent original first-seen, physical sensor truth, slot selection or TAF validation; warnings and disagreements retained",
    }
    (args.output / "VERIFIED.json").write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n"
    )
    shutil.copyfile(__file__, args.output / "verify_native_metar.py")
    print(json.dumps(dict(counts)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
