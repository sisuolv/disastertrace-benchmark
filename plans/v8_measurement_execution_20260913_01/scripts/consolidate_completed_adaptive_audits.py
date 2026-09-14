"""Score immutable incremental audits separately while the original audit runs."""

import datetime as dt
import hashlib
import json
import shutil
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import score_admitted
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract

HERE = Path(__file__).resolve().parents[1]
BATCH = HERE / "gpu/adaptive_large_02"
AUDIT = BATCH / "audit_incremental_01"
OUT = BATCH / "audit_consolidated_01"
DEADLINE = dt.datetime(2026, 9, 14, 2, 30, tzinfo=dt.timezone.utc)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def now():
    return dt.datetime.now(dt.timezone.utc)


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    plan = read(BATCH / "PLAN.json")
    plan_sha = sha(BATCH / "PLAN.json")
    for name, expected in plan["files"].items():
        if sha(BATCH / name) != expected:
            raise ValueError("Changed frozen file: " + name)
    if sha(AUDIT / "verify_adaptive.py") != sha(BATCH / "source/verify_adaptive.py"):
        raise ValueError("Incremental verifier differs from the original freeze")
    save(
        OUT / "STARTED.json",
        {
            "at": now().isoformat(),
            "deadline": DEADLINE.isoformat(),
            "plan_sha256": plan_sha,
            "verifier_sha256": sha(AUDIT / "verify_adaptive.py"),
            "new_model_calls": 0,
            "scope": "Supplementary original-scorer aggregation of successful, immutable per-case audits. No original audit is disabled, overwritten or counted as complete by this process.",
        },
    )
    rows, bindings, groups = {}, {}, set()
    while now() < DEADLINE:
        for case in plan["cases"]:
            ident = case["id"]
            exit_path = AUDIT / (ident + ".exit.json")
            if ident in rows or not exit_path.exists():
                continue
            if read(exit_path)["exit_code"] != 0:
                continue
            source = AUDIT / ident
            validation = read(source / "VALIDATION.json")
            if validation["status"] != "qualified":
                continue
            run = BATCH / "runs" / ident
            if not (run / "COMPLETE.json").is_file():
                raise ValueError("An incremental qualified session is unfinished")
            for path, expected in (
                (run / "REPORT.json", validation["source_report_sha256"]),
                (run / "FINAL_CHECKPOINT.json", validation["checkpoint_sha256"]),
                (source / "admission_reconstructed.jsonl", validation["admission_journal_sha256"]),
            ):
                if sha(path) != expected:
                    raise ValueError("Changed qualified audit input: " + str(path))
            destination = OUT / ident
            destination.mkdir(exist_ok=False)
            bindings[ident] = {}
            for name in ("VALIDATION.json", "RECEIPTS.json", "admission_reconstructed.jsonl"):
                expected = sha(source / name)
                shutil.copyfile(source / name, destination / name)
                if sha(destination / name) != expected:
                    raise ValueError("Changed copied audit artifact")
                bindings[ident][name] = expected
            bindings[ident]["original_case_exit_sha256"] = sha(exit_path)
            rows[ident] = validation
        for group_id in sorted({case["data_case"] for case in plan["cases"]}):
            cases = [case for case in plan["cases"] if case["data_case"] == group_id]
            if group_id in groups or not all(case["id"] in rows for case in cases):
                continue
            source = BATCH / "cases" / group_id
            contract = read(source / "COMPARISON.json")["payload"]
            paths = {
                case["arm"]: OUT / case["id"] / "admission_reconstructed.jsonl"
                for case in cases
            }
            save(OUT / (group_id + "_STARTED.json"), {"at": now().isoformat()})
            result = score_admitted(
                read(source / "OUTCOMES.json"),
                paths,
                comparison=ComparisonContract(contract["invariants"], contract["allowed_interventions"]),
            )
            save(
                OUT / (group_id + "_SCORES.json"),
                {
                    "expected_arms": [case["arm"] for case in cases],
                    "qualified_arms": list(paths),
                    "unqualified_arms": [],
                    "full_comparison_qualified": True,
                    "scores": result,
                },
            )
            groups.add(group_id)
            print(json.dumps({"group": group_id, "completed_groups": len(groups), "at": now().isoformat()}), flush=True)
        if len(groups) == len({case["data_case"] for case in plan["cases"]}) and (BATCH / "COMPLETE.json").exists():
            break
        time.sleep(min(15, max(0, (DEADLINE - now()).total_seconds())))
    save(OUT / "SOURCE_BINDINGS.json", bindings)
    if len(groups) != len({case["data_case"] for case in plan["cases"]}):
        save(OUT / "STOPPED.json", {"at": now().isoformat(), "complete_groups": sorted(groups), "reason": "No incomplete group is promoted to a full comparison"})
        return
    completion = read(BATCH / "COMPLETE.json")
    intents = [item for path in BATCH.glob("BATCH_*_INTENT.json") for item in read(path)["calls"]]
    identities = {(row["case"], row["call_id"]) for row in intents}
    actual = sum(row["actual_model_calls"] for row in rows.values())
    if not (completion["all_controller_exits_zero"] and actual == completion["actual_model_calls"] == len(identities) == len(intents) <= plan["model_call_ceiling"]):
        raise ValueError("Full original invocation count mismatch")
    if sha(BATCH / "PLAN.json") != plan_sha:
        raise ValueError("Frozen plan changed during aggregation")
    save(
        OUT / "VALIDATION.json",
        {
            "plan_sha256": plan_sha,
            "all_sessions_qualified": True,
            "registered_sessions": len(plan["cases"]),
            "expected_opportunity_rows": sum(case["opportunities"] for case in plan["cases"]),
            "sessions": [rows[case["id"]] for case in plan["cases"]],
            "audited_actual_model_calls": actual,
            "issued_model_calls": len(intents),
            "unique_generation_batch_seconds": sum(read(path)["compute_seconds"] for path in BATCH.glob("BATCH_*_COMPLETE.json")),
            "engineering_rehearsal": False,
            "independent_confirmation": False,
            "origin": "Separate aggregation using the original frozen scorer and hash-bound successful incremental case audits; original audit_01 remains independently authoritative when complete.",
            "timing_limitations": plan["timing"],
        },
    )
    save(OUT / "COMPLETE.json", {"at": now().isoformat(), "all_groups_qualified": True, "new_model_calls": 0})
    print(json.dumps({"all_groups_qualified": True, "model_calls_reconciled": actual}), flush=True)


if __name__ == "__main__":
    main()
