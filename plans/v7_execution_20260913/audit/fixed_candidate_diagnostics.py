"""Post-hoc action sensitivity over recorded probabilities and completion times."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path

from audit_saved_traces import (
    COHORTS,
    PRIOR,
    REPO,
    direction,
    dump,
    independent_scores,
    read,
)
from disastertrace.monitoring_v1.state import MonitoringEngine
from disastertrace.monitoring_v1.targets import canonical_hash


def mutate_actions(replay, calls):
    changed = []
    replay = deepcopy(replay)
    for event in replay["payload"]["events"]:
        if event["kind"] != "candidate":
            continue
        call_id = event["payload"]["call_id"]
        row = calls[call_id]
        if row["valid_response"] and row["differs_from_base_at_start"] and row["decision"] != "override":
            if event["payload"]["probability"] != row["proposed_probability"]:
                raise ValueError("Candidate payload probability differs")
            event["payload"]["decision"] = "override"
            changed.append(call_id)
    replay["sha256"] = canonical_hash(replay["payload"])
    return replay, changed


def stability(rows, value, time):
    by_target = defaultdict(list)
    for row in rows:
        if row[value] is not None:
            by_target[row["target_id"]].append(row)
    changes = []
    for values in by_target.values():
        values = sorted(values, key=lambda r: r[time])
        changes.extend(abs(a[value] - b[value]) for a, b in pairwise(values))
    return {"targets": len(by_target), "adjacent_observed_transitions": len(changes),
            "nonconstant_transitions": sum(x > 1e-12 for x in changes),
            "total_absolute_change": math.fsum(changes),
            "mean_absolute_change": math.fsum(changes) / len(changes) if changes else None,
            "interpretation": "Outcome-blind descriptive stability; adjacent valid recorded calls or registered cutoffs only. A constant forecast can be stable and inaccurate."}


def run(args):
    args.audit = args.audit.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "schema": "disastertrace.fixed_candidate_action_diagnostic.v1",
        "declared_at": datetime.now(timezone.utc).isoformat(),
        "post_hoc_to_existing_results": True,
        "rule": "For each actually saved valid candidate whose probability differs from its captured call-start baseline, replace follow/no_change by override. Leave all other candidate actions and every probability/time/exogenous event unchanged.",
        "purpose": "Identify whether the recorded probability/action interface, rather than the wrapper alone, explains unused nonbaseline proposals.",
        "limits": "Not a new adaptive policy: the replay can alter later state but the recorded future outputs are not regenerated from that altered state. No candidate is created for an uncalled opportunity. No tuning from replay scores.",
        "new_model_calls": 0,
    }
    dump(args.output / "PROTOCOL.json", protocol)
    bindings = {}
    links_path = args.audit / "CALL_LINKS.jsonl"
    links_bytes = links_path.read_bytes()
    bindings[str(links_path.relative_to(REPO))] = hashlib.sha256(links_bytes).hexdigest()
    by_session, by_arm, cross_counts = defaultdict(dict), defaultdict(list), Counter()
    for line in links_bytes.splitlines():
        row = json.loads(line)
        by_session[row["session"]][row["call_id"]] = row
        by_arm[(row["cohort"], row["arm"])].append(row)
        cross_counts["E:" + row["expected_e"] + "->" + str(row["reported_e"])] += 1
        if row["actual_disclosed_mapping"]["probability"] != row["base_at_start"]:
            cross_counts["actual_evidence_mapping_changes_base"] += 1
        if row["differs_from_base_at_start"]:
            cross_counts["nonbase_proposal_action:" + row["decision"]] += 1
        if row["status"] == "accepted" and row["static_candidate_gain_vs_start_base_evaluator_only"] is not None:
            cross_counts["accepted_static_gain:" + direction(row["static_candidate_gain_vs_start_base_evaluator_only"])] += 1
    report, stability_report = {}, {}
    saved_bindings, digest = read(args.audit / "INPUT_BINDINGS.json")
    bindings[str((args.audit / "INPUT_BINDINGS.json").relative_to(REPO))] = digest
    saved_bindings = saved_bindings["sha256_by_repo_relative_path"]
    for cohort, (calendar, _, _) in COHORTS.items():
        rows_path = PRIOR / calendar / "ROWS.json"
        rows, digest = read(rows_path)
        bindings[str(rows_path.relative_to(REPO))] = digest
        if saved_bindings[str(rows_path.relative_to(REPO))] != digest:
            raise ValueError("Calendar changed after W0 audit")
        results = defaultdict(list)
        counts = defaultdict(Counter)
        for session, calls in by_session.items():
            first = next(iter(calls.values()))
            if first["cohort"] != cohort:
                continue
            arm = first["arm"]
            trace_path = REPO / session / "TRACE.json"
            trace, digest = read(trace_path)
            if saved_bindings[str(trace_path.relative_to(REPO))] != digest:
                raise ValueError("Trace changed after W0 audit")
            bindings[str(trace_path.relative_to(REPO))] = digest
            replay, changed = mutate_actions(trace["event_replay"], calls)
            counts[arm]["sessions"] += 1
            counts[arm]["changed_candidate_actions"] += len(changed)
            if changed:
                engine = MonitoringEngine.restore(replay)
                snapshots = list(engine.snapshots.values())
                counts[arm]["replayed_changed_sessions"] += 1
                counts[arm].update("replay_attempt:" + a["status"] for a in engine.attempts)
            else:
                snapshots = trace["snapshots"]
                counts[arm]["identical_sessions_no_replay_required"] += 1
            anchor = {r["opportunity_id"]: r for r in rows[arm]}
            originals = {r["opportunity_id"]: r for r in trace["snapshots"]}
            for s in snapshots:
                ref = anchor[s["opportunity_id"]]
                if s["base_probability"] != ref["base"] or s["target_id"] != ref["target_id"]:
                    raise ValueError("Replay changed common baseline or target")
                counts[arm]["changed_final_snapshots"] += s["probability"] != originals[s["opportunity_id"]]["probability"]
                results[arm].append(dict(ref, prediction=s["probability"]))
            print(cohort + ": " + session.split("/")[-1] + ": " + str(len(changed)) + " action changes", flush=True)
        report[cohort] = {}
        stability_report[cohort] = {}
        for arm, replay_rows in results.items():
            if len(replay_rows) != len(rows[arm]):
                raise ValueError("Incomplete replay cohort")
            original = independent_scores(rows[arm])
            revised = independent_scores(replay_rows)
            report[cohort][arm] = {"counts": dict(counts[arm]), "recorded_scores": original,
                                    "fixed_candidate_action_replay_scores": revised,
                                    "gain_vs_recorded_on_common_settled_mask": original["system_brier"] - revised["system_brier"]}
            call_rows = by_arm[(cohort, arm)]
            stability_report[cohort][arm] = {
                "recorded_valid_proposals": stability(call_rows, "proposed_probability", "started_at"),
                "recorded_cutoff_predictions": stability(rows[arm], "prediction", "cutoff"),
                "common_baseline_cutoffs": stability(rows[arm], "base", "cutoff"),
                "interpretation": "Proposal and cutoff sequences use different observation grids; their total variations are not a paired model improvement metric.",
            }
    for path in [Path(__file__), REPO / "disastertrace-starter/src/disastertrace/monitoring_v1/state.py"]:
        bindings[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    dump(args.output / "FIXED_CANDIDATE_ACTION_REPORT.json", {"protocol": protocol, "cohorts": report, "new_model_calls": 0})
    dump(args.output / "STABILITY_AND_INTERFACE.json", {"cross_counts": dict(cross_counts), "cohorts": stability_report, "new_model_calls": 0})
    dump(args.output / "INPUT_BINDINGS.json", {"sha256_by_repo_relative_path": bindings})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
