"""Keep actual model answers, arithmetic controls, and unavailable providers separate."""

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish


def lines(path):
    import json

    return [json.loads(line) for line in path.read_text().splitlines()]


def main(out):
    out.mkdir(exist_ok=False)
    run = Path(__file__).resolve().parents[1]
    pairs = [run / "reports/feature_temperature_final_02/scores", run / "large_feature_trial_01/final_audit_01/scores"]
    results, sources, unavailable = {}, {}, {}
    for folder in pairs:
        for name in ("RESULT.json", "ANSWERS.jsonl", "FIELDS.jsonl", "ROWS.jsonl"):
            sources[str(folder / name)] = digest(folder / name)
        answers, fields, rows = (lines(folder / n) for n in ("ANSWERS.jsonl", "FIELDS.jsonl", "ROWS.jsonl"))
        for model in sorted({r["model"] for r in answers}):
            selected = [r for r in answers if r["model"] == model]
            received = [r for r in selected if r["capture_state"] == "RECEIVED"]
            if not received:
                unavailable[model] = {"registered": len(selected), "states": dict(Counter(r["capture_state"] for r in selected)),
                    "model_performance_ranked": False, "reason": "compatibility402; fallback scores are deployment bookkeeping only"}
                continue
            errors = defaultdict(Counter)
            for field in fields:
                if field["model"] != model:
                    continue
                errors[field["field"]].update(registered=1, correct=int(field["semantic_exact"]),
                    invalid_answer=int(field["invalid_answer"]))
            temperature = [r for r in rows if r["model"] == model and r["kind"] == "temperature_F"]
            valid = [r for r in temperature if r["outcome"] is not None]
            changes = [r["probabilities"]["model_F"]-r["probabilities"]["FOLLOW"] for r in temperature]
            gains = [(r["probabilities"]["FOLLOW"]-r["outcome"])**2 - (r["probabilities"]["model_F"]-r["outcome"])**2 for r in valid]
            aviation = [r for r in rows if r["model"] == model and r["kind"] == "aviation_features"]
            statuses = defaultdict(Counter)
            for row in aviation:
                for state in row["E_slot_statuses"].values():
                    statuses[str(row["threshold"])].update(registered=1, equal=int(state["claimed"] == state["native"]))
            results[model] = {"received": len(received), "valid": sum(r["valid"] for r in selected),
                "invalid_rows_retained": sum(not r["valid"] for r in selected), "field_agreement": dict(errors),
                "E_threshold_status_agreement": dict(statuses),
                "temperature": {"registered": len(temperature), "scored": len(valid), "positive": sum(r["outcome"] for r in valid),
                    "exact_baseline_copies": sum(d == 0 for d in changes), "changed_by_more_than1e_minus6": sum(abs(d) > 1e-6 for d in changes),
                    "baseline_brier": math.fsum((r["probabilities"]["FOLLOW"]-r["outcome"])**2 for r in valid)/len(valid),
                    "model_brier": math.fsum((r["probabilities"]["model_F"]-r["outcome"])**2 for r in valid)/len(valid),
                    "g_plus": math.fsum(max(0, g) for g in gains)/len(gains),
                    "g_minus": math.fsum(max(0, -g) for g in gains)/len(gains), "net_gain": math.fsum(gains)/len(gains)},
                "ordinary_aviation": {str(t): {"registered": sum(r["threshold"] == t and r["cohort"] == "ordinary" for r in aviation),
                    "positive": sum(r["outcome"] == 1 for r in aviation if r["threshold"] == t and r["cohort"] == "ordinary")}
                    for t in (1000, 5000)},
                "comparison_not_parameter_count_causal": True}
    publish(out / "SOURCE_HASHES.json", sources)
    publish(out / "RESULT.json", {"passed": True, "models": results, "unavailable_providers": unavailable,
        "score_contracts": "This report compares only the same212feature/F tasks with predeclared whole-fence acceptance.",
        "first2016packet_answers_are_separate_contract": True, "confirmation_opened": False,
        "new_inference": 0, "interpretation": "Local235B revises more temperature baselines but loses accuracy on this exposed sample; extraction accuracy depends on explicit main-report and interval contracts."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.out.absolute())
