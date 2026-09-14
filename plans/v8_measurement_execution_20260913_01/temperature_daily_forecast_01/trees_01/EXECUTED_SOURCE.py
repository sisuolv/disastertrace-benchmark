"""Fetch a one-use manifest of public contract sources with bounded responses."""

import argparse
import datetime as dt
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "temperature_daily_forecast_01"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT):
        raise ValueError("Output outside this temperature contract work package")
    plan = json.loads(args.plan.read_text())
    if len(plan["requests"]) > 16:
        raise ValueError("At most sixteen bounded public requests per manifest")
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(args.plan, args.output / "PLAN.json")
    shutil.copyfile(Path(__file__), args.output / "EXECUTED_SOURCE.py")
    receipts = []
    for row in plan["requests"]:
        target = args.output / row["name"]
        if not target.resolve().is_relative_to(args.output.resolve()):
            raise ValueError("Invalid local path")
        if not row["url"].startswith(
            (
                "https://api.github.com/",
                "https://raw.githubusercontent.com/",
                "https://codes.ecmwf.int/",
            )
        ):
            raise ValueError("Unexpected contract-source host")
        result = {**row, "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(
                row["url"],
                headers={"User-Agent": "DisasterTrace-contract-verification/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read(2_097_153)
                if len(data) > 2_097_152:
                    raise ValueError("Contract response exceeds2MiBcap")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle:
                    handle.write(data)
                result.update(
                    status="downloaded",
                    http_status=response.status,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    final_url=response.url,
                )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            result.update(
                status="failed_preserved_no_retry",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        result["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        receipts.append(result)
        with (args.output / "RECEIPTS.jsonl").open("a") as handle:
            handle.write(json.dumps(result) + "\n")
    with (args.output / "COMPLETE.json").open("x") as handle:
        json.dump(
            {
                "requests": len(receipts),
                "successful": sum(r["status"] == "downloaded" for r in receipts),
                "new_model_calls": 0,
                "retries": 0,
                "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    print(
        json.dumps(
            [{k: r.get(k) for k in ("name", "status", "bytes")} for r in receipts]
        )
    )


if __name__ == "__main__":
    main()
