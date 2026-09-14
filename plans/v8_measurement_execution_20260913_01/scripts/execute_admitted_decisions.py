"""Replay fixed native F trajectories into separate synthetic D policies."""

import argparse
import copy
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, AdmissionEvent
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.decision_baselines import act
from disastertrace.monitoring_fixed_v1.decision_inputs import (
    choose_admitted_preparation,
)
from disastertrace.monitoring_v1.preparation import score_preparation

US = 1_000_000
MINUTE = 60 * US
METHODS = ("no_preparation", "threshold", "edf", "rolling_two_step")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def projection(engine):
    # Journal prefix hashes necessarily differ after adding D events.
    return {
        oid: {
            k: row[k]
            for k in (
                "target",
                "cutoff",
                "forecast",
                "base_forecast",
                "mode",
                "override_call_id",
            )
        }
        for oid, row in engine.snapshots.items()
    }


def fixed_source(report, target_time):
    source = report["event_replay"]["payload"]
    contract = copy.deepcopy(source["contract"])
    opportunities = [
        r
        for r in contract["opportunities"]
        if r["target"]["physical_start"] == target_time
    ]
    tids = {r["target"]["target_id"] for r in opportunities}
    assert len(tids) == 3 and len(opportunities) == 9
    events = [e for step in source["history"] for e in step["events"]]
    begins = {
        e["payload"]["call_id"]
        for e in events
        if e["kind"] == "begin"
        and e["payload"]["bundle"]["payload"]["target"]["target_id"] in tids
    }
    selected = []
    for event in events:
        kind, payload = event["kind"], event["payload"]
        if kind in {"baseline", "begin"}:
            keep = payload["bundle"]["payload"]["target"]["target_id"] in tids
        elif kind == "baseline_withdrawal":
            keep = payload["target_id"] in tids
        elif kind == "completion":
            keep = payload["call_id"] in begins
        else:
            raise ValueError("Unregistered source trace event kind")
        if keep:
            selected.append(event)
    assert len({e["event_id"] for e in selected}) == len(selected)
    contract.pop("experiment", None)
    contract["opportunities"] = opportunities
    contract["fallbacks"] = {tid: contract["fallbacks"][tid] for tid in tids}
    expected = {
        row["opportunity_id"]: {
            k: row[k]
            for k in (
                "target",
                "cutoff",
                "forecast",
                "base_forecast",
                "mode",
                "override_call_id",
            )
        }
        for row in report["snapshots"]
        if row["target"]["target_id"] in tids
    }
    return contract, selected, expected


def timeline(spec):
    groups = defaultdict(list)
    for event in spec["events"]:
        groups[event["time"]].append(event)
    for at in spec["decision_ticks"]:
        assert at + 1 not in groups
        groups[at]
    groups[spec["finish_at"]]
    return [(at, groups[at]) for at in sorted(groups)]


def finish(engine, spec, method, *, start=0, checkpoint_dir=None):
    decisions = []
    ticks = set(spec["decision_ticks"])
    for index, (at, events) in enumerate(timeline(spec)):
        if index < start:
            continue
        engine.run([AdmissionEvent(**e) for e in events], until=at)
        if at in ticks:
            decision = choose_admitted_preparation(
                engine,
                method=method,
                at=at,
                next_at=at + 15 * MINUTE,
                miss_penalty=spec["miss_penalty"],
            )
            decisions.append(decision)
            act(
                engine,
                decision["action"],
                decision["action_at"],
                event_id="D-" + str(at),
            )
            if at == spec["decision_ticks"][2] and checkpoint_dir is not None:
                save(checkpoint_dir / "BRANCH_CHECKPOINT.json", engine.export())
                save(
                    checkpoint_dir / "BRANCH_REQUEST.json",
                    {"spec": spec, "method": method, "next_index": index + 1},
                )
    return decisions


def continuation(directory):
    request = read(directory / "BRANCH_REQUEST.json")
    engine = AdmissionEngine.restore(read(directory / "BRANCH_CHECKPOINT.json"))
    decisions = finish(
        engine, request["spec"], request["method"], start=request["next_index"]
    )
    save(
        directory / "CONTINUATION.json",
        {
            "checkpoint": engine.export(),
            "preparation": engine.preparation.to_dict(),
            "decisions": decisions,
            "source_or_model_requests": 0,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--continue-from", type=Path)
    args = parser.parse_args()
    if args.continue_from is not None:
        continuation(args.continue_from)
        return
    execution, output = args.execution.resolve(), args.output.resolve()
    report_path = (
        execution
        / "gpu/adaptive_large_02/runs/5000__base_bound_override__A04_risk_program/REPORT.json"
    )
    audit_path = (
        execution
        / "gpu/adaptive_large_02/audit_incremental_01/5000__base_bound_override__A04_risk_program/VALIDATION.json"
    )
    audit = read(audit_path)
    assert audit["status"] == "qualified" and audit["source_report_sha256"] == sha(
        report_path
    )
    report = read(report_path)
    assert report["actual_model_calls"] == 0
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            execution.parents[1] / "disastertrace-starter/src/disastertrace" / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text(
        '"""Frozen admitted-F decision replay."""\n'
    )
    shutil.copyfile(Path(__file__), source / Path(__file__).name)
    specs = []
    for iso in (
        "2025-02-03T08:00:00+00:00",
        "2025-02-03T16:00:00+00:00",
        "2025-02-04T00:00:00+00:00",
    ):
        target_time = int(datetime.fromisoformat(iso).timestamp()) * US
        contract, events, expected = fixed_source(report, target_time)
        jobs = [
            {
                "job_id": "job-" + str(i),
                "target_id": tid,
                "deadline": target_time,
                "duration": 20 * MINUTE,
                "expires_at": target_time + 60 * MINUTE,
                "cost": 1,
                "cleanup_duration": 5 * MINUTE,
                "cleanup_cost": 1,
            }
            for i, tid in enumerate(sorted(contract["fallbacks"]))
        ]
        card = {
            "schema": "disastertrace.preparation_scenario.v1",
            "kind": "research_assumption",
            "capacity": 1,
            "budget": 6,
            "units": "synthetic_cost_units",
            "jobs": jobs,
        }
        spec = {
            "id": "target_" + str(target_time),
            "target_time_utc": iso,
            "contract": contract,
            "events": events,
            "expected_F": expected,
            "scenario": card,
            "miss_penalty": 20,
            "decision_ticks": [
                target_time - m * MINUTE for m in (90, 75, 60, 45, 30, 15)
            ],
            "finish_at": max(target_time + 61 * MINUTE, max(e["time"] for e in events)),
        }
        specs.append(spec)
    plan = {
        "schema": "disastertrace.native_fixed_F_decision_replay.v1",
        "scenarios": specs,
        "methods": METHODS,
        "source_report": str(report_path),
        "source_report_sha256": sha(report_path),
        "source_audit_sha256": sha(audit_path),
        "source": {str(p.relative_to(source)): sha(p) for p in source.rglob("*.py")},
        "selection": "Three fixed clock cohorts,08/16/24UTC,and all three stations,not selected by probability, outcome or model success.",
        "information": "All D policies consume the same already-captured program F stream at each actual replay time. Later events and outcomes are not decision input. No acquisition/predictor is rerun.",
        "scenario": "Synthetic costs, capacity, duration and readiness. This does not establish operational mitigation or a model-selected D policy.",
        "scope": "Conditional three-target D replay from one qualified original program session; full-session acquisition/model/D feedback is not enabled.",
        "new_model_calls": 0,
    }
    save(output / "PLAN.json", plan)
    results = []
    for spec in specs:
        no_D = AdmissionEngine._from_contract(spec["contract"])
        for at, events in timeline(spec):
            no_D.run([AdmissionEvent(**e) for e in events], until=at)
        assert projection(no_D) == spec["expected_F"]
        for method in METHODS:
            directory = output / (spec["id"] + "__" + method)
            directory.mkdir()
            contract = {**spec["contract"], "preparation": spec["scenario"]}
            engine = AdmissionEngine._from_contract(contract)
            decisions = finish(engine, spec, method, checkpoint_dir=directory)
            assert projection(engine) == spec["expected_F"]
            save(directory / "DECISIONS.json", decisions)
            save(directory / "FINAL_CHECKPOINT.json", engine.export())
            save(directory / "PREPARATION.json", engine.preparation.to_dict())
            engine.write_journal(directory / "admission.jsonl")
            replay = AdmissionEngine.from_journal(directory / "admission.jsonl")
            assert replay.export() == engine.export()
            assert replay.preparation.to_dict() == engine.preparation.to_dict()
            command = [
                sys.executable,
                str(source / Path(__file__).name),
                "--continue-from",
                str(directory),
            ]
            save(directory / "CONTINUATION_COMMAND.json", {"command": command})
            env = dict(
                os.environ,
                PYTHONPATH=str(source),
                PYTHONDONTWRITEBYTECODE="1",
                CUDA_VISIBLE_DEVICES="",
            )
            with (directory / "continuation.log").open("x") as log:
                process = subprocess.run(
                    command,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    check=False,
                )
            save(
                directory / "CONTINUATION_EXIT.json", {"exit_code": process.returncode}
            )
            assert process.returncode == 0
            resumed = read(directory / "CONTINUATION.json")
            assert resumed["checkpoint"] == engine.export()
            assert resumed["preparation"] == engine.preparation.to_dict()
            assert resumed["decisions"] == decisions[3:]
            synthetic = []
            for vector in itertools.product((0, 1), repeat=3):
                demands = dict(zip(sorted(engine.preparation.jobs), vector))
                synthetic.append(
                    {
                        "demands": demands,
                        "score": score_preparation(
                            engine.preparation,
                            demands,
                            miss_penalty=spec["miss_penalty"],
                        ),
                    }
                )
            save(directory / "SYNTHETIC_DEMAND_SCORES.json", synthetic)
            result = {
                "scenario": spec["id"],
                "method": method,
                "passed": True,
                "unchanged_F_opportunities": len(engine.snapshots),
                "decisions": len(decisions),
                "D_spent": engine.preparation.spent,
                "D_reserved": engine.preparation.reserved,
                "prepared_targets": sum(
                    s["ready"] for s in engine.preparation.snapshots.values()
                ),
                "distinct_probability_vectors": len(
                    {fingerprint(r["probabilities"]) for r in decisions}
                ),
                "journal_replay_equal": True,
                "separate_process_continuation_equal": True,
            }
            save(directory / "VALIDATION.json", result)
            results.append(result)
            print(json.dumps(result), flush=True)
    save(
        output / "VALIDATION.json",
        {
            "passed": True,
            "trajectories": len(results),
            "results": results,
            "native_unique_targets": 9,
            "native_unique_opportunities": 27,
            "repeated_method_opportunity_rows": 108,
            "synthetic_demand_settlements": 96,
            "real_weather_outcomes_read": False,
            "fixed_F_across_D_methods": True,
            "dynamic_current_F_decision_inputs": True,
            "new_source_requests": 0,
            "new_model_calls": 0,
            "independent_confirmation": False,
            "operational_mitigation": False,
        },
    )


if __name__ == "__main__":
    main()
