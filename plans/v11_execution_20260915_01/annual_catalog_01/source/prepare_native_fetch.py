"""Freeze unique full native TAF downloads from verified complete calendar catalogs."""

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def main(args):
    requests, bindings = {}, []
    for receipt_path in sorted(args.catalogs.glob("taf-catalog-*.json")):
        if receipt_path.name.endswith(".intent.json"):
            continue
        receipt = json.loads(receipt_path.read_text())
        path = args.catalogs / receipt["body_file"]
        raw = path.read_bytes()
        if (
            not receipt.get("complete")
            or receipt["http_status"] != 200
            or hashlib.sha256(raw).hexdigest() != receipt["sha256"]
        ):
            raise ValueError("Catalog capture is not complete and bound")
        bindings.append({"path": str(path.resolve()), "sha256": receipt["sha256"]})
        for row in csv.DictReader(raw.decode().splitlines()):
            pid = row["product_id"]
            if not re.fullmatch(r"[A-Za-z0-9-]+", pid):
                raise ValueError(
                    "Native product ID is missing or not a safe path component"
                )
            spec = {
                "id": "taf-" + pid,
                "url": "https://mesonet.agron.iastate.edu/api/1/nwstext/" + pid,
                "max_bytes": 131072,
                "timeout": 60,
                "purpose": "full native bulletin from fixed temporal replication calendar",
                "catalog_metadata": {
                    "station": row["station"],
                    "issued_at": row["valid"],
                },
            }
            if pid in requests and requests[pid] != spec:
                raise ValueError(
                    "Native product has conflicting catalog station/issue metadata"
                )
            requests[pid] = spec
    if not requests or len(bindings) != 3:
        raise ValueError("Expected three nonempty station calendars")
    plan = {
        "schema": "disastertrace.monitoring.public_capture.v1",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "transport": "curl",
        "limits": {"requests": len(requests), "bytes": len(requests) * 131073},
        "allowed_hosts": ["mesonet.agron.iastate.edu"],
        "pause_seconds": 3,
        "catalog_bindings": bindings,
        "planner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "requests": [requests[k] for k in sorted(requests)],
    }
    with args.output.open("x") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"native_bulletins": len(requests), "catalogs": len(bindings)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
