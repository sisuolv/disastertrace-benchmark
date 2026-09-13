"""Compare every native row of repeated USGS captures without replacing old labels."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gpu_worker import digest, save


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("USGS timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def decode(body, spec):
    data = json.loads(body.read_text())
    if data["type"] != "FeatureCollection" or any(link.get("rel") == "next" for link in data.get("links", [])):
        raise ValueError("Incomplete native feature collection or unconsumed pagination")
    query = parse_qs(urlsplit(spec["url"]).query)
    station = query["monitoring_location_id"][0]
    start, end = map(instant, query["datetime"][0].split("/"))
    rows = {}
    for feature in data["features"]:
        row = feature["properties"]
        at = instant(row["time"])
        if (row["monitoring_location_id"] != station or row["parameter_code"] != "00060"
                or row["statistic_id"] != "00011" or row["unit_of_measure"] != "ft^3/s"
                or not start <= at <= end):
            raise ValueError("Discharge identity, unit or requested support mismatch")
        value = Decimal(row["value"])
        if not value.is_finite():
            raise ValueError("Non-finite reported flow")
        key = at.isoformat()
        if key in rows:
            raise ValueError("Duplicate native record at the same station/time")
        rows[key] = {"time": key, "value": str(value.normalize()), "raw_value": row["value"],
                     "approval_status": row["approval_status"], "qualifier": row.get("qualifier"),
                     "time_series_id": row["time_series_id"],
                     "last_modified": instant(row["last_modified"]).isoformat() if row.get("last_modified") else None,
                     "eligible_report_value": value >= 0 and row["approval_status"] in {"Provisional", "Approved"} and row.get("qualifier") in (None, "")}
    if data.get("numberReturned", len(rows)) != len(rows):
        raise ValueError("Native row count differs")
    return rows


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_hydro_revisions.py")
    source = args.source.resolve()
    plan_path = source / "PLAN.json"
    plan = json.loads(plan_path.read_text())
    complete_path = source / "CAPTURE_COMPLETE.json"
    complete = json.loads(complete_path.read_text())
    if complete["plan_sha256"] != digest(plan_path) or complete["requests"] != 3:
        raise ValueError("Capture scope differs from frozen plan")
    bindings = {str(plan_path): digest(plan_path), str(complete_path): digest(complete_path)}
    for name, expected in plan["before_bindings"].items():
        if digest(source / name) != expected:
            raise ValueError("Original capture changed")
    reports, changes, failures = [], [], []
    for spec in plan["specs"]:
        try:
            sides = {}
            for side in ("before", "after"):
                receipt_path = source / side / (spec["id"] + ".json")
                body_path = receipt_path.with_suffix(".body")
                receipt = json.loads(receipt_path.read_text())
                bindings[str(receipt_path)] = digest(receipt_path)
                bindings[str(body_path)] = digest(body_path)
                if (receipt["url"] != spec["url"] or receipt["http_status"] != 200 or receipt["curl_exit"] != 0
                        or receipt.get("locally_truncated") or digest(body_path) != receipt["sha256"]
                        or body_path.stat().st_size != receipt["bytes"] or receipt["bytes"] > spec["max_bytes"]):
                    raise ValueError("Unsuccessful, incomplete or changed source capture")
                sides[side] = (decode(body_path, spec), receipt)
            old, old_receipt = sides["before"]
            new, new_receipt = sides["after"]
            if instant(new_receipt["started_at"]) <= instant(old_receipt["finished_at"]):
                raise ValueError("The repeat capture did not follow the original")
            common = sorted(set(old) & set(new))
            fields = ("value", "approval_status", "qualifier", "time_series_id", "last_modified", "eligible_report_value")
            changed_counts = Counter()
            for key in common:
                changed = [field for field in fields if old[key][field] != new[key][field]]
                changed_counts.update(changed)
                if changed:
                    changes.append({"source_id": spec["id"], "time": key, "changed_fields": changed,
                                    "before": old[key], "after": new[key]})
            target_comparisons = []
            for hour in (0, 6):
                key = f"2026-09-12T{hour:02d}:00:00+00:00"
                target_comparisons.append({"time": key, "before": old.get(key), "after": new.get(key),
                                           "same_reported_flow": key in old and key in new and old[key]["value"] == new[key]["value"]})
            reports.append({"source_id": spec["id"], "before_rows": len(old), "after_rows": len(new),
                            "paired_rows": len(common), "added_times": sorted(set(new) - set(old)),
                            "removed_times": sorted(set(old) - set(new)), "changed_fields": dict(changed_counts),
                            "before_quality": dict(Counter(r["approval_status"] for r in old.values())),
                            "after_quality": dict(Counter(r["approval_status"] for r in new.values())),
                            "before_ineligible": sum(not r["eligible_report_value"] for r in old.values()),
                            "after_ineligible": sum(not r["eligible_report_value"] for r in new.values()),
                            "captured_before_finished_at": old_receipt["finished_at"],
                            "captured_after_finished_at": new_receipt["finished_at"],
                            "body_sha256_changed": old_receipt["sha256"] != new_receipt["sha256"],
                            "previous_six_target_comparisons": target_comparisons})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            failures.append({"source_id": spec["id"], "error": type(error).__name__ + ": " + str(error)})
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "sources": reports, "failures": failures,
              "all_three_native_sources_decoded": len(reports) == 3 and not failures,
              "paired_native_rows": sum(r["paired_rows"] for r in reports),
              "logical_source_requests": complete["requests"], "new_response_bytes": complete["bytes"],
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "verify_hydro_revisions.py"),
              "reference_kind": "native_USGS_report", "support_assumption": "exact_reported_product_value_not_error_free_physical_discharge",
              "new_H08_monitoring_warning_admission": False, "new_model_calls": 0,
              "interpretation": [
                  "All original provisional captures and six earlier outcomes are retained; this report does not replace them.",
                  "USGS last_modified is a source metadata timestamp, not proven historical public availability.",
                  "A changed response hash or metadata-only update does not imply a changed flow value.",
                  "No detected numerical revision in this bounded pair of downloads does not guarantee future stability.",
                  "This is H08 source-maturity readiness, not a new warning engine, flood-threshold validation or C1/F gain experiment.",
              ]}
    save(args.output / "REPORT.json", report)
    save(args.output / "CHANGED_ROWS.json", changes)
    lines = ["# H08 provisional-source revision preflight", "",
             "The same three USGS windows were downloaded a second time, retaining all original bytes and labels.", "",
             "| Source | Old rows | New rows | Paired | Flow changes | Quality changes | Modified-time changes |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in reports:
        change = item["changed_fields"]
        lines.append(f"| {item['source_id']} | {item['before_rows']} | {item['after_rows']} | {item['paired_rows']} | "
                     f"{change.get('value',0)} | {change.get('approval_status',0)} | {change.get('last_modified',0)} |")
    lines += ["", "Failures: " + json.dumps(failures), "",
              "REPORT.json retains additions, removals, quality status and the six prior exact-time target comparisons.",
              "CHANGED_ROWS.json retains every detected field change, including metadata-only changes.",
              "This validates a bounded maturity check; it does not establish a complete flood-warning task or historical first-seen.", ""]
    (args.output / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"sources": len(reports), "paired_rows": report["paired_native_rows"], "changed_rows": len(changes), "failures": failures}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
