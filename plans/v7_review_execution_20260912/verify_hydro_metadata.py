"""Check native gauge mappings and distinguish stage thresholds from flow gaps."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save


def threshold(value):
    if value is None or value == -9999:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Malformed native threshold")
    return value


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_hydro_metadata.py")
    root = args.source.resolve()
    plan_path = root / "PLAN.json"
    plan = json.loads(plan_path.read_text())
    complete = json.loads((root / "CAPTURE_COMPLETE.json").read_text())
    if digest(plan_path) != complete["plan_sha256"] or complete["logical_requests"] != 3:
        raise ValueError("Metadata capture differs from its bounded plan")
    bindings = {str(plan_path): digest(plan_path), str(root / "CAPTURE_COMPLETE.json"): digest(root / "CAPTURE_COMPLETE.json")}
    rows = []
    for spec in plan["specs"]:
        receipt_path = root / (spec["id"] + ".json")
        body_path = receipt_path.with_suffix(".body")
        receipt = json.loads(receipt_path.read_text())
        if (receipt["url"] != spec["url"] or receipt["http_status"] != 200 or receipt["curl_exit"] != 0
                or receipt.get("locally_truncated") or digest(body_path) != receipt["sha256"]
                or body_path.stat().st_size != receipt["bytes"]):
            raise ValueError("Unsuccessful or changed native metadata capture")
        body = json.loads(body_path.read_text())
        if body["lid"] != spec["expected_nws_lid"] or body["usgsId"] != spec["expected_usgs_site"]:
            raise ValueError("Official metadata does not confirm the original site mapping")
        flood = body["flood"]
        if flood["stageUnits"] != "ft" or flood["flowUnits"] != "cfs":
            raise ValueError("Unexpected native threshold units")
        categories = {name: {"stage_ft": threshold(flood["categories"][name]["stage"]),
                             "flow_cfs": threshold(flood["categories"][name]["flow"]),
                             "raw": flood["categories"][name]}
                      for name in ("action", "minor", "moderate", "major")}
        rows.append({"nws_lid": body["lid"], "usgs_id": body["usgsId"], "name": body["name"],
                     "site_mapping_confirmed": True, "categories": categories,
                     "datum_metadata": [{"abbrev": r["abbrev"], "value": r["value"]}
                                        for r in body["datums"]["vertical"]["value"]],
                     "hydronotes": body["hydronotes"], "retrieved_at": receipt["finished_at"],
                     "has_minor_flow_threshold_for_existing_QINE_chain": categories["minor"]["flow_cfs"] is not None,
                     "has_current_minor_stage_threshold": categories["minor"]["stage_ft"] is not None,
                     "historical_threshold_effective_dates_verified": False})
        bindings[str(receipt_path)] = digest(receipt_path)
        bindings[str(body_path)] = digest(body_path)
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "gauges": rows,
              "native_source_requests": complete["logical_requests"], "response_bytes": complete["response_bytes"],
              "confirmed_site_mappings": sum(r["site_mapping_confirmed"] for r in rows),
              "current_minor_stage_thresholds": sum(r["has_current_minor_stage_threshold"] for r in rows),
              "current_minor_flow_thresholds": sum(r["has_minor_flow_threshold_for_existing_QINE_chain"] for r in rows),
              "new_H08_warning_admission": False, "new_model_calls": 0,
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "verify_hydro_metadata.py"),
              "interpretation": [
                  "The original HEFS/USGS station mappings are confirmed by current official metadata.",
                  "Native -9999 is retained as an unavailable field, never a physical flow threshold or a zero.",
                  "Stage in ft cannot be applied to QINE discharge in CFS or converted by a unit multiplier.",
                  "Next qualification should verify a native stage forecast and USGS 00065/NWPS observation with the same gauge datum, or an official versioned rating relation for discharge.",
                  "Current threshold metadata does not establish historical validity; do not retrospectively relabel the six prior flow targets.",
                  "Historical crest tables and convenient observed stage/flow pairs are not an official time-valid rating curve.",
              ]}
    save(args.output / "REPORT.json", report)
    lines = ["# Official H08 gauge-metadata preflight", "",
             "All three existing NWS-to-USGS site mappings match current official NWPS metadata.",
             "Native unavailable values remain explicit; stage and discharge are separate variables.", "",
             "| NWS gauge | USGS site | Action stage, ft | Minor flood stage, ft | Minor flow threshold, cfs |",
             "| --- | --- | ---: | ---: | --- |"]
    for row in rows:
        categories = row["categories"]
        lines.append(f"| {row['nws_lid']} | {row['usgs_id']} | {categories['action']['stage_ft']} | "
                     f"{categories['minor']['stage_ft']} | {categories['minor']['flow_cfs']} (raw {categories['minor']['raw']['flow']}) |")
    lines += ["", "The old QINE/CFS chain remains a discharge task. A flood-stage task requires matched stage forecasts, observations, datum and threshold-history evidence.",
              "CRHA2 metadata notes seasonal ice effects; all datum and quality notes remain in REPORT.json and original payloads.",
              "No flood labels, historical threshold validity or new monitoring admission are inferred from this metadata sample.", ""]
    (args.output / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({k: report[k] for k in ("confirmed_site_mappings", "current_minor_stage_thresholds", "current_minor_flow_thresholds", "new_H08_warning_admission")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
