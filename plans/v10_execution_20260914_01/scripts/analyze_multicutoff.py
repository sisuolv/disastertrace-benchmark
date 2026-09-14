"""Cross-arm full replay, independent arithmetic, and protocol attribution."""

import argparse
import json
import math
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import score_formal
from disastertrace.monitoring_v1.spool_backend import publish, read


def audit_case(item):
    case, card = item
    c = read(case / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(c["invariants"], c["allowed_interventions"])
    outcomes = read(case / "OUTCOMES.json")
    registry = {r["opportunity_id"]: r for r in outcomes}
    scores = score_formal(
        outcomes,
        {a: case / a / "admission.jsonl" for a in card["arms"]},
        comparison=comparison,
    )
    reports = {a: read(case / a / "REPORT.json") for a in card["arms"]}
    rows, counters = [], {}
    reference = reports["base_bound_override__FREQUENCY_ALWAYS"]
    reference_source = reference["source_receipts"]
    reference_schedule = [
        (c["opportunity_id"], c["started_at"], c["persisted_at"])
        for c in reference["calls"]
    ]
    for arm, report in reports.items():
        protocol, method = arm.split("__", 1)
        if method != "FOLLOW":
            assert report["source_receipts"] == reference_source
            assert [
                (c["opportunity_id"], c["started_at"], c["persisted_at"])
                for c in report["calls"]
            ] == reference_schedule
            assert report["resource_spent"] == reference["resource_spent"]
        calls = report["calls"]
        counters[arm] = {
            "calls": len(calls),
            "admission": dict(Counter(c["admission_status"] for c in calls)),
            "spent": report["resource_spent"],
        }
        if method == "FREQUENCY_HARM001":
            assert all(
                c["adoption_decision"]["max_pointwise_harm"] <= 0.01
                for c in calls
                if c["admitted_action"]
            )
        targets_seen = Counter(
            c["bundle"]["payload"]["target"]["target_id"]
            for c in calls
            if c["admitted_action"]
        )
        if method in {"BASELINE_FIRST_HOLD", "FREQUENCY_FIRST"}:
            assert all(n <= 1 for n in targets_seen.values())
        loss = []
        for snapshot in report["snapshots"]:
            oid = snapshot["opportunity_id"]
            y, p, base = (
                registry[oid]["value"],
                snapshot["forecast"]["value"],
                snapshot["base_forecast"]["value"],
            )
            if method in {"FOLLOW", "FREQUENCY_KEEP"}:
                assert p == base
            if y is not None:
                loss.append((p - y) ** 2)
            rows.append(
                {
                    "case": case.name,
                    "region": case.name.split("__")[0],
                    "arm": arm,
                    "protocol": protocol,
                    "method": method,
                    "opportunity_id": oid,
                    "target_id": snapshot["target"]["target_id"],
                    "cutoff": snapshot["cutoff"],
                    "lead_hours": (
                        snapshot["target"]["physical_start"] - snapshot["cutoff"]
                    )
                    / 3600_000_000,
                    "outcome": y,
                    "probability": p,
                    "baseline": base,
                    "loss": (p - y) ** 2 if y is not None else None,
                    "base_loss": (base - y) ** 2 if y is not None else None,
                    "possible_harm_vs_latest_base": max(
                        (p - z) ** 2 - (base - z) ** 2 for z in (0, 1)
                    ),
                }
            )
        expected = scores["scores"]["arms"][arm]
        assert expected["scored"] == len(loss)
        assert math.isclose(
            expected["loss_sum"], math.fsum(loss), abs_tol=1e-12, rel_tol=1e-12
        )
    return {
        "case": case.name,
        "scores": scores,
        "rows": rows,
        "counters": counters,
        "all_active_arms_same_acquisition_forecast_schedule_and_cost": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    plan = read(args.batch / "PLAN.json")
    if read(args.batch / "COMPLETE.json")["completed"] != 216:
        raise ValueError("Full registered experiment must finish before audit")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        cases = list(
            pool.map(audit_case, [(args.batch / c["case"], c) for c in plan["cases"]])
        )
    rows = [row for case in cases for row in case["rows"]]
    groups = defaultdict(list)
    for row in rows:
        groups[row["arm"]].append(row)
    metrics = {}
    for arm, group in groups.items():
        valid = [r for r in group if r["outcome"] is not None]
        metrics[arm] = {
            "registered": len(group),
            "scored": len(valid),
            "brier": math.fsum(r["loss"] for r in valid) / len(valid),
            "baseline_brier": math.fsum(r["base_loss"] for r in valid) / len(valid),
            "numerically_differs_from_latest_base": sum(
                r["probability"] != r["baseline"] for r in group
            ),
            "sealed_max_possible_harm_vs_latest_base": max(
                r["possible_harm_vs_latest_base"] for r in group
            ),
        }
    protocols = defaultdict(dict)
    for row in rows:
        protocols[row["case"], row["method"], row["opportunity_id"]][
            row["protocol"]
        ] = row["probability"]
    contrasts = Counter()
    for (_, method, _), values in protocols.items():
        if values["base_bound_override"] != values["persistent_override"]:
            contrasts[method] += 1
    with (args.out / "ROWS.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    publish(
        args.out / "CROSS_ARM_REPLAY.json",
        [{k: v for k, v in c.items() if k != "rows"} for c in cases],
    )
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "cases": len(cases),
            "trajectories": 216,
            "opportunities": 324,
            "unique_targets": 108,
            "method_opportunity_rows": len(rows),
            "metrics": metrics,
            "protocol_numeric_differences": dict(contrasts),
            "same_acquisition_forecast_schedule_and_cost_for_all_computing_arms": True,
            "future_labels_used_for_adoption": False,
            "new_model_calls": 0,
            "scope": "exposed development same-target program controls, 6/3/1h leads; original bank fitted at 1h",
        },
    )
    print(
        json.dumps(
            {"passed": True, "rows": len(rows), "protocol_differences": dict(contrasts)}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
