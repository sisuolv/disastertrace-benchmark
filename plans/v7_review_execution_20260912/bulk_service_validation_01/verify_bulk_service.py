"""Verify real batching capability and keep logical archive pricing distinct."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent


def verified(directory, receipt_path):
    receipt = json.loads(receipt_path.read_text())
    path = directory / receipt["body_file"]
    raw = path.read_bytes()
    if (
        not receipt.get("complete")
        or receipt["http_status"] != 200
        or len(raw) != receipt["bytes"]
        or hashlib.sha256(raw).hexdigest() != receipt["sha256"]
    ):
        raise ValueError("Unverified native response")
    return receipt, list(csv.DictReader(raw.decode().splitlines()))


def main(args):
    args.output.mkdir(exist_ok=False)
    originals = {}
    for station in ("KSFO", "KOAK", "KSJC"):
        _, rows = verified(
            BASE / "captures_03",
            BASE / "captures_03" / ("metar-routine-" + station + ".json"),
        )
        for row in rows:
            originals[(row["station"], row["valid"])] = row["metar"]
    checks = []
    for name in ("bulk_service_captures_01", "bulk_hourly_captures_01"):
        directory = BASE / name
        manifest = json.loads((directory / "MANIFEST.json").read_text())
        for spec in manifest["rows"]:
            receipt, rows = verified(directory, directory / (spec["id"] + ".json"))
            matches = all(
                originals.get((r["station"], r["valid"])) == r["metar"] for r in rows
            )
            if not rows or not matches:
                raise ValueError(
                    "Bulk source differs from separately bound station archive"
                )
            if "target_hour" in spec:
                target = datetime.fromisoformat(
                    spec["target_hour"].replace("Z", "+00:00")
                )
                if len(rows) != 3 or any(
                    datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
                    .replace(tzinfo=timezone.utc)
                    .replace(minute=0)
                    != target
                    for r in rows
                ):
                    raise ValueError(
                        "Hourly query did not respect its registered window"
                    )
            checks.append(
                {
                    "id": spec["id"],
                    "capture": str(directory.relative_to(BASE)),
                    "rows": len(rows),
                    "stations": sorted({r["station"] for r in rows}),
                    "bytes": receipt["bytes"],
                    "sha256": receipt["sha256"],
                    "matches_native_single_station_rows": matches,
                }
            )
    record = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "observed": "One historical HTTP request returns all three stations for one hour (3 rows), or for one day (72 rows). The source matches single-station native METAR exactly.",
        "scope": "Observed archive API transport capability; original historical first-seen and live service latency remain unproved.",
        "request_sensitivity": {
            "hours": 72,
            "logical_full_read_slot_requests": 216,
            "one_batch_per_hour_requests": 72,
            "current_logical_budget": 144,
            "full_read_fits_request_cap_if_hourly_batching_is_legal": True,
            "full_period_transport_bytes": "not independently measured for each historical replay hour",
        },
        "strong_comparator": "Use the all-source complete-update program's predictions as the all-read comparator. Its original 216 slot charges remain unchanged; any 72-request physical batch repricing is separately labelled a sensitivity, not an actually run online workload.",
        "scientific_consequence": "The three-station task does not establish naturally scarce source acquisition. Preserve it for E/version/F engineering and do not attribute logical-price scheduling gains to a deployed LLM advantage.",
        "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.output / "VERIFIED.json").write_text(json.dumps(record, indent=2) + "\n")
    shutil.copyfile(__file__, args.output / "verify_bulk_service.py")
    print(
        json.dumps(
            {
                "real_responses": len(checks),
                "matched_rows_including_overlap": sum(r["rows"] for r in checks),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
