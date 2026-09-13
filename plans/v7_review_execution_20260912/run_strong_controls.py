"""Cheap full-update baselines and exact joint E references for disjoint hourly slots."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.evidence import sufficient_recipes
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.reachability import (
    Goal,
    Query,
    Witness,
    solve_joint,
    validate_witness,
)
from disastertrace.monitoring_v1.resources import Cost
from run_programs import score

BASE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def joint_reference(data, budget, threshold):
    products = {q["query_id"]: q for q in data["query_results"]}
    catalog = {q["query_id"]: q for q in data["query_catalog"]}
    cutoffs = sorted({p["deadline"] for p in data["e_f_pairs"]})
    seen_queries, local_records, all_queries, all_goals = set(), [], [], []
    # Full solutions are tractable here because registered report slots do not
    # recur across cutoffs. This decomposition is not a generic scheduling solver.
    states = {0: (0.0, ())}
    for tick, cutoff in enumerate(cutoffs):
        pairs = [p for p in data["e_f_pairs"] if p["deadline"] == cutoff]
        qids = {q for p in pairs for q in p["query_ids"]}
        if seen_queries & qids:
            raise ValueError("Hourly decomposition invalid: query shared across cutoffs")
        seen_queries.update(qids)
        queries = [Query(q, Cost(requests=1, bytes=catalog[q]["upper_bytes"], compute_ms=100),
                         catalog[q]["available_at"], catalog[q]["latency_ms"] * 1000) for q in sorted(qids)]
        goals = [Goal(p["opportunity_id"], cutoff, sufficient_recipes(p["query_ids"], products, threshold)) for p in pairs]
        start = cutoff - 600 * 1_000_000
        local = solve_joint(queries, goals, {"requests": len(qids)}, start=start, concurrency=1)
        if not local.exact:
            raise ValueError("Small hourly graph unexpectedly not exact")
        for witness in local.frontier:
            validate_witness(witness, queries, goals, {"requests": len(qids)}, start=start, concurrency=1)
        local_records.append({"cutoff": cutoff, "clock_unit": "UTC_microseconds", "reference": asdict(local)})
        credit = budget * (tick + 1) // len(cutoffs)
        updated = {}
        for used, (value, chosen) in states.items():
            for witness in local.frontier:
                cost = used + witness.cost.requests
                utility = value + len(witness.resolved)
                if cost <= credit and (cost not in updated or utility > updated[cost][0]):
                    updated[cost] = (utility, chosen + (witness,))
        states = updated
        all_queries.extend(queries)
        all_goals.extend(goals)
    best_cost, (value, choices) = max(states.items(), key=lambda pair: (pair[1][0], -pair[0]))
    total = Cost()
    for choice in choices:
        total += choice.cost
    starts = tuple(s for choice in choices for s in choice.starts)
    combined = Witness(starts, tuple(sorted(r for choice in choices for r in choice.resolved)), total,
                       max((s[2] for s in starts), default=cutoffs[0] - 600 * 1_000_000))
    limits = {"requests": budget, "bytes": budget * 2048, "compute_ms": budget * 100}
    validate_witness(combined, all_queries, all_goals, limits, concurrency=1,
                     start=cutoffs[0] - 600 * 1_000_000)
    if len(combined.resolved) != value or total.requests != best_cost:
        raise ValueError("Joint dynamic-program witness does not attain the stated utility")
    return {"exact": True, "scope": "B11 E acquisition only; same public calendar pacing; disjoint registered hourly queries; no F-utility or model-inference optimum claim",
            "limits": limits, "concurrency": 1, "joint_E_utility": value,
            "witness": asdict(combined), "hourly_references": local_records,
            "remaining_dp_states": len(states), "full_opportunities": len(data["opportunities"])}


def main(args):
    output = args.output
    output.mkdir(exist_ok=False)
    source_package = Path(run_session.__code__.co_filename).resolve().parent
    shutil.copytree(source_package, output / "implementation/monitoring_v1", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(Path(__file__), output / "implementation/run_strong_controls.py")
    bank = json.loads(args.bank.read_text())
    reports = {}
    configurations = []
    for budget in (args.hours, args.hours * 2, args.hours * 3):
        for selector in ("round_robin", "risk", "coverage", "batch_complete"):
            for protocol in ("base_bound_override", "persistent_override"):
                configurations.append({"seed": 20260912, "request_budget": budget,
                    "forecast_call_cap": args.hours * 9, "per_tick_forecast_cap": 9,
                    "input_token_cap": 8192, "output_token_cap": 384, "call_compute_cap_ms": 120000,
                    "wakeup_seconds": 600, "token_cap": args.hours * 2 * (8192 + 384),
                    "compute_ms_cap": args.hours * 2 * 120000 + budget * 100,
                    "selector_kind": selector, "isolation_mode": "actual_cost_clock",
                    "allocation_mode": "global_budget", "authorization_mode": "session_shared",
                    "protocol": protocol, "candidate_cap_is_not_model_call_budget": True,
                    "program_cost_note": "Fixed-count lookup program has no model tokens and may update every target; 1ms per update is an archive accounting assumption"})
    write(output / "CONFIGURATIONS.json", configurations)
    for threshold in (1000, 5000):
        data = load_session(args.dataset, stations=args.stations, hours=args.hours, threshold=threshold)
        for budget in (args.hours, args.hours * 2, args.hours * 3):
            reference = joint_reference(data, budget, threshold)
            write(output / f"t{threshold}-budget{budget}-JOINT.json", reference)
        for i, config in enumerate(configurations):
            ident = f"t{threshold}-arm{i:02d}"
            trace = run_session(data, bank, config)
            if len(trace["snapshots"]) != len(data["opportunities"]):
                raise ValueError("Missing strong-baseline opportunities")
            write(output / (ident + "-TRACE.json"), trace)
            outcomes = json.loads((args.dataset / "private/OUTCOMES.json").read_text())
            reports[ident] = {"config": config, "scores": score(trace, outcomes),
                              "actual_model_calls": 0, "cheap_program_updates": len(trace["calls"])}
            print(ident, config["selector_kind"], config["request_budget"], trace["e_counts"], flush=True)
    write(output / "SUMMARY.json", {"finished_at": datetime.now(timezone.utc).isoformat(),
        "data_audit_sha256": hashlib.sha256((args.dataset / "REGIONAL_JOIN_AUDIT.json").read_bytes()).hexdigest(),
        "bank_sha256": hashlib.sha256(args.bank.read_bytes()).hexdigest(), "runs": reports,
        "interpretation": "Stronger full-update CPU baselines; extra inference is not charged as LLM calls; whole-session E reference is a finite archive oracle under declared query-only constraints"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=BASE / "regional_02")
    parser.add_argument("--bank", type=Path, default=BASE / "calibration_bank_01/BANK.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--stations", nargs="+", default=["KSFO", "KOAK", "KSJC"])
    main(parser.parse_args())
