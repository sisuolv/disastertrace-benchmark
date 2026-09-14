"""Decode captured live native reports and retain actual collector first-seen."""

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.providers.aviation import parse_metar, parse_taf

HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instant(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    source = HERE / "shadow_capture_01"
    plan = read(source / "PLAN.json")
    assert args.allow_incomplete or (source / "COMPLETE.json").exists()
    args.output.mkdir(exist_ok=False)
    products, captures, failed = {}, [], []
    for receipt_path in sorted(source.glob("poll_*/*.receipt.json")):
        receipt = read(receipt_path)
        if receipt["status"] != "received_json":
            failed.append(
                {
                    "receipt": str(receipt_path.relative_to(source)),
                    "status": receipt["status"],
                    "http_status": receipt.get("http_status"),
                }
            )
            continue
        kind = receipt["kind"]
        raw_path = receipt_path.with_name(kind + ".raw.json")
        assert sha(raw_path) == receipt["payload_sha256"]
        fetched = instant(receipt["completed_at"])
        assert instant(receipt["started_at"]) <= fetched
        captures.append(
            {
                "receipt": str(receipt_path.relative_to(source)),
                "receipt_sha256": sha(receipt_path),
                "payload_sha256": sha(raw_path),
            }
        )
        for item in read(raw_path):
            assert item["icaoId"] in plan["stations"]
            raw = item["rawTAF" if kind == "taf" else "rawOb"]
            key = (
                kind
                + ":"
                + item["icaoId"]
                + ":"
                + hashlib.sha256(raw.encode()).hexdigest()
            )
            observation = (
                dt.datetime.fromtimestamp(item["obsTime"], dt.timezone.utc)
                if kind == "metar"
                else None
            )
            source_time = observation or instant(item["issueTime"])
            row = {
                "product_id": key,
                "kind": kind,
                "station": item["icaoId"],
                "raw": raw,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "native_source_time": source_time.isoformat(),
                "collector_first_seen": fetched.isoformat(),
                "visible_at": fetched.isoformat(),
                "provider_database_time": item.get(
                    "dbPopTime", item.get("receiptTime")
                ),
                "provider_report_time": item.get("reportTime"),
                "capture_receipts": [str(receipt_path.relative_to(source))],
            }
            try:
                if source_time > fetched:
                    raise ValueError(
                        "Native issuance/observation later than actual receipt"
                    )
                if kind == "taf":
                    parsed = parse_taf(
                        raw, station=item["icaoId"], archive_issue=item["issueTime"]
                    )
                    if (
                        parsed.valid_start != item["validTimeFrom"] * 1_000_000
                        or parsed.valid_end != item["validTimeTo"] * 1_000_000
                    ):
                        raise ValueError(
                            "Native TAF envelope differs from provider metadata"
                        )
                    row.update(
                        parse_status="parsed",
                        native_status=parsed.status,
                        valid_start=parsed.valid_start,
                        valid_end=parsed.valid_end,
                        clause_operators=[c.operator for c in parsed.clauses],
                    )
                else:
                    kind_map = {"METAR": "routine", "SPECI": "special"}
                    parsed = parse_metar(
                        raw,
                        observation_time=observation.isoformat(),
                        report_type=kind_map[item["metarType"]],
                    )
                    if parsed.station != item["icaoId"]:
                        raise ValueError("Native METAR station differs from metadata")
                    row.update(
                        parse_status="parsed",
                        report_type=parsed.report_type,
                        visibility=parsed.visibility.to_dict()
                        if parsed.visibility
                        else None,
                        quality_flags=list(parsed.quality_flags),
                        provider_qc_field=item.get("qcField"),
                    )
            except (ValueError, KeyError) as error:
                row.update(
                    parse_status="unresolved",
                    error_type=type(error).__name__,
                    reason=str(error),
                )
            if key in products:
                old = products[key]
                assert (
                    old["raw"] == row["raw"]
                    and old["native_source_time"] == row["native_source_time"]
                )
                old["capture_receipts"].extend(row["capture_receipts"])
                old["collector_first_seen"] = min(
                    old["collector_first_seen"], row["collector_first_seen"]
                )
                old["visible_at"] = old["collector_first_seen"]
            else:
                products[key] = row
    counts = Counter((r["kind"], r["parse_status"]) for r in products.values())
    output = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_plan_sha256": sha(source / "PLAN.json"),
        "collection_complete": (source / "COMPLETE.json").exists(),
        "registered_poll_count": len(plan["poll_times"]),
        "successful_captured_requests": len(captures),
        "failed_captured_requests": failed,
        "captures": captures,
        "unique_products": len(products),
        "parse_counts": [
            {"kind": k, "status": s, "n": n} for (k, s), n in sorted(counts.items())
        ],
        "products": list(products.values()),
        "actual_model_calls": 0,
        "submitted_forecast_opportunities": 0,
        "scope": "Actual prospective source receipts with native parsing and source/version retention. Source-only development validation, not a live forecasting benchmark score. Collector first-seen is not global first publication; missing requests and parser failures are retained.",
        "time_rule": "METAR physical/native reference uses obsTime validated against raw DDHHMMZ, never rounded provider reportTime. TAF envelope is checked against raw native DDHH endpoints.",
        "support_rule": "Native encoded product values/censoring; not error-free physical visibility. AWC derived display fields do not replace raw encoded support.",
    }
    with (args.output / "REPORT.json").open("x") as handle:
        json.dump(output, handle, indent=2, allow_nan=False)
    (args.output / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(
        json.dumps(
            {
                "unique_products": len(products),
                "parse_counts": output["parse_counts"],
                "requests": len(captures),
                "actual_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
