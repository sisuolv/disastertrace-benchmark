"""Parallelize canonical journal replays; retain the original comparison scorer."""

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract

HERE = Path(__file__).resolve().parents[1]
BATCH = HERE / "gpu/adaptive_large_02"
OUTPUT = BATCH / "audit_parallel_recovery_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def replay(path):
    return path, AdmissionEngine.from_journal(path)


def main():
    if socket.gethostname() != "pt-45149fa42ad9486ba289a5491590e7ba-worker-0":
        raise ValueError("Only the existing allocated container is allowed")
    OUTPUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUTPUT / "EXECUTED_SOURCE.py")
    plan = read(BATCH / "PLAN.json")
    for name, expected in plan["files"].items():
        if sha(BATCH / name) != expected:
            raise ValueError("Frozen input changed")
    groups = ["1000__base_bound_override", "1000__persistent_override"]
    cases = [row for row in plan["cases"] if row["data_case"] in groups]
    paths, bindings = [], {}
    for case in cases:
        ident = case["id"]
        src = BATCH / "audit_incremental_01" / ident
        row = read(src / "VALIDATION.json")
        assert row["status"] == "qualified"
        assert read(src.parent / (ident + ".exit.json"))["exit_code"] == 0
        assert sha(BATCH / "runs" / ident / "REPORT.json") == row["source_report_sha256"]
        assert sha(BATCH / "runs" / ident / "FINAL_CHECKPOINT.json") == row["checkpoint_sha256"]
        assert sha(src / "admission_reconstructed.jsonl") == row["admission_journal_sha256"]
        dst = OUTPUT / case["data_case"] / ident
        dst.mkdir(parents=True, exist_ok=False)
        bindings[ident] = {}
        for name in ("VALIDATION.json", "RECEIPTS.json", "admission_reconstructed.jsonl"):
            shutil.copyfile(src / name, dst / name)
            assert sha(src / name) == sha(dst / name)
            bindings[ident][name] = sha(dst / name)
        paths.append(str(dst / "admission_reconstructed.jsonl"))
    save(OUTPUT / "STARTED.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "plan_sha256": sha(BATCH / "PLAN.json"),
        "processes": 26, "cpu_affinity": len(os.sched_getaffinity(0)),
        "new_gpu_jobs": 0, "new_model_calls": 0,
        "algorithm": "Run unmodified AdmissionEngine.from_journal once per input in 26 CPU processes, then reuse those exact engines inside unmodified score_admitted; compare a complete reference group against its prior serial canonical result.",
    })
    with concurrent.futures.ProcessPoolExecutor(max_workers=26) as executor:
        engines = dict(executor.map(replay, paths))
    original = AdmissionEngine.__dict__["from_journal"]
    AdmissionEngine.from_journal = classmethod(lambda cls, path: engines[str(path)])
    try:
        for group in groups:
            selected = [case for case in cases if case["data_case"] == group]
            card = read(BATCH / "cases" / group / "COMPARISON.json")["payload"]
            scores = score_admitted(
                read(BATCH / "cases" / group / "OUTCOMES.json"),
                {case["arm"]: OUTPUT / group / case["id"] / "admission_reconstructed.jsonl" for case in selected},
                comparison=ComparisonContract(card["invariants"], card["allowed_interventions"]),
            )
            value = {"expected_arms": [case["arm"] for case in selected], "qualified_arms": [case["arm"] for case in selected], "unqualified_arms": [], "full_comparison_qualified": True, "scores": scores}
            save(OUTPUT / group / "SCORES.json", value)
            prior = BATCH / "audit_parallel_scores_01" / group / "SCORES.json"
            if prior.exists() and read(prior) != value:
                raise ValueError("Parallel replay and original serial canonical score disagree")
            save(OUTPUT / group / "SOURCE_BINDINGS.json", {case["id"]: bindings[case["id"]] for case in selected})
    finally:
        AdmissionEngine.from_journal = original
    save(OUTPUT / "COMPLETE.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "all_groups_qualified": True, "reference_group_exact_agreement": "1000__persistent_override", "new_model_calls": 0})
    print("PARALLEL_REPLAY_RECOVERY_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
