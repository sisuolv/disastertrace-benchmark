"""Audit current native stage availability and exact-time inter-service matches."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import shutil
from pathlib import Path

from gpu_worker import digest, save


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Native timestamp lacks a timezone")
    return result.astimezone(timezone.utc)


def number(value):
    if value is None or isinstance(value, bool):
        return None
    result = Decimal(str(value))
    return result if result.is_finite() and result != -9999 else None


def main(args):
    root = args.source.resolve()
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_hydro_stage.py")
    plan_path = root / "PLAN.json"
    plan = json.loads(plan_path.read_text())
    complete = json.loads((root / "CAPTURE_COMPLETE.json").read_text())
    if complete["plan_sha256"] != digest(plan_path) or complete["logical_requests"] != 6:
        raise ValueError("Stage capture does not match its six-request scope")
    bindings = {str(plan_path): digest(plan_path),
                str(root / "CAPTURE_COMPLETE.json"): digest(root / "CAPTURE_COMPLETE.json")}
    metadata = []
    for name, expected in plan["metadata_binding"].items():
        path = Path(name)
        if digest(path) != expected:
            raise ValueError("Previously verified station metadata changed")
        bindings[name] = expected
        metadata += json.loads(path.read_text())["gauges"]
    sites = {r["nws_lid"]: r for r in metadata}
    captures, failures, total_bytes = {}, [], 0
    for spec in plan["specs"]:
        receipt_path = root / (spec["id"] + ".json")
        body_path = receipt_path.with_suffix(".body")
        receipt = json.loads(receipt_path.read_text())
        if (receipt["url"] != spec["url"] or digest(body_path) != receipt["sha256"]
                or body_path.stat().st_size != receipt["bytes"]):
            raise ValueError("Native capture identity changed")
        total_bytes += receipt["bytes"]
        for path in (receipt_path, body_path):
            bindings[str(path)] = digest(path)
        if receipt["http_status"] != 200 or receipt["curl_exit"] != 0 or receipt.get("locally_truncated"):
            failures.append({"id": spec["id"], "http_status": receipt["http_status"], "curl_exit": receipt["curl_exit"]})
            continue
        captures[spec["id"]] = (json.loads(body_path.read_text()), receipt)
    if total_bytes != complete["response_bytes"]:
        raise ValueError("Captured byte accounting differs")
    rows = []
    paired_rows = []
    for lid in ("NRWI4", "CRHA2", "SCOC1"):
        native_id, usgs_id = "nwps-stageflow-" + lid.lower(), "usgs-stage-" + lid.lower()
        if native_id not in captures or usgs_id not in captures:
            rows.append({"nws_lid": lid, "pair_status": "unavailable_capture"})
            continue
        native, receipt = captures[native_id]
        usgs, _ = captures[usgs_id]
        sections, tables = {}, {}
        for key in ("observed", "forecast"):
            section = native[key]
            if section["primaryName"] != "Stage" or section["primaryUnits"] != "ft":
                raise ValueError("Expected native stage in ft; no automatic variable conversion")
            samples = section["data"]
            table = {}
            for sample in samples:
                time = instant(sample["validTime"])
                instant(sample["generatedTime"])
                if time in table:
                    raise ValueError("Multiple native rows at one valid time require a version policy")
                table[time] = sample
            tables[key] = table
            sections[key] = {"pedts": section["pedts"], "issued_time": section["issuedTime"],
                             "primary_name": section["primaryName"], "primary_units": section["primaryUnits"],
                             "secondary_name": section["secondaryName"], "secondary_units": section["secondaryUnits"],
                             "rows": len(samples), "finite_stage_rows": sum(number(s["primary"]) is not None for s in samples),
                             "valid_start": min(table).isoformat() if table else None,
                             "valid_end": max(table).isoformat() if table else None,
                             "valid_after_local_retrieval": sum(t > instant(receipt["finished_at"]) for t in table),
                             "native_generated_times": sorted({s["generatedTime"] for s in samples}) if key == "forecast" else None}
        if usgs["numberReturned"] != len(usgs["features"]) or any(link["rel"] == "next" for link in usgs["links"]):
            raise ValueError("USGS result is incomplete or paginated")
        observations = {}
        for feature in usgs["features"]:
            value = feature["properties"]
            if (value["parameter_code"] != "00065" or value["unit_of_measure"] != "ft"
                    or value["monitoring_location_id"] != "USGS-" + sites[lid]["usgs_id"]):
                raise ValueError("USGS gage-height identity or units differ")
            time = instant(value["time"])
            if time in observations:
                raise ValueError("Multiple USGS stage series at one instant")
            observations[time] = value
        paired = []
        for time in sorted(observations.keys() & tables["observed"].keys()):
            left, right = tables["observed"][time], observations[time]
            lv, rv = number(left["primary"]), number(right["value"])
            paired.append({"nws_lid": lid, "valid_time": time.isoformat(),
                           "nwps_stage_ft": str(lv) if lv is not None else None,
                           "usgs_stage_ft": str(rv) if rv is not None else None,
                           "delta_ft": str(lv - rv) if lv is not None and rv is not None else None,
                           "equal_finite_stage": lv is not None and rv is not None and lv == rv,
                           "usgs_approval_status": right["approval_status"],
                           "usgs_qualifier": right["qualifier"],
                           "usgs_last_modified": right["last_modified"],
                           "nwps_generated_time": left["generatedTime"]})
        paired_rows.extend(paired)
        rows.append({"nws_lid": lid, "usgs_site": sites[lid]["usgs_id"], "pair_status": "decoded",
                     "series": sections, "usgs_native_rows": len(observations),
                     "usgs_approval_statuses": dict(Counter(v["approval_status"] for v in observations.values())),
                     "exact_time_pairs": len(paired), "equal_finite_stage_pairs": sum(p["equal_finite_stage"] for p in paired),
                     "unmatched_usgs_times": sorted(t.isoformat() for t in observations.keys() - tables["observed"].keys()),
                     "current_minor_stage_threshold_ft": sites[lid]["categories"]["minor"]["stage_ft"],
                     "datum_metadata": sites[lid]["datum_metadata"],
                     "datum_history_independently_verified": False})
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "native_source_requests": 6,
              "response_bytes": total_bytes, "transport_failures": failures, "gauges": rows,
              "paired_native_rows": len(paired_rows), "equal_stage_pairs": sum(r["equal_finite_stage"] for r in paired_rows),
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "verify_hydro_stage.py"),
              "new_model_calls": 0, "new_H08_warning_admission": False,
              "interpretation": [
                  "Current native deterministic stage forecasts and observed stage are actually downloaded; the existing HEFS flow chain is unchanged.",
                  "NWPS observed data may relay USGS measurements: exact matches are service linkage evidence, not independent truth replication.",
                  "Valid, issued, generated and locally retrieved times remain distinct; retrospective first-seen and future outcome settlement are not established.",
                  "Current stage agreement and gauge metadata support a stage-task candidate, not historical datum/threshold validity or a versioned rating curve.",
                  "NWPS secondary flow uses kcfs; never treat it as cfs, stage or a native event probability.",
                  "No near-time substitution, flood-label creation or fit on these samples is performed; absent timestamps remain absent.",
              ]}
    save(args.output / "PAIRS.json", paired_rows)
    save(args.output / "REPORT.json", report)
    print(json.dumps({k: report[k] for k in ("native_source_requests", "response_bytes", "paired_native_rows", "equal_stage_pairs", "new_H08_warning_admission")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
