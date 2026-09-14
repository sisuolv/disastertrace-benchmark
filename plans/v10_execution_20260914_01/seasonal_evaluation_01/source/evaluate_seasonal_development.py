"""Audit new seasonal native data and evaluate frozen winter banks without refitting."""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.evidence import exists_report_support, report_fact_status
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector
from disastertrace.monitoring_v1.providers.aviation import parse_metar
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash
from fit_native_feature_bank import native_examples, probability


def prepare(args):
    args.out.mkdir(exist_ok=False)
    run = Path(__file__).resolve().parents[1]
    (args.out / "banks").mkdir()
    for region in ("new_york", "chicago", "denver"):
        shutil.copyfile(run / "native_feature_sessions_01" / (region + "__2025-01-06__1000") / "BANK.json",
                        args.out / "banks" / (region + ".json"))
    for mode in ("common", "mask_age", "values"):
        shutil.copyfile(run / "native_feature_bank_01" / ("BANK_" + mode + ".json"), args.out / "banks" / (mode + ".json"))
    shutil.copytree(run / "native_feature_bank_01/source", args.out / "source")
    shutil.copyfile(__file__, args.out / "source/evaluate_seasonal_development.py")
    publish(args.out / "PLAN.json", {"schema": "disastertrace.seasonal_fixed_bank.v1",
        "completion_batch": str(args.completion), "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "registered_units": read(args.completion / "PLAN.json")["units"], "registered_opportunities": 12096,
        "prediction_time": "cutoff minus600seconds for all methods", "raw_primary": True,
        "calibrated_secondary": "frozen winter prior2 PAV/CDF; no seasonal recalibration",
        "factors": ["common_only", "all_registered"], "families": ["common", "mask_age", "values"],
        "scope": "seasonal developmental transfer; winter-only training support is explicitly limited",
        "independent_synoptic_process_count_established": False, "calendar_blocks": 4,
        "new_fit": False, "model_calls": 0, "confirmation_opened": False,
        "files": {str(p.relative_to(args.out)): digest(p) for p in args.out.rglob("*") if p.is_file()}})


def audit_and_score(pair):
    out, unit = pair
    dataset = Path(unit["dataset"])
    for name, sha in unit["dataset_files"].items():
        if digest(dataset / name) != sha:
            raise ValueError("Frozen seasonal dataset changed")
    region, week = unit["unit"].split("__")
    sources = read(dataset / "SOURCES.json")
    source_lines, hashes = {}, {}
    for sid, source in sources.items():
        for field, sha_field in (("path", "sha256"), ("receipt_path", "receipt_sha256")):
            path = Path(source[field])
            if digest(path) != source[sha_field]:
                raise ValueError("Actual native source or acquisition receipt changed")
            hashes[str(path)] = source[sha_field]
        receipt = read(Path(source["receipt_path"]))
        assert receipt["http_status"] == 200 and receipt["complete"] and receipt["curl_exit"] == 0
        if sid.startswith("metar"):
            source_lines[sid] = Path(source["path"]).read_text().splitlines()
    decoded = read(dataset / "private/DECODED_REPORTS.json")
    record_ids = set()
    for row in decoded:
        if not row.get("decoded"):
            continue
        line = source_lines[row["source_id"]][row["source_line"] - 1]
        assert row["raw"] in next(csv.reader([line]))
        at = dt.datetime.fromtimestamp(row["observation_time"] / 1e6, dt.timezone.utc).isoformat()
        native = parse_metar(row["raw"], observation_time=at, report_type="routine")
        assert native.station == row["station"]
        assert (None if native.visibility is None else native.visibility.to_dict()) == row["visibility"]
        record_ids.add(canonical_hash([row["station"], row["observation_time"], hashlib.sha256(row["raw"].encode()).hexdigest()]))
    outcomes = {r["target_id"]: r for r in read(dataset / "private/OUTCOMES.json")}
    targets = {r["target_id"]: r for r in read(dataset / "public/TARGETS.json")}
    pairs = {r["opportunity_id"]: r for r in read(dataset / "public/E_F_PAIRS.json")}
    opportunities = read(dataset / "public/OPPORTUNITIES.json")
    if len(opportunities) != 1008 or len({r["opportunity_id"] for r in opportunities}) != 1008:
        raise ValueError("Seasonal natural-calendar denominator differs")
    rows = [{**r, "station": targets[r["target_id"]]["entity"], "region": region,
        "role": "seasonal_development", "query_ids": pairs[r["opportunity_id"]]["query_ids"],
        "outcome": outcomes[r["target_id"]]["outcome"]} for r in opportunities]
    baseline = read(out / "banks" / (region + ".json"))
    banks = {mode: read(out / "banks" / (mode + ".json")) for mode in ("common", "mask_age", "values")}
    result_rows, e_rows, drift = [], [], Counter()
    for item in native_examples(dataset, rows):
        for threshold, target in item["targets"].items():
            assert target["physical_start"] > item["at"]
            qids, evidence = item["query_ids"], item["views"][-1]
            e = exists_report_support(qids, evidence, threshold)
            states = [report_fact_status(evidence[q], threshold) if q in evidence else "undetermined" for q in qids]
            e_rows.append({"unit": unit["unit"], "opportunity_id": item["opportunity_ids"][threshold],
                "threshold": threshold, "E": e, "slot_statuses": states, "outcome": item["outcomes"][threshold],
                "read_slots": len(evidence), "reference_status": outcomes[target["target_id"]]["status"]})
        predictions = {"FOLLOW": {t: predict(baseline, target, item["candidate"])["probability"] for t, target in item["targets"].items()}}
        feature_hashes = {}
        for mode, bank in banks.items():
            for condition in ("common_only", "all_registered"):
                features = feature_vector(item["target"], item["candidate"], item["query_ids"],
                    {} if condition == "common_only" else item["views"][-1], at=item["at"], mode=mode)
                for name, mean, scale in zip(bank["feature_names"], bank["mean"], bank["scale"], strict=True):
                    if abs((features.get(name, 0)-mean)/scale) > 5:
                        drift[mode + "__" + condition + "__" + name] += 1
                for calibrated in (False, True):
                    name = mode + "__" + condition + "__" + ("pav_prior2_cdf" if calibrated else "raw")
                    predictions[name] = probability(bank, features, calibrated=calibrated)
                    feature_hashes[name] = canonical_hash(features)
                    assert 0 <= predictions[name][1000] <= predictions[name][5000] <= 1
        for method, p in predictions.items():
            for t, value in p.items():
                result_rows.append({"unit": unit["unit"], "region": region, "week": week,
                    "opportunity_id": item["opportunity_ids"][t], "method": method, "threshold": t,
                    "probability": value, "base": predictions["FOLLOW"][t], "outcome": item["outcomes"][t],
                    "information_sha256": item["information_sha256"], "feature_sha256": feature_hashes.get(method),
                    "quality": outcomes[item["targets"][t]["target_id"]]["status"]})
    directory = out / unit["unit"]
    directory.mkdir()
    for name, values in (("ROWS.jsonl", result_rows), ("E_ROWS.jsonl", e_rows)):
        with (directory / name).open("x") as stream:
            for row in values:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
    publish(directory / "SOURCE_AUDIT.json", {"passed": True, "source_hashes": hashes,
        "decoded_records": len(decoded), "distinct_native_record_ids": sorted(record_ids),
        "registered_opportunities": len(opportunities), "reference_status": dict(Counter(r["status"] for r in outcomes.values())),
        "feature_outside5_training_sd": dict(drift), "threshold_crossings_in_feature_predictions": 0,
        "raw_parsing_independence": "exact source-line and byte audit, frozen provider parser reused"})
    return {"unit": unit["unit"], "complete": True, "opportunities": len(opportunities),
            "rows": len(result_rows), "source_files": len(hashes)}


def execute(args):
    plan = read(args.out / "PLAN.json")
    publish(args.out / "RUN_CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    for path, sha in plan["files"].items():
        assert digest(args.out / path) == sha
    complete = Path(plan["completion_batch"]) / "COMPLETE.json"
    deadline = time.monotonic() + args.wait_seconds
    while not complete.exists() and time.monotonic() < deadline:
        time.sleep(20)
    units = read(complete)["units"]
    if {r["unit"] for r in units} != set(plan["registered_units"]):
        raise ValueError("Registered seasonal unit roster changed")
    publish(args.out / "DATA_FREEZE.json", {"completion_sha256": digest(complete), "units": units})
    good = [u for u in units if u["complete"]]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(audit_and_score, [(args.out, unit) for unit in good]))
    groups, metrics = defaultdict(list), {}
    for unit in good:
        for line in (args.out / unit["unit"] / "ROWS.jsonl").read_text().splitlines():
            row = json.loads(line)
            for key in ("ALL", row["region"], row["week"]):
                groups[key + "__" + str(row["threshold"]) + "__" + row["method"]].append(row)
    for key, rows in groups.items():
        metrics[key] = brier_report({"opportunity_id": r["opportunity_id"], "base": r["base"],
            "prediction": r["probability"], "outcome": r["outcome"], "region": r["region"], "period": r["week"],
            "source": "IEM routine METAR", "quality": r["quality"], "maturity": "archived_report",
            "baseline_kind": "research"} for r in rows)
    publish(args.out / "METRICS.json", metrics)
    publish(args.out / "RESULT.json", {"passed": len(results) == len(units), "units": results,
        "missing_units": [u for u in units if not u["complete"]], "registered_opportunities": 12096,
        "available_opportunities": sum(r["opportunities"] for r in results),
        "model_calls": 0, "new_fit": False, "confirmation_opened": False,
        "interpretation": "Frozen winter banks evaluated across4new seasonal calendars; no independence or calibrated-transfer guarantee"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--completion", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    args.out = args.out.absolute()
    execute(args) if args.execute else prepare(args)
