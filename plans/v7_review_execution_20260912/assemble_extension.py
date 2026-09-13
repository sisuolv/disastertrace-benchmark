"""Assemble hash-verified source receipts without redownloading or hiding failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def assemble(args):
    origins = json.loads((BASE / "EXTENSION_NATIVE_ORIGINS.json").read_text())
    contract = json.loads(args.contract.read_text())
    if args.kind == "taf":
        ids = origins["region_product_ids"][args.region]
        locations = {
            ident: REPO / origins["reused_verified"][ident]
            if ident in origins["reused_verified"]
            else args.new_captures
            for ident in ids
        }
    else:
        locations = {}
        for station in contract["stations"]:
            ident = "metar-routine-" + station
            old_receipt = args.original_captures / (ident + ".json")
            original = json.loads(old_receipt.read_text())
            locations[ident] = (
                args.original_captures
                if original.get("complete") and original["http_status"] == 200
                else args.new_captures
            )
    # Do not claim a partial downloader is a complete regional capture.
    for ident, directory in locations.items():
        for suffix in (".body", ".json"):
            if not (directory / (ident + suffix)).is_file():
                raise ValueError("Capture is not yet available: " + ident)
    args.output.mkdir(exist_ok=False)
    rows, provenance = [], []
    for ident, directory in sorted(locations.items()):
        body, receipt_path = (
            directory / (ident + ".body"),
            directory / (ident + ".json"),
        )
        receipt = json.loads(receipt_path.read_text())
        if digest(body) != receipt["sha256"] or body.stat().st_size != receipt["bytes"]:
            raise ValueError("Source body differs from its receipt: " + ident)
        for path in (body, receipt_path):
            shutil.copyfile(path, args.output / path.name)
        rows.append(receipt)
        provenance.append(
            {
                "id": ident,
                "source": str(directory.resolve()),
                "body_sha256": digest(body),
                "receipt_sha256": digest(receipt_path),
            }
        )
    save(
        args.output / "MANIFEST.json",
        {
            "planned": len(rows),
            "attempted": len(rows),
            "rows": rows,
            "assembled_at": datetime.now(timezone.utc).isoformat(),
            "assembly_is_not_a_network_request": True,
        },
    )
    save(
        args.output / "ASSEMBLY.json",
        {
            "region": args.region,
            "kind": args.kind,
            "origins": provenance,
            "contract_sha256": digest(args.contract),
            "implementation_sha256": digest(Path(__file__)),
            "success": sum(
                r.get("complete", False) and r["http_status"] == 200 for r in rows
            ),
            "prior_failed_attempts_retained": str(args.original_captures),
        },
    )
    shutil.copyfile(__file__, args.output / "assemble_extension.py")
    print(json.dumps({"output": str(args.output), "assembled": len(rows)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=["bay_area", "front_range"], required=True)
    parser.add_argument("--kind", choices=["taf", "metar"], required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument(
        "--new-captures", type=Path, default=BASE / "extension_native_captures_02"
    )
    parser.add_argument("--original-captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    assemble(parser.parse_args())
