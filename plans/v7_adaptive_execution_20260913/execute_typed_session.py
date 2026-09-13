"""Real archive, paid evidence, typed heads, cutoff journals and branch recovery."""

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.journal import EventJournal
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.resources import BudgetLedger
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BANK = ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01/BANK.json"


def save(path, data):
    with path.open("x") as f:
        f.write(json.dumps(data, indent=2, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def config():
    return {
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
        "selector_kind": "round_robin",
        "isolation_mode": "public_schedule",
        "public_call_slot_ms": 30000,
        "allocation_mode": "global_budget",
        "authorization_mode": "session_shared",
        "protocol": "base_bound_override",
        "session_runtime": "typed_admission_v1",
        "typed_head": "joint",
        "persistence_latency_ms": 1,
    }


def verify_accounting(report):
    settled = {r["receipt_id"]: r for r in report["resource_events"] if r["event"] != "reserve"}
    sources = {r["receipt_id"]: r for r in report["source_receipts"]}
    bundle_receipts = set()
    for call in report["calls"]:
        bundle = EvidenceBundle.restore(call["bundle"])
        assert (
            native_slot_support(bundle, at=call["started_at"])["status"]
            == call["expected_e_from_disclosed_products"]
        )
        assert settled[call["call_id"]]["actual"] == call["receipt"]["cost"]
        for r in bundle.policy_view()["receipts"]:
            assert r["cost"] == settled[r["receipt_id"]]["actual"]
            assert (
                r["completed_at"] == sources[r["receipt_id"]]["completed_at"] <= call["started_at"]
            )
            bundle_receipts.add(r["receipt_id"])
    return {
        "calls": len(report["calls"]),
        "unique_acquisitions_exposed": len(bundle_receipts),
        "acquisitions_paid": len(sources),
        "resource_spent": report["resource_spent"],
        "admissions": dict(Counter(c["admission_status"] for c in report["calls"])),
    }


def worker(spec, output):
    row = json.loads(spec.read_text())
    session = SessionCoordinator.restore(row["snapshot"], row["data"], row["bank"])
    while not session.done:
        session.step(row["controls"])
    save(output, {"pid": os.getpid(), "report": session.report, "snapshot": session.snapshot()})


def main(dataset, out, hours):
    out.mkdir(parents=True, exist_ok=False)
    data = load_session(dataset, stations=["KSFO", "KOAK", "KSJC"], hours=hours, threshold=5000)
    bank, base_config = json.loads(BANK.read_text()), config()
    arms, reports, checks = {}, {}, {}
    save(out / "POLICY_ENVIRONMENT.json", data)
    save(out / "BANK.json", bank)
    configs = {}
    for allocation in ("fixed_quota", "global_budget"):
        for authorization in ("target_private", "session_shared"):
            name = allocation + "__" + authorization
            configs[name] = dict(
                base_config, allocation_mode=allocation, authorization_mode=authorization
            )
    configs["follow"] = dict(base_config, acquire=False, predict=False)
    configs["complete_batch"] = dict(base_config, selector_kind="batch_complete")
    save(out / "CONFIGS.json", configs)
    for name, settings in configs.items():
        path, ledger_path = out / (name + ".jsonl"), out / (name + "-resources.jsonl")
        with EventJournal(path) as journal, EventJournal(ledger_path) as resource_journal:
            report = run_session(
                data, bank, settings, journal=journal, resource_journal=resource_journal
            )
        restored = AdmissionEngine.from_journal(path)
        assert restored.export() == report["event_replay"]
        with EventJournal(ledger_path) as journal:
            resources = BudgetLedger.restore(journal)
            assert asdict(resources.spent) == report["resource_spent"]
        checks[name] = verify_accounting(report)
        reports[name], arms[name] = report, path
        save(out / (name + "-report.json"), report)
    prefix = SessionCoordinator(data, bank, base_config)
    prefix.step()
    snapshot = prefix.snapshot()
    save(out / "PREFIX.json", snapshot)
    branches = {
        "continue": {},
        "wait": {"acquire": False, "predict": False},
        "one_query": {"query_limit_per_tick": 1},
        "batch": {"selector_kind": "batch_complete"},
    }
    commands, branch_checks = [], {}
    for name, controls in branches.items():
        spec, result = out / (name + "-branch-input.json"), out / (name + "-branch-result.json")
        save(spec, {"snapshot": snapshot, "data": data, "bank": bank, "controls": controls})
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(spec.resolve()),
            "--output",
            str(result.resolve()),
        ]
        run = subprocess.run(command, text=True, capture_output=True, timeout=180, check=False)
        commands.append(
            {
                "argv": command,
                "returncode": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
            }
        )
        if run.returncode:
            save(out / "FAILED_COMMANDS.json", commands)
            run.check_returncode()
        record = json.loads(result.read_text())
        assert record["pid"] != os.getpid()
        report = record["report"]
        if name == "continue":
            assert report == reports["global_budget__session_shared"]
        prefix_calls = snapshot["payload"]["controller"]["call_records"]
        assert report["calls"][: len(prefix_calls)] == prefix_calls
        events = snapshot["payload"]["ledger"]["events"]
        assert report["resource_events"][: len(events)] == events
        restored = AdmissionEngine.restore(report["event_replay"])
        path = out / (name + "-branch.jsonl")
        restored.write_journal(path)
        arms["branch_" + name] = path
        branch_checks[name] = dict(verify_accounting(report), independent_pid=record["pid"])
    # Outcome loading happens only after every arm and branch is complete.
    outcomes = {
        o["target_id"]: o for o in json.loads((dataset / "private/OUTCOMES.json").read_text())
    }
    registry = AdmissionEngine.from_journal(next(iter(arms.values()))).opportunities
    reference = [
        {
            "opportunity_id": oid,
            "target_contract_hash": o.target.contract_hash,
            "value": outcomes[o.target.target_id]["outcome"],
            "status": "mature"
            if outcomes[o.target.target_id]["status"] == "settled_final_archived_report"
            else "missing",
            "source_revision": fingerprint(outcomes[o.target.target_id]),
        }
        for oid, o in registry.items()
    ]
    save(out / "OUTCOME_REFERENCES.json", reference)
    scores = score_admitted(reference, arms)
    save(out / "SCORES.json", scores)
    report = {
        "schema": "disastertrace.typed_adaptive_validation.v1",
        "dataset": str(dataset.resolve()),
        "opportunities": len(registry),
        "arms": checks,
        "branches": branch_checks,
        "native_acquisition_and_head_receipts_bound_to_ledger": True,
        "original_continuation_equals_uninterrupted_report": True,
        "fixed_selector_2x2": True,
        "prefix_charged_once": True,
        "single_clock": "monitoring_v1.event_loop.run_clock through AdmissionEngine",
        "new_model_calls": 0,
        "program_timing": "declared 1ms CPU program plus 1ms persistence, released in fixed 30s public slots",
        "time_basis": "declared_archive_scenario",
        "inflight_restore_qualified": False,
        "D_restore_qualified": False,
        "independent_scientific_confirmation": False,
    }
    save(out / "COMMANDS.json", commands)
    save(out / "REPORT.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=int, default=3)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.output)
    else:
        main(args.dataset, args.output, args.hours)
