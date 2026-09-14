"""Audit identical forecast slots and the allocation/sharing program factorial."""

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.audit_contracts import require_exact_ids
from disastertrace.monitoring_v1.formal_session import score_formal
from disastertrace.monitoring_v1.spool_backend import publish, read


def audit_case(pair):
    case, card = pair
    comp = read(case / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(comp["invariants"], comp["allowed_interventions"])
    outcomes = read(case / "OUTCOMES.json")
    scores = score_formal(
        outcomes,
        {a: case / a / "admission.jsonl" for a in card["arms"]},
        comparison=comparison,
    )
    registry = {r["opportunity_id"]: r for r in outcomes}
    reports = {arm: read(case / arm / "REPORT.json") for arm in card["arms"]}
    reference = reports["B11_COVERAGE"]
    fixed = [
        (c["opportunity_id"], c["started_at"], c["persisted_at"])
        for c in reference["calls"]
    ]
    rows, summary = [], {}
    for arm, report in reports.items():
        if arm != "FOLLOW":
            assert [
                (c["opportunity_id"], c["started_at"], c["persisted_at"])
                for c in report["calls"]
            ] == fixed
            assert not any(
                f["forecast_schedule"]["undispatched_opportunities"]
                for f in report["frames"]
            )
        require_exact_ids(
            registry,
            [s["opportunity_id"] for s in report["snapshots"]],
            scope=case.name + "/" + arm,
        )
        e = {
            oid: status
            for frame in report["frames"]
            for oid, status in frame["e_statuses"].items()
        }
        losses = []
        for snapshot in report["snapshots"]:
            oid = snapshot["opportunity_id"]
            p, y, base = (
                snapshot["forecast"]["value"],
                registry[oid]["value"],
                snapshot["base_forecast"]["value"],
            )
            loss = None if y is None else (p - y) ** 2
            if loss is not None:
                losses.append(loss)
            rows.append(
                {
                    "case": case.name,
                    "arm": arm,
                    "opportunity_id": oid,
                    "threshold_m": int(case.name.rsplit("__", 1)[1]),
                    "probability": p,
                    "outcome": y,
                    "baseline": base,
                    "e_status": e[oid],
                    "loss": loss,
                    "baseline_loss": None if y is None else (base - y) ** 2,
                }
            )
        expected = scores["scores"]["arms"][arm]
        assert expected["scored"] == len(losses)
        assert math.isclose(
            expected["loss_sum"], math.fsum(losses), abs_tol=1e-12, rel_tol=1e-12
        )
        summary[arm] = {
            "scored": len(losses),
            "loss_sum": math.fsum(losses),
            "E": dict(Counter(e.values())),
            "spent": report["resource_spent"],
            "calls": len(report["calls"]),
        }
    return {
        "case": case.name,
        "rows": rows,
        "metrics": summary,
        "full_journal_replay": True,
        "identical_forecast_targets_start_and_persistence_times": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    deadline = time.monotonic() + args.wait_seconds
    while not (args.batch / "COMPLETE.json").exists() and time.monotonic() < deadline:
        time.sleep(10)
    plan = read(args.batch / "PLAN.json")
    complete = read(args.batch / "COMPLETE.json")
    wanted = [c["case"] + "/" + a for c in plan["cases"] for a in c["arms"]]
    require_exact_ids(
        wanted,
        [r["case"] + "/" + r["arm"] for r in complete["results"]],
        scope="query-control trajectories",
    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        cases = list(
            pool.map(audit_case, [(args.batch / c["case"], c) for c in plan["cases"]])
        )
    rows = [row for case in cases for row in case["rows"]]
    groups, metrics = defaultdict(list), {}
    for row in rows:
        groups[row["threshold_m"], row["arm"]].append(row)
    for (threshold, arm), values in groups.items():
        valid = [r for r in values if r["loss"] is not None]
        metrics[str(threshold) + "__" + arm] = {
            "registered": len(values),
            "scored": len(valid),
            "positive": sum(r["outcome"] for r in valid),
            "brier": math.fsum(r["loss"] for r in valid) / len(valid),
            "baseline_brier": math.fsum(r["baseline_loss"] for r in valid) / len(valid),
            "E": dict(Counter(r["e_status"] for r in values)),
            "source_requests": sum(
                c["metrics"][arm]["spent"]["requests"]
                for c in cases
                if c["case"].endswith("__" + str(threshold))
            ),
        }
    with (args.out / "ROWS.jsonl").open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    publish(
        args.out / "CASE_AUDIT.json",
        [{k: v for k, v in c.items() if k != "rows"} for c in cases],
    )
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "cases": len(cases),
            "trajectories": len(wanted),
            "opportunities": plan["opportunities"],
            "method_opportunity_rows": len(rows),
            "metrics": metrics,
            "fixed_selector_for_factorial": "coverage",
            "same_scheduled_forecasts_verified": True,
            "interpretation": "program-only exposed development; simple allocation/sharing effects, not LLM superiority",
            "model_calls": 0,
            "confirmation_opened": False,
        },
    )


if __name__ == "__main__":
    main()
