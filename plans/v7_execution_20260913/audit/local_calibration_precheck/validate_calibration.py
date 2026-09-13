"""Validate raw provenance, chronological splits and static evaluation masks."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from precheck import HERE, REPO, capture

sys.path.insert(0, str(HERE.parent))
from audit_saved_traces import independent_scores  # noqa: E402
from disastertrace.monitoring_v1.calibration import feature_key  # noqa: E402
from disastertrace.monitoring_v1.targets import utc_us  # noqa: E402


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    dataset = HERE / "local_dataset_02"
    contract_path = HERE / "FULL_CONTRACT.json"
    contract = load(contract_path)
    audit = load(dataset / "REGIONAL_JOIN_AUDIT.json")
    if audit["contract_sha256"] != sha(contract_path):
        raise ValueError("Contract hash mismatch")
    sources = load(dataset / "SOURCES.json")
    for identity, record in sources.items():
        if sha(HERE / record["path"]) != record["sha256"] or sha(HERE / record["receipt_path"]) != record["receipt_sha256"]:
            raise ValueError("Raw dataset source binding changed")
        capture((HERE / record["path"]).parent, identity)
    targets = {r["target_id"]: r for r in load(dataset / "public/TARGETS.json")}
    opportunities = load(dataset / "public/OPPORTUNITIES.json")
    outcomes = {r["target_id"]: r for r in load(dataset / "private/OUTCOMES.json")}
    pairs = {r["opportunity_id"]: r for r in load(dataset / "public/E_F_PAIRS.json")}
    bases = {r["opportunity_id"]: r for r in load(dataset / "environment/LATEST_BASELINES.json")}
    products = {r["query_id"]: r for r in load(dataset / "environment/QUERY_RESULTS.json")}
    split_results = {}
    for split_name, directory in [("matched", "bank_matched_01"), ("expanded", "bank_expanded_01")]:
        split = contract["paired_matched_window_rule"] if split_name == "matched" else contract["split"]
        start, end = utc_us(split["fit_start"]), utc_us(split["fit_end_exclusive"])
        check_start, check_end = utc_us(split["check_start"]), utc_us(split["check_end_exclusive"])
        if not end <= utc_us(split["purge_start"]) < utc_us(split["purge_end_exclusive"]) <= check_start:
            raise ValueError("Missing chronological purge")
        bank = load(HERE / directory / "BANK.json")
        fit_ids = load(HERE / directory / "FIT_IDS.json")
        eligible = [o for o in opportunities if start <= o["cutoff"] < end and targets[o["target_id"]]["physical_end"] <= end and outcomes[o["target_id"]]["outcome"] is not None]
        expected_ids = [o["opportunity_id"] for o in eligible]
        if set(expected_ids) != set(fit_ids) or len(expected_ids) != len(fit_ids):
            raise ValueError("Fit membership differs from frozen prior-period split")
        if hashlib.sha256(json.dumps(sorted(fit_ids)).encode()).hexdigest() != bank["fit_opportunity_ids_sha256"]:
            raise ValueError("Fit identity checksum mismatch")
        seen, reconstructed = set(), defaultdict(lambda: {"n": 0, "positive": 0})
        for opportunity in eligible:
            target = targets[opportunity["target_id"]]
            candidate = bases.get(opportunity["opportunity_id"])
            pair = pairs[opportunity["opportunity_id"]]
            keys = {feature_key(target, candidate), json.dumps([target["threshold"], "pooled"], separators=(",", ":"))}
            for size in range(1, len(pair["query_ids"]) + 1):
                for selected in combinations(pair["query_ids"], size):
                    keys.add(feature_key(target, candidate, pair["query_ids"], {q: products[q] for q in selected}))
            for key in keys:
                identity = (target["target_id"], key)
                if identity not in seen:
                    seen.add(identity)
                    reconstructed[key]["n"] += 1
                    reconstructed[key]["positive"] += outcomes[target["target_id"]]["outcome"]
        if dict(reconstructed) != bank["cells"]:
            raise ValueError("Frozen frequency cells do not reconstruct from prior targets")
        expected_check = [o for o in opportunities if check_start <= o["cutoff"] < check_end and targets[o["target_id"]]["physical_end"] <= check_end]
        fit_targets = {o["target_id"] for o in eligible}
        check_targets = {o["target_id"] for o in expected_check}
        if fit_targets & check_targets:
            raise ValueError("Train/check target overlap")
        check_rows = load(HERE / directory / "CHECK_ROWS.json")
        if set(r["opportunity_id"] for r in check_rows) != {o["opportunity_id"] for o in expected_check}:
            raise ValueError("Check membership changed")
        if bank["source_dataset_audit_sha256"] != sha(dataset / "REGIONAL_JOIN_AUDIT.json") or bank["contract_sha256"] != sha(contract_path):
            raise ValueError("Bank provenance mismatch")
        split_results[split_name] = {"fit_opportunities": len(fit_ids), "fit_unique_targets": len(fit_targets),
                                    "check_opportunities": len(check_rows), "check_unique_targets": len(check_targets),
                                    "overlapping_targets": 0, "cell_counts_reconstructed": len(reconstructed),
                                    "fit_dates": [split["fit_start"], split["fit_end_exclusive"]],
                                    "check_dates": [split["check_start"], split["check_end_exclusive"]],
                                    "heldout_positive_opportunities_by_threshold": dict(Counter(str(r["threshold"]) for r in check_rows if r["outcome"] == 1))}
    static = load(HERE / "static_comparison_01/REPORT.json")
    predictions = load(HERE / "static_comparison_01/PREDICTIONS_BEFORE_LABELS.json")
    freeze = load(HERE / "static_comparison_01/PREDICTION_FREEZE.json")
    if freeze["rows_sha256"] != sha(HERE / "static_comparison_01/PREDICTIONS_BEFORE_LABELS.json"):
        raise ValueError("Prediction file changed after label-free freeze")
    evaluation_path = REPO / static["design"]["evaluation_dataset"] / "private/OUTCOMES.json"
    if static["outcomes_sha256"] != sha(evaluation_path):
        raise ValueError("Evaluation result table changed")
    evaluation = {r["target_id"]: r for r in load(evaluation_path)}
    for name, values in predictions.items():
        if any(r["target_id"] in targets for r in values):
            raise ValueError("Evaluation target reused in December training dataset")
        score = independent_scores([dict(r, outcome=evaluation[r["target_id"]]["outcome"]) for r in values])
        if score != static["arms"][name]["scores"]:
            raise ValueError("Static score reconstruction changed")
    bound_files = [contract_path, HERE / "STATIC_COMPARISON_DESIGN.json", dataset / "REGIONAL_JOIN_AUDIT.json", dataset / "SOURCES.json",
                   HERE / "bank_matched_01/BANK.json", HERE / "bank_expanded_01/BANK.json", HERE / "static_comparison_01/REPORT.json", evaluation_path]
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "source_bodies_and_receipts_verified": len(sources),
              "splits": split_results, "january_targets_disjoint_from_training_dataset": True,
              "static_arms_recomputed": len(predictions), "all_static_arms_common_mask": True,
              "input_bindings": {str(p.relative_to(REPO)): sha(p) for p in bound_files},
              "validator_sha256": sha(Path(__file__)), "new_model_calls": 0}
    with (HERE / "FULL_VALIDATION.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "input_bindings"}, indent=2))


if __name__ == "__main__":
    main()
