"""Freeze deterministic prior-trained predictions before loading January labels."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))

from audit_saved_traces import backoff, independent_scores  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    design_path = HERE / "STATIC_COMPARISON_DESIGN.json"
    design = load(design_path)
    output = HERE / "static_comparison_01"
    output.mkdir(exist_ok=False)
    dataset = REPO / design["evaluation_dataset"]
    bank_files = {"bay_transferred_original": REPO / design["original_bay_bank"],
                  "front_local_matched_window": HERE / "bank_matched_01/BANK.json",
                  "front_local_expanded_window": HERE / "bank_expanded_01/BANK.json"}
    banks = {name: load(path) for name, path in bank_files.items()}
    targets = {r["target_id"]: r for r in load(dataset / "public/TARGETS.json")}
    opportunities = [r for r in load(dataset / "public/OPPORTUNITIES.json") if r["threshold_m"] == 1000]
    opportunities.sort(key=lambda r: r["opportunity_id"])
    bases = {r["opportunity_id"]: r for r in load(dataset / "environment/LATEST_BASELINES.json")}
    pairs = {r["opportunity_id"]: r for r in load(dataset / "public/E_F_PAIRS.json")}
    products = {r["query_id"]: r for r in load(dataset / "environment/QUERY_RESULTS.json")}
    catalog = {r["query_id"]: r for r in load(dataset / "public/QUERY_CATALOG.json")}
    rows_by_arm = {}
    for bank_name, bank in banks.items():
        for condition in design["evidence_conditions"]:
            values = []
            for o in opportunities:
                target, candidate = targets[o["target_id"]], bases.get(o["opportunity_id"])
                qids = pairs[o["opportunity_id"]]["query_ids"]
                visible = {}
                if condition == "all_registered":
                    for q in qids:
                        if catalog[q]["available_at"] + catalog[q]["latency_ms"] * 1000 > o["cutoff"]:
                            raise ValueError("All-read diagnostic includes a late source")
                        visible[q] = products[q]
                mapped = backoff(bank, target, candidate, qids, visible)
                anchor = backoff(banks["bay_transferred_original"], target, candidate)
                values.append({"opportunity_id": o["opportunity_id"], "target_id": target["target_id"],
                               "cutoff": o["cutoff"], "station": target["entity"],
                               "base": anchor["probability"], "prediction": mapped["probability"],
                               "cell_key": mapped["cell_key"], "cell_n": mapped["n"],
                               "mapping_level": mapped["level"], "read_query_ids": sorted(visible)})
            rows_by_arm[bank_name + "/" + condition] = values
    write(output / "PREDICTIONS_BEFORE_LABELS.json", rows_by_arm)
    write(output / "PREDICTION_FREEZE.json", {"frozen_at": datetime.now(timezone.utc).isoformat(),
                                             "rows_sha256": digest(output / "PREDICTIONS_BEFORE_LABELS.json"),
                                             "design_sha256": digest(design_path),
                                             "bank_sha256": {n: digest(p) for n, p in bank_files.items()},
                                             "january_evaluation_label_file_read_by_this_process": False,
                                             "dates_previously_exposed_in_project": True})
    outcome_path = dataset / "private/OUTCOMES.json"
    outcomes = {r["target_id"]: r for r in load(outcome_path)}
    scores = {}
    for arm, values in rows_by_arm.items():
        scored = [dict(r, outcome=outcomes[r["target_id"]]["outcome"]) for r in values]
        scores[arm] = {"scores": independent_scores(scored),
                       "mapping_levels": dict(Counter(r["mapping_level"] for r in values)),
                       "unique_probabilities": len({r["prediction"] for r in values}),
                       "predictions_different_from_original_bay_base": sum(r["prediction"] != r["base"] for r in values)}
    old_calendar = load(REPO / "plans/v7_review_execution_20260912/calendar_analysis_front_02/REPORT.json")
    old_score = next(iter(old_calendar["arms"].values()))["scores"]
    common = scores["bay_transferred_original/common_only"]["scores"]
    if any(abs(common[k] - old_score[k]) > 1e-12 for k in ["opportunities", "settled", "base_brier"]):
        raise ValueError("Original baseline or common evaluation denominator changed")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "design": design, "arms": scores,
              "outcomes_sha256": digest(outcome_path), "common_opportunities": len(opportunities),
              "original_bay_baseline_reproduced": True, "new_model_calls": 0,
              "full_adaptive_policy_execution": False,
              "interpretation": "Exposed development static forecasts from frozen prior-period banks. All-read is a fixed source-information diagnostic; no end-to-end acquisition cost/latency gain or local-calibration superiority guarantee.",
              "implementation_sha256": digest(Path(__file__))}
    write(output / "REPORT.json", report)
    print(json.dumps({name: value["scores"] for name, value in scores.items()}, indent=2))


if __name__ == "__main__":
    main()
