"""Run the unchanged canonical scorer for one independently audited group."""

import argparse
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
DEADLINE = dt.datetime(2026, 9, 14, 2, 30, tzinfo=dt.timezone.utc)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", required=True)
    args = parser.parse_args()
    plan = read(BATCH / "PLAN.json")
    cases = [row for row in plan["cases"] if row["data_case"] == args.group]
    if len(cases) != 13:
        raise ValueError("Expected a complete registered comparison group")
    output = BATCH / "audit_parallel_scores_01" / args.group
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), output / "EXECUTED_SOURCE.py")
    for name, expected in plan["files"].items():
        if sha(BATCH / name) != expected:
            raise ValueError("Changed frozen input: " + name)
    if sha(AUDIT / "verify_adaptive.py") != sha(BATCH / "source/verify_adaptive.py"):
        raise ValueError("Original incremental verifier differs")
    save(output / "STARTED.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "plan_sha256": sha(BATCH / "PLAN.json"), "new_model_calls": 0, "source": "Original per-case incremental audits; unchanged frozen canonical scorer."})
    while dt.datetime.now(dt.timezone.utc) < DEADLINE:
        exits = [AUDIT / (case["id"] + ".exit.json") for case in cases]
        if all(path.exists() and read(path)["exit_code"] == 0 for path in exits):
            break
        time.sleep(15)
    else:
        save(output / "STOPPED.json", {"reason": "Required original case audits not complete before deadline"})
        return
    bindings = {}
    for case in cases:
        ident = case["id"]
        source, run = AUDIT / ident, BATCH / "runs" / ident
        row = read(source / "VALIDATION.json")
        if row["status"] != "qualified" or not (run / "COMPLETE.json").exists():
            raise ValueError("Incomplete original session")
        for path, expected in (
            (run / "REPORT.json", row["source_report_sha256"]),
            (run / "FINAL_CHECKPOINT.json", row["checkpoint_sha256"]),
            (source / "admission_reconstructed.jsonl", row["admission_journal_sha256"]),
        ):
            if sha(path) != expected:
                raise ValueError("Changed qualified artifact: " + str(path))
        destination = output / ident
        destination.mkdir(exist_ok=False)
        bindings[ident] = {"original_case_exit_sha256": sha(AUDIT / (ident + ".exit.json"))}
        for name in ("VALIDATION.json", "RECEIPTS.json", "admission_reconstructed.jsonl"):
            digest = sha(source / name)
            shutil.copyfile(source / name, destination / name)
            if sha(destination / name) != digest:
                raise ValueError("Copied original audit differs")
            bindings[ident][name] = digest
    group = BATCH / "cases" / args.group
    contract = read(group / "COMPARISON.json")["payload"]
    save(output / "SCORING_STARTED.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    result = score_admitted(
        read(group / "OUTCOMES.json"),
        {case["arm"]: output / case["id"] / "admission_reconstructed.jsonl" for case in cases},
        comparison=ComparisonContract(contract["invariants"], contract["allowed_interventions"]),
    )
    save(output / "SCORES.json", {"expected_arms": [case["arm"] for case in cases], "qualified_arms": [case["arm"] for case in cases], "unqualified_arms": [], "full_comparison_qualified": True, "scores": result})
    save(output / "SOURCE_BINDINGS.json", bindings)
    save(output / "COMPLETE.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "group": args.group, "all_13_arms_qualified": True, "new_model_calls": 0, "scores_sha256": sha(output / "SCORES.json")})
    print(json.dumps({"group": args.group, "complete": True}), flush=True)


if __name__ == "__main__":
    main()
