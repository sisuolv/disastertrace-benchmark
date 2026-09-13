"""Fresh-process continuation of one real archive prefix, four legal controls."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.targets import canonical_hash
from execute_admission import MATRIX, ROOT, save


def worker(spec, output):
    record = json.loads(spec.read_text())
    session = SessionCoordinator.restore(
        record["snapshot"], record["data"], record["bank"]
    )
    for _ in range(record["steps"]):
        session.step(record["controls"])
    save(
        output,
        {
            "report": session.report,
            "snapshot": session.snapshot(),
            "worker_pid": os.getpid(),
        },
    )


def main(out):
    out.mkdir(exist_ok=False, parents=True)
    data = load_session(
        ROOT / "plans/v7_review_execution_20260912/extension_bay_area_01",
        stations=["KSFO", "KOAK", "KSJC"],
        hours=3,
        threshold=5000,
    )
    bank = json.loads((MATRIX / "BANK.json").read_text())
    config = {
        "seed": 20260913,
        "request_budget": 9,
        "forecast_call_cap": 18,
        "per_tick_forecast_cap": 6,
        "input_token_cap": 8192,
        "output_token_cap": 384,
        "call_compute_cap_ms": 120000,
        "wakeup_seconds": 600,
        "token_cap": 18 * 8576,
        "compute_ms_cap": 18 * 120100,
        "selector_kind": "coverage",
        "isolation_mode": "actual_cost_clock",
        "allocation_mode": "global_budget",
        "authorization_mode": "session_shared",
        "protocol": "base_bound_override",
    }
    baseline = run_session(data, bank, config)
    prefix = SessionCoordinator(data, bank, config)
    prefix.step()
    snapshot = prefix.snapshot()
    save(out / "PREFIX_SNAPSHOT.json", snapshot)
    definitions = {
        "original_continuation": {},
        "wait": {"acquire": False, "predict": False},
        "one_report_per_tick": {"query_limit_per_tick": 1},
        "complete_batch": {"selector_kind": "batch_complete"},
    }
    save(
        out / "BRANCH_DEFINITIONS.json",
        {
            "steps": 2,
            "branches": definitions,
            "no_new_model_calls": True,
            "nonexistent_tool_branch": "not_evaluated; no registered same-input tool result",
        },
    )
    branch_results, commands = {}, []
    for name, control in definitions.items():
        spec = out / (name + "-input.json")
        result_file = out / (name + "-result.json")
        save(
            spec,
            {
                "snapshot": snapshot,
                "data": data,
                "bank": bank,
                "steps": 2,
                "controls": control,
            },
        )
        argv = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker-spec",
            str(spec.resolve()),
            "--output",
            str(result_file.resolve()),
        ]
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=90, check=False
        )
        commands.append(
            {
                "argv": argv,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode:
            save(out / "FAILED_COMMANDS.json", commands)
            result.check_returncode()
        record = json.loads(result_file.read_text())
        if record["worker_pid"] == os.getpid():
            raise ValueError("Recovery did not cross processes")
        if name == "original_continuation" and record["report"] != baseline:
            raise ValueError("No-change continuation differs from uninterrupted run")
        past = snapshot["payload"]["controller"]
        report = record["report"]
        if (
            report["frames"][: len(past["frames"])] != past["frames"]
            or report["calls"][: len(past["call_records"])] != past["call_records"]
            or report["resource_events"][: len(snapshot["payload"]["ledger"]["events"])]
            != snapshot["payload"]["ledger"]["events"]
        ):
            raise ValueError("Branch changed prefix or recharged inherited receipts")
        branch_results[name] = {
            "worker_pid": record["worker_pid"],
            "resource_spent": report["resource_spent"],
            "snapshots": len(report["snapshots"]),
            "program_calls": len(report["calls"]),
            "e_counts": report["e_counts"],
            "event_replay_sha256": report["event_replay"]["sha256"],
        }
    if canonical_hash(prefix.snapshot()["payload"]) != snapshot["sha256"]:
        raise ValueError("Branches mutated original state")
    report = {
        "schema": "disastertrace.quiescent_branch_report.v1",
        "real_source": "archived IEM TAF/METAR",
        "branches": branch_results,
        "prefix_cost_counted_once": True,
        "cross_process_restore": True,
        "no_change_full_report_equals_uninterrupted": True,
        "branch_cache_and_resources_isolated": True,
        "real_model_calls": 0,
        "inflight_restore_qualified": False,
        "steps_after_prefix": 2,
        "engine_scope": "existing aviation controller using the common clock; typed fixed admission separately qualified",
        "D_preparation_state_in_snapshot": False,
        "scientific_gain_claim": False,
    }
    save(out / "QUIESCENT_BRANCH_REPORT.json", report)
    save(out / "COMMANDS.json", commands)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker-spec", type=Path)
    args = parser.parse_args()
    if args.worker_spec:
        worker(args.worker_spec, args.output)
    else:
        main(args.output)
