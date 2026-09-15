"""Read-only comparison of old/new qualification on existing actual artifacts."""

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1 import feature_tasks as current
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def load_legacy(path, name):
    spec = importlib.util.spec_from_file_location("disastertrace.monitoring_v1." + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def result(function, *args):
    try:
        return {"valid": True, "value": function(*args)}
    except (ValueError, TypeError, OverflowError, KeyError, IndexError) as exc:
        return {"valid": False, "error_type": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    out = args.run / "impact_01"
    out.mkdir(exist_ok=False)
    before = args.run / "before/disastertrace-starter/src/disastertrace/monitoring_v1"
    legacy = load_legacy(before / "feature_tasks.py", "v11_legacy_feature_tasks")
    native = load_legacy(before / "native_feature_forecast.py", "v11_legacy_native_features")
    legacy.validate_claims = native.validate_claims
    records, bindings, counts = [], {}, Counter()
    unique_temperature = set()

    def compare(identity, category, old, new, *values):
        a, b = result(old, *values), result(new, *values)
        changed = a != b
        counts[category] += 1
        counts[category + "_changed"] += changed
        records.append({"id": identity, "category": category, "before": a, "after": b, "changed": changed})

    def read_bound(path):
        bindings[str(path)] = digest(path)
        return read(path)

    v10 = args.repo / "plans/v10_execution_20260914_01"
    for batch in ("feature_temperature_trial_02", "large_feature_trial_01", "clarified_feature_trial_01"):
        root = v10 / batch
        packets = read_bound(root / "PACKETS.json")
        for call_id, packet in packets.items():
            bundle = read_bound(root / "bundles" / (call_id + ".json"))
            if packet["kind"] == "temperature_F":
                unique_temperature.add(bundle["opportunity_id"])
                compare(batch + "/" + call_id, "temperature_model_input",
                        legacy.temperature_ensemble_probability, current.temperature_ensemble_probability, bundle)
            responses = list((root / "gpu").glob("worker_*/" + call_id + ".response.json"))
            if len(responses) != 1:
                raise ValueError("Expected exactly one original GPU capture for " + batch + "/" + call_id)
            capture = read_bound(responses[0])
            if packet["kind"] == "temperature_F":
                compare(batch + "/" + call_id, "temperature_response", legacy.parse_temperature,
                        current.parse_temperature, capture["raw"])
            else:
                compare(batch + "/" + call_id, "feature_response", legacy.parse_features,
                        current.parse_features, capture["raw"], list(bundle["disclosed"]))
    months = args.repo / "plans/v9_followup_execution_20260914_01/temperature_fullcalendar_01"
    directories = sorted(months.glob("20??-??"))
    if len(directories) != 24:
        raise ValueError("Expected all24 original temperature months")
    for month in directories:
        for row in read_bound(month / "POLICY.json")["rows"]:
            unique_temperature.add(row["opportunity_id"])
            compare(month.name + "/" + row["opportunity_id"], "temperature_calendar_input",
                    legacy.temperature_ensemble_probability, current.temperature_ensemble_probability, row)
    publish(out / "RECORDS.json", records)
    publish(out / "BINDINGS.json", bindings)
    changes = [r for r in records if r["changed"]]
    summary = {"completed_scope": True, "counts": dict(counts), "changes": changes,
        "distinct_temperature_opportunities": len(unique_temperature), "months": len(directories),
        "original_artifacts_modified": False, "new_model_calls": 0,
        "scope": "128-task packets for two GPU models,84 clarified tasks, and24-month original POLICY rows; not every historical dataset",
        "records_sha256": digest(out / "RECORDS.json")}
    publish(out / "RESULT.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "changes"}), flush=True)


if __name__ == "__main__":
    main()
