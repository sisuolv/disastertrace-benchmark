"""Full-denominator descriptive C1 controls from the40 original program runs."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.scoring import brier_report

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "reports/program_calendar_analysis_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    audit_root = HERE / "reports/program_calendar_optimized_audit_01"
    assert read(audit_root / "BATCH_COMPLETE.json")["all_passed"]
    OUT.mkdir(exist_ok=False)
    totals, effects = [], []
    for threshold in (1000, 5000):
        for protocol in ("base_bound_override", "persistent_override"):
            group = f"{threshold}__{protocol}"
            original = HERE / "reports/program_calendar_02" / group
            qualified = audit_root / group
            scores = read(qualified / "SCORES.json")
            receipt = read(qualified / "VALIDATION.json")
            assert receipt["passed"]
            hashes = {r["arm"]: r for r in receipt["arms"]}
            outcomes = {
                r["opportunity_id"]: r for r in read(original / "OUTCOMES.json")
            }
            config = read(original / "CONFIGS.json")
            baselines = {
                r["opportunity_id"]: r
                for r in read(original / "P00_follow/REPORT.json")["snapshots"]
            }
            group_rows = {}
            for arm in config:
                path = original / arm / "REPORT.json"
                assert sha(path) == hashes[arm]["source_report_sha256"]
                report = read(path)
                metrics_rows, changes = [], Counter()
                for row in report["snapshots"]:
                    oid = row["opportunity_id"]
                    base = baselines[oid]["forecast"]["value"]
                    prediction = row["forecast"]["value"]
                    result = outcomes[oid]
                    y = result["value"] if result["status"] == "mature" else None
                    assert row["base_forecast"] == baselines[oid]["base_forecast"]
                    metrics_rows.append(
                        {
                            "opportunity_id": oid,
                            "outcome": y,
                            "base": base,
                            "prediction": prediction,
                            "region": "Bay",
                            "period": "2025-02-03",
                            "source": "native_routine_METAR",
                            "quality": result["quality_status"],
                            "maturity": result["status"],
                            "baseline_kind": row["baseline_kind"],
                        }
                    )
                    changes["effective_probability_changed"] += int(prediction != base)
                    changes["effective_override"] += int(row["mode"] == "OVERRIDE")
                    changes["same_value_override"] += int(
                        row["mode"] == "OVERRIDE" and prediction == base
                    )
                    if y is not None:
                        gain = (base - y) ** 2 - (prediction - y) ** 2
                        changes[
                            "help"
                            if gain > 1e-15
                            else "harm"
                            if gain < -1e-15
                            else "no_loss_change"
                        ] += 1
                metrics = brier_report(metrics_rows)
                assert (
                    abs(
                        metrics["system_brier"]
                        - scores["scores"]["arms"][arm]["mean_loss"]
                    )
                    < 1e-14
                )
                assert metrics["opportunities"] == scores["scores"]["registered"] == 216
                item = {
                    "group": group,
                    "threshold_m": threshold,
                    "protocol": protocol,
                    "arm": arm,
                    "selector": config[arm]["selector_kind"],
                    "allocation": config[arm]["allocation_mode"],
                    "authorization": config[arm]["authorization_mode"],
                    "opportunities": metrics["opportunities"],
                    "settled": metrics["settled"],
                    "missing": metrics["missing"],
                    "positive_opportunities": sum(
                        r["outcome"] == 1 for r in metrics_rows
                    ),
                    "unique_positive_targets": len(
                        {
                            r["target_contract_hash"]
                            for r in outcomes.values()
                            if r["status"] == "mature" and r["value"] == 1
                        }
                    ),
                    "brier": metrics["system_brier"],
                    "gain_vs_follow": metrics["net_realized_gain"],
                    "source_queries": report["resource_spent"]["requests"],
                    "program_forecasts": len(report["calls"]),
                    "actual_model_calls": report["actual_model_calls"],
                    "E_determined": report["e_counts"].get("supported", 0)
                    + report["e_counts"].get("refuted", 0),
                    "E_statuses": report["e_counts"],
                    "attempt_statuses": dict(
                        Counter(r["status"] for r in report["attempts"])
                    ),
                    "resource_spent": report["resource_spent"],
                    "resource_reserved": report["resource_reserved"],
                    "change_counts": dict(changes),
                    "missingness_bounds": metrics["full_population_gain_bounds"],
                    "missingness_strata": metrics["strata"],
                    "source_report_sha256": sha(path),
                }
                totals.append(item)
                group_rows[arm] = item
            for arm in ("P06_qp", "P06_qs", "P06_gp", "P06_gs"):
                assert group_rows[arm]["selector"] == "round_robin"
            for measure in ("E_determined", "gain_vs_follow", "source_queries"):
                qp, qs, gp, gs = [
                    group_rows[a][measure]
                    for a in ("P06_qp", "P06_qs", "P06_gp", "P06_gs")
                ]
                effects.append(
                    {
                        "group": group,
                        "measure": measure,
                        "sharing_under_fixed_quota": qs - qp,
                        "sharing_under_global_budget": gs - gp,
                        "global_allocation_under_private": gp - qp,
                        "global_allocation_under_shared": gs - qs,
                        "interaction": (gs - gp) - (qs - qp),
                        "interpretation": "Descriptive fixed-selector2x2 contrast on one exposed day; no independent confidence interval.",
                    }
                )
    save("ARMS.json", totals)
    save("FACTORIAL_CONTRASTS.json", effects)
    fields = [
        "group",
        "arm",
        "opportunities",
        "settled",
        "positive_opportunities",
        "unique_positive_targets",
        "brier",
        "gain_vs_follow",
        "source_queries",
        "E_determined",
        "program_forecasts",
        "actual_model_calls",
    ]
    with (OUT / "ARMS.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(totals)
    save(
        "VALIDATION.json",
        {
            "passed": True,
            "program_arm_runs": len(totals),
            "registered_opportunities_per_arm": 216,
            "all_metrics_match_independent_scores": True,
            "model_calls": 0,
            "source_audit_sha256": sha(audit_root / "BATCH_COMPLETE.json"),
            "scope": "Posthoc full-denominator descriptive decomposition of the original72-query public-schedule program experiment. Separate from the48-query measured-model-clock adaptive experiment; do not pool them for LLM effect claims.",
            "independent_confirmation": False,
        },
    )
    print(
        json.dumps(
            {
                "arms": len(totals),
                "all_metrics_match": True,
                "groups": [
                    {
                        "group": r["group"],
                        "follow_brier": r["brier"],
                        "positive_opportunities": r["positive_opportunities"],
                        "unique_positive_targets": r["unique_positive_targets"],
                    }
                    for r in totals
                    if r["arm"] == "P00_follow"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
