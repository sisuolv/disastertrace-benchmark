"""Real-data program controls; preserve every opportunity and both wrappers."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.evidence import sufficient_recipes
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.reachability import Goal, Query, solve_joint, validate_witness
from disastertrace.monitoring_v1.resources import Cost
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.state import MonitoringEngine
from disastertrace.monitoring_v1.targets import canonical_hash


ROOT = Path(__file__).resolve().parent


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def score(trace, private_outcomes):
    outcomes = {r["target_id"]: r for r in private_outcomes}
    rows = [{"opportunity_id": r["opportunity_id"], "base": r["base_probability"], "prediction": r["probability"],
             "outcome": outcomes[r["target_id"]]["outcome"], "region": "bay_area",
             "period": str(r["cutoff"] // 86_400_000_000), "source": "native_metar",
             "quality": outcomes[r["target_id"]]["status"], "maturity": "final_archive", "baseline_kind": r["baseline_kind"]}
            for r in trace["snapshots"]]
    result = brier_report(rows)
    result.update(calls=len(trace["calls"]), e_counts=trace["e_counts"], resource_spent=trace["resource_spent"],
                  missing_snapshots=False, invalid_responses=sum(c["response_error"] is not None for c in trace["calls"]))
    return result


def main(dataset, bank_path, output, hours, sites):
    output.mkdir(parents=True, exist_ok=False)
    bank = json.loads(bank_path.read_text())
    stations = ["KSFO", "KOAK", "KSJC"][:sites]
    summaries, fixed_trace = {}, {}
    config = {"seed": 20260912, "request_budget": hours * 2, "forecast_call_cap": hours * 2,
              "per_tick_forecast_cap": 2, "input_token_cap": 8192, "output_token_cap": 384,
              "call_compute_cap_ms": 120000, "wakeup_seconds": 600,
              "token_cap": hours * 2 * (8192 + 384), "compute_ms_cap": hours * 2 * 120100,
              "selector_kind": "round_robin", "isolation_mode": "public_schedule", "public_call_slot_ms": 120000}
    configurations = []
    for allocation in ("fixed_quota", "global_budget"):
        for authorization in ("target_private", "session_shared"):
            for protocol in ("base_bound_override", "persistent_override"):
                configurations.append(dict(config, allocation_mode=allocation, authorization_mode=authorization, protocol=protocol))
    configurations.extend([
        dict(config, allocation_mode="global_budget", authorization_mode="session_shared", protocol="base_bound_override", predict=False, acquire=False, label="FOLLOW"),
        dict(config, allocation_mode="global_budget", authorization_mode="session_shared", protocol="base_bound_override", selector_kind="risk", isolation_mode="actual_cost_clock"),
        dict(config, allocation_mode="global_budget", authorization_mode="session_shared", protocol="base_bound_override", selector_kind="coverage", isolation_mode="actual_cost_clock"),
        dict(config, allocation_mode="global_budget", authorization_mode="session_shared", protocol="base_bound_override", selector_kind="risk", isolation_mode="actual_cost_clock", gate="capacity_revise_defer"),
        dict(config, allocation_mode="global_budget", authorization_mode="session_shared", protocol="base_bound_override", request_budget=hours * sites,
             token_cap=hours * sites * (8192 + 384), compute_ms_cap=hours * sites * 120100, isolation_mode="actual_cost_clock", label="batch_shared_nontight")])
    write(output / "CONFIGURATIONS.json", configurations)
    source_binding = {"bank_sha256": hashlib.sha256(bank_path.read_bytes()).hexdigest(),
                      "dataset_audit_sha256": hashlib.sha256((dataset / "REGIONAL_JOIN_AUDIT.json").read_bytes()).hexdigest()}
    for threshold in (1000, 5000):
        data = load_session(dataset, stations=stations, hours=hours, threshold=threshold)
        for index, arm in enumerate(configurations):
            run_id = f"t{threshold}-arm{index:02d}"
            trace = run_session(data, bank, arm)
            if len(trace["snapshots"]) != len(data["opportunities"]):
                raise ValueError("Policy lost opportunities")
            restored = MonitoringEngine.restore(trace["event_replay"])
            if list(restored.snapshots.values()) != trace["snapshots"]:
                raise ValueError("Deterministic event reconstruction mismatch")
            write(output / (run_id + "-TRACE.json"), trace)
            # Outcome access begins only after the policy trace has been sealed.
            private_outcomes = json.loads((dataset / "private/OUTCOMES.json").read_text())
            summaries[run_id] = {"config": arm, "scores": score(trace, private_outcomes)}
            if index < 8:
                counterfactual = deepcopy(trace["event_replay"])
                other = "persistent_override" if arm["protocol"] == "base_bound_override" else "base_bound_override"
                counterfactual["payload"]["protocol"] = other
                counterfactual["sha256"] = canonical_hash(counterfactual["payload"])
                reconstructed = MonitoringEngine.restore(counterfactual)
                alternate = dict(trace, snapshots=list(reconstructed.snapshots.values()))
                fixed_trace[run_id] = {"original_protocol": arm["protocol"], "alternate_protocol": other,
                    "original": summaries[run_id]["scores"], "alternate_fixed_candidates": score(alternate, private_outcomes),
                    "interpretation": "controlled direct wrapper comparison, not an independently adapted policy run"}
            print(run_id, len(trace["snapshots"]), len(trace["calls"]), trace["e_counts"], flush=True)
        pool = {q["query_id"]: q for q in data["query_results"]}
        reachability = []
        for cutoff in sorted({p["deadline"] for p in data["e_f_pairs"]}):
            pairs = [p for p in data["e_f_pairs"] if p["deadline"] == cutoff]
            qids = sorted({q for p in pairs for q in p["query_ids"]})
            graph_queries = [Query(q, Cost(requests=1), 0, 1) for q in qids]
            goals = [Goal(p["opportunity_id"], 10, sufficient_recipes(p["query_ids"], pool, threshold)) for p in pairs]
            for budget in (1, 2, 3):
                result = solve_joint(graph_queries, goals, {"requests": budget}, concurrency=2)
                for witness in result.frontier:
                    validate_witness(witness, graph_queries, goals, {"requests": budget}, concurrency=2)
                reachability.append({"cutoff": cutoff, "budget": budget, "reference": asdict(result)})
        write(output / f"t{threshold}-JOINT_REFERENCES.json", reachability)
    write(output / "SUMMARY.json", {"finished_at": datetime.now(timezone.utc).isoformat(), "bindings": source_binding,
        "hours": hours, "stations": stations, "runs": summaries, "fixed_trace_comparisons": fixed_trace,
        "gpu_model_calls": 0, "real_program_frequency_predictions": True,
        "limits": ["Exposed development", "Padded X01 isolation controls do not measure natural latency benefit",
                   "Clock-realistic shared baselines are separate arms", "No independent process-level confirmation"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("bank", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--hours", type=int, default=8)
    parser.add_argument("--sites", type=int, default=2)
    args = parser.parse_args()
    main(args.dataset, args.bank, args.output, args.hours, args.sites)
