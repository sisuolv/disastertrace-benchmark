"""Read original program journals with the qualified transaction optimization."""

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import score_admitted
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.journal import EventJournal, read_journal
from disastertrace.monitoring_v1.resources import BudgetLedger
from disastertrace.monitoring_v1.spool_backend import publish, read

HERE = Path(
    os.environ.get(
        "DISASTERTRACE_V8_EXECUTION_ROOT", Path(__file__).resolve().parents[1]
    )
)
SOURCE_BATCH = HERE / "reports/program_calendar_02"
OUT = HERE / "reports/program_calendar_optimized_audit_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(group):
    original = SOURCE_BATCH / group
    out = OUT / group
    out.mkdir(exist_ok=False)
    frozen = read(original / "FREEZE.json")
    for rel, expected in frozen["source"].items():
        assert (
            sha(
                original / "source" / Path(rel).relative_to("disastertrace-starter/src")
            )
            == expected
        )
    for name, expected in frozen["files"].items():
        assert fingerprint(read(original / name)) == expected
    arms = read(original / "CONFIGS.json")
    rows = []
    for arm in arms:
        directory = original / arm
        report = read(directory / "REPORT.json")
        assert read(directory / "VALIDATION.json")["replay_equal"]
        saved = report["event_replay"]
        assert fingerprint(saved["payload"]) == saved["sha256"]
        journal = read_journal(directory / "admission.jsonl")
        assert not journal.incomplete_tail
        assert journal.records[0]["payload"] == saved["payload"]["contract"]
        assert journal.records[-1]["payload"]["checkpoint_sha256"] == saved["sha256"]
        snapshots = {r["opportunity_id"]: r for r in report["snapshots"]}
        assert len(snapshots) == frozen["opportunities"] == len(report["snapshots"])
        assert fingerprint(snapshots) == saved["payload"]["snapshots_sha256"]
        assert fingerprint(report["attempts"]) == saved["payload"]["attempts_sha256"]
        with EventJournal(directory / "resources.jsonl") as resource_journal:
            ledger = BudgetLedger.restore(resource_journal)
            assert ledger.events == report["resource_events"]
            assert asdict(ledger.spent) == report["resource_spent"]
            assert asdict(ledger.reserved) == report["resource_reserved"]
        rows.append(
            {
                "arm": arm,
                "opportunities": len(snapshots),
                "spent": asdict(ledger.spent),
                "source_report_sha256": sha(directory / "REPORT.json"),
                "admission_journal_sha256": sha(directory / "admission.jsonl"),
                "resource_journal_sha256": sha(directory / "resources.jsonl"),
                "E_availability": report["e_counts"],
            }
        )
    comparison = read(original / "COMPARISON.json")["payload"]
    result = score_admitted(
        read(original / "OUTCOMES.json"),
        {arm: original / arm / "admission.jsonl" for arm in arms},
        comparison=ComparisonContract(
            comparison["invariants"], comparison["allowed_interventions"]
        ),
    )
    publish(out / "SCORES.json", result)
    publish(
        out / "VALIDATION.json",
        {
            "passed": True,
            "arms": rows,
            "group": group,
            "original_execution_source_unchanged": True,
            "original_journal_transactions_replayed": True,
            "scope": "Independent current-replayer audit of original program captures; original driver and its scorer remain untouched.",
            "new_model_calls": 0,
        },
    )
    print(json.dumps({"group": group, "passed": True}), flush=True)


def main():
    if len(sys.argv) > 1:
        audit(sys.argv[1])
        return
    OUT.mkdir(exist_ok=False)
    source = OUT / "source"
    shutil.copytree(HERE / "gpu/adaptive_large_01/source", source)
    shutil.copyfile(Path(__file__), source / "audit_program_results.py")
    groups = [
        str(t) + "__" + p
        for t in (1000, 5000)
        for p in ("base_bound_override", "persistent_override")
    ]
    publish(
        OUT / "PLAN.json",
        {
            "groups": groups,
            "original": str(SOURCE_BATCH),
            "source": {
                str(p.relative_to(source)): sha(p) for p in source.rglob("*.py")
            },
            "new_model_calls": 0,
            "condition": "All original arm reports and original per-arm replay receipts must exist; nothing is re-executed or overwritten.",
        },
    )

    def one(group):
        command = [sys.executable, str(source / "audit_program_results.py"), group]
        publish(OUT / (group + ".command.json"), {"command": command})
        with (OUT / (group + ".log")).open("x") as log:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(source),
                    DISASTERTRACE_V8_EXECUTION_ROOT=str(HERE),
                ),
            )
        publish(OUT / (group + ".exit.json"), {"exit_code": result.returncode})
        return result.returncode

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        exits = list(pool.map(one, groups))
    publish(
        OUT / "BATCH_COMPLETE.json",
        {
            "all_passed": not any(exits),
            "group_exit_codes": exits,
            "program_arm_runs": 40,
            "new_model_calls": 0,
            "original_execution_repeated": False,
        },
    )
    raise SystemExit(int(any(exits)))


if __name__ == "__main__":
    main()
