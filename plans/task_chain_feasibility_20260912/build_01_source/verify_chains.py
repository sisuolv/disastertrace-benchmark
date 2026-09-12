"""Independently re-read source bytes and recompute the small pilot's scores."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

import eccodes


REPO = Path(__file__).resolve().parents[2]


def dt(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve the old verification")
    bindings = json.loads((args.data / "SOURCE_BINDINGS.json").read_text())
    raw = {}
    errors = []
    for item in bindings:
        path = REPO / item["path"]
        content = path.read_bytes()
        receipt = (REPO / item["receipt"]).read_bytes()
        if (hashlib.sha256(content).hexdigest() != item["sha256"] or len(content) != item["bytes"]
                or hashlib.sha256(receipt).hexdigest() != item["receipt_sha256"]):
            errors.append("source_binding:" + item["id"])
        raw[item["id"]] = content
    checkpoints = rows(args.data / "public/checkpoints.jsonl")
    outcomes = {r["target_id"]: r for r in rows(args.data / "private/outcomes.jsonl")}
    by_checkpoint = {r["checkpoint_id"]: r for r in checkpoints}
    grib_checks = 0
    for model in json.loads((args.data / "DECODED_PRODUCTS.json").read_text()):
        if "nearest" not in model:
            continue
        h = eccodes.codes_new_from_message(raw[model["source"]])
        try:
            values = eccodes.codes_get_values(h)
            actual = float(values[model["nearest"]["index"]])
            if abs(actual - model["nearest"]["value"]) > 1e-8:
                errors.append("grib_value:" + model["source"])
            for key in ["shortName", "units", "dataDate", "dataTime", "validityDate", "validityTime"]:
                if eccodes.codes_get(h, key) != model[key]:
                    errors.append("grib_metadata:" + key)
            grib_checks += 1
        finally:
            eccodes.codes_release(h)
    reference_checks = 0
    for ref in outcomes.values():
        if ref["source"] is None:
            continue
        if ref["family"] == "river_discharge":
            matches = [f["properties"] for f in json.loads(raw[ref["source"]])["features"]
                       if dt(f["properties"]["time"]) == dt(ref["target_time"])]
            if len(matches) != 1 or float(matches[0]["value"]) != ref["value"]:
                errors.append("flow_reference:" + ref["target_id"])
        else:
            native = list(csv.DictReader(io.StringIO(raw[ref["source"]].decode())))
            key = "DATE" if ref["family"] in {"temperature", "precipitation"} else "valid"
            matches = [r for r in native if dt(r[key]) == dt(ref["target_time"])]
            if len(matches) != 1:
                errors.append("reference_count:" + ref["target_id"])
                continue
            native = matches[0]
            if ref["family"] == "temperature":
                value, qc = native["TMP"].split(",")
                if qc in {"1", "5"}:
                    if int(value) / 10 != ref["value"]:
                        errors.append("temperature_reference:" + ref["target_id"])
                elif ref["value"] is not None or ref["status"] != "unresolved_quality":
                    errors.append("suspect_temperature_admitted")
            elif ref["family"] == "precipitation":
                if native["AA1"].split(",")[2] != "3" or ref["value"] is not None:
                    errors.append("accumulation_condition_admitted")
            else:
                # For these US reports the threshold is far from a rounding boundary.
                reported = float(native["vsby"]) * 1609.344
                if (reported < 1000) != ref["below_1000m"] or native["metar"] != ref["raw_metar"]:
                    errors.append("visibility_reference:" + ref["target_id"])
        reference_checks += 1
    for point in checkpoints:
        ref = outcomes[point["target_id"]]
        clock, target = dt(point["clock"]), dt(point["target_time"])
        if target != dt(ref["target_time"]) or clock >= target:
            errors.append("target_time:" + point["checkpoint_id"])
        forecast = point["professional_forecast"]
        if not dt(forecast["issue"]) <= dt(forecast["available_at"]) <= clock:
            errors.append("forecast_available_time:" + point["checkpoint_id"])
        prior = point["prior_observation"]
        if prior and dt(prior["time"]) + timedelta(minutes=5) > clock:
            errors.append("observation_future_leak:" + point["checkpoint_id"])
        if any(key in point for key in ["outcome", "outcome_value", "reference", "gold", "actual_below_1000m"]):
            errors.append("outcome_in_public_row:" + point["checkpoint_id"])
        if point["task_kind"] == "point_discharge":
            members = json.loads(raw[forecast["source"]])[0]
            values = [float(e["value"]) for m in members for e in m["events"] if dt(e["valid_datetime"]) == target]
            if len(values) != forecast["member_count"] or not math.isclose(statistics.fmean(values), forecast["value"], abs_tol=1e-9):
                errors.append("ensemble_mean:" + point["checkpoint_id"])
        elif point["task_kind"] == "point_temperature":
            if abs(forecast["grid_point"]["value"] - 273.15 - forecast["value"]) > 1e-9:
                errors.append("temperature_unit_conversion")
        elif point["task_kind"] == "point_visibility":
            if not dt(forecast["segment_start"]) <= target < dt(forecast["segment_end"]):
                errors.append("taf_support:" + point["checkpoint_id"])
    scores = rows(args.data / "baselines.jsonl")
    for score in scores:
        point = by_checkpoint[score["checkpoint_id"]]
        ref = outcomes[point["target_id"]]
        if "absolute_error" in score:
            expected = None if score["value"] is None or ref["value"] is None else abs(score["value"] - ref["value"])
            if expected != score["absolute_error"]:
                errors.append("scalar_score:" + score["checkpoint_id"])
        else:
            predicted, actual = score["predicted_below_1000m"], ref["below_1000m"]
            expected = None if predicted is None or actual is None else predicted == actual
            if expected != score["correct"]:
                errors.append("classification_score:" + score["checkpoint_id"])
    if len(outcomes) != 34 or len(checkpoints) != 96 or len(scores) != 192 or len(by_checkpoint) != 96:
        errors.append("expected_opportunities")
    result = dict(all_passed=not errors, errors=errors, source_files=len(bindings),
                  grib_messages_redecoded=grib_checks, reference_records=reference_checks,
                  checkpoints=len(checkpoints), scores=len(scores), targets=len(outcomes),
                  builder_imported=False, new_model_calls=0,
                  scope="File bindings, independent values, timing, retained rejection and numerical score checks.")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
