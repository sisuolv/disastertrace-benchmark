"""Fit only preregistered December blocks; January outcomes never enter fitting."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from disastertrace.monitoring_v1.calibration import feature_key, predict
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.targets import utc_us

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def fit(dataset, contract_path, output):
    contract = load(contract_path)
    audit = load(dataset / "REGIONAL_JOIN_AUDIT.json")
    contract_digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    if audit["contract_sha256"] != contract_digest:
        raise ValueError("Dataset was not built from this calibration contract")
    split = contract["split"]
    fit_start, fit_end = utc_us(split["fit_start"]), utc_us(split["fit_end_exclusive"])
    check_start, check_end = utc_us(split["check_start"]), utc_us(split["check_end_exclusive"])
    targets = {r["target_id"]: r for r in load(dataset / "public/TARGETS.json")}
    opportunities = load(dataset / "public/OPPORTUNITIES.json")
    outcomes = {r["target_id"]: r for r in load(dataset / "private/OUTCOMES.json")}
    bases = {r["opportunity_id"]: r for r in load(dataset / "environment/LATEST_BASELINES.json")}
    pairs = {r["opportunity_id"]: r for r in load(dataset / "public/E_F_PAIRS.json")}
    results = {r["query_id"]: r for r in load(dataset / "environment/QUERY_RESULTS.json")}
    cells = defaultdict(lambda: {"n": 0, "positive": 0})
    seen = set()
    fit_ids = []
    for opportunity in opportunities:
        target_id, opp_id = opportunity["target_id"], opportunity["opportunity_id"]
        target, outcome = targets[target_id], outcomes[target_id]
        # Entire physical support is inside the fit block, including the tail.
        if not fit_start <= opportunity["cutoff"] < fit_end or target["physical_end"] > fit_end or outcome["outcome"] is None:
            continue
        candidate, pair = bases.get(opp_id), pairs[opp_id]
        keys = {feature_key(target, candidate), json.dumps([target["threshold"], "pooled"], separators=(",", ":"))}
        for size in range(1, len(pair["query_ids"]) + 1):
            for chosen in combinations(pair["query_ids"], size):
                disclosed = {q: results[q] for q in chosen}
                keys.add(feature_key(target, candidate, pair["query_ids"], disclosed))
        for key in keys:
            identity = (target_id, key)
            if identity in seen:
                continue
            seen.add(identity)
            cells[key]["n"] += 1
            cells[key]["positive"] += outcome["outcome"]
        fit_ids.append(opp_id)
    bank = {"schema": "disastertrace.monitoring.frequency_bank.v1",
        "mapping_version": "native_taf_interval_counts." + split["fit_start"][:7] + ".v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(), "minimum_cell_n": 20, "smoothing": "(positive+1)/(n+2)",
        "cells": dict(sorted(cells.items())), "fit_opportunities": len(fit_ids),
        "fit_opportunity_ids_sha256": hashlib.sha256(json.dumps(sorted(fit_ids)).encode()).hexdigest(),
        "source_dataset_audit_sha256": hashlib.sha256((dataset / "REGIONAL_JOIN_AUDIT.json").read_bytes()).hexdigest(),
        "contract_sha256": contract_digest,
        "temporal_horizon_identity": "target start minus native product issue, stable until product changes",
        "deduplication": "One target contributes at most once per feature cell; cells are not independent observations",
        "probability_semantics": "smoothed research forecast mapping, not native TAF/TEMPO probability or guaranteed calibrated acquisition policy",
        "confirmation": False}
    rows = []
    for opportunity in opportunities:
        target = targets[opportunity["target_id"]]
        if not check_start <= opportunity["cutoff"] < check_end or target["physical_end"] > check_end:
            continue
        candidate = bases.get(opportunity["opportunity_id"])
        base = predict(bank, target, candidate)
        pair = pairs[opportunity["opportunity_id"]]
        revised = predict(bank, target, candidate, pair["query_ids"], {q: results[q] for q in pair["query_ids"]})
        rows.append({"opportunity_id": opportunity["opportunity_id"], "threshold": target["threshold"],
                     "base": base["probability"], "prediction": revised["probability"],
                     "outcome": outcomes[target["target_id"]]["outcome"], "region": "bay_area",
                     "period": str(opportunity["cutoff"] // 86_400_000_000), "source": "native_metar",
                     "quality": outcomes[target["target_id"]]["status"], "maturity": "final_archive",
                     "baseline_kind": "research"})
    report = {"fit_start": split["fit_start"], "fit_end_exclusive": split["fit_end_exclusive"],
              "check_start": split["check_start"], "check_end_exclusive": split["check_end_exclusive"],
              "fit_unique_targets": len({opportunities_id.split('-cutoff-')[0] for opportunities_id in fit_ids}),
              "cell_count": len(cells), "by_threshold": {str(threshold): brier_report([r for r in rows if r["threshold"] == threshold])
                                                         for threshold in contract["thresholds_m"]},
              "interpretation": "separate development check, not independent weather-process confirmation; no formal calibration guarantee",
              "bank_frozen_before_january_model_predictions": True}
    output.mkdir(parents=True, exist_ok=False)
    source = output / "implementation"
    source.mkdir()
    shutil.copyfile(__file__, source / "fit_calibration.py")
    mapping_source = Path(predict.__code__.co_filename)
    shutil.copyfile(mapping_source, source / "calibration.py")
    bank["implementation_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    for name, data in (("BANK.json", bank), ("CHECK_REPORT.json", report), ("CHECK_ROWS.json", rows), ("FIT_IDS.json", fit_ids)):
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"fit_opportunities": len(fit_ids), "cells": len(cells), "check_opportunities": len(rows)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--contract", type=Path, default=ROOT / "CALIBRATION_CONTRACT.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fit(args.dataset, args.contract, args.output)
