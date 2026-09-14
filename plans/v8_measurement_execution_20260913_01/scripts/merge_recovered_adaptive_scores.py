"""Join four hash-bound canonical groups without re-running any model or scorer."""

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BATCH = HERE / "gpu/adaptive_large_02"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    base = BATCH / "audit_parallel_scores_01"
    recovery = BATCH / "audit_parallel_recovery_01"
    recovered = read(recovery / "COMPLETE.json")
    if not recovered["all_groups_qualified"] or recovered["reference_group_exact_agreement"] != "1000__persistent_override":
        raise ValueError("Parallel replay recovery reference not qualified")
    intent = read(HERE / "PARALLEL_REPLAY_RECOVERY_INTENT_01.json")
    if sha(recovery / "EXECUTED_SOURCE.py") != intent["script_sha256"]:
        raise ValueError("Parallel replay recovery source changed")
    plan = read(BATCH / "PLAN.json")
    completion = read(BATCH / "COMPLETE.json")
    plan_sha = sha(BATCH / "PLAN.json")
    launch = read(base / "LAUNCHED.json")
    groups = sorted({case["data_case"] for case in plan["cases"]})
    if {row["group"] for row in launch["children"]} != set(groups):
        raise ValueError("Parallel launch group registry mismatch")
    for group in groups:
        root = base / group
        if group == "1000__base_bound_override":
            if read(recovery / "STARTED.json")["plan_sha256"] != plan_sha:
                raise ValueError("Recovery plan mismatch")
            continue
        done = read(root / "COMPLETE.json")
        if (
            not done["all_13_arms_qualified"]
            or done["scores_sha256"] != sha(root / "SCORES.json")
            or read(root / "STARTED.json")["plan_sha256"] != plan_sha
            or sha(root / "EXECUTED_SOURCE.py") != launch["script_sha256"]
        ):
            raise ValueError("Unqualified or changed canonical group")
    output = BATCH / "audit_parallel_merged_01"
    output.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), output / "EXECUTED_SOURCE.py")
    rows, bindings, agreements = {}, {}, ["1000__persistent_override_parallel_replay_matches_serial"]
    for group in groups:
        root = (recovery if group == "1000__base_bound_override" else base) / group
        sources = read(root / "SOURCE_BINDINGS.json")
        cases = [case for case in plan["cases"] if case["data_case"] == group]
        if set(sources) != {case["id"] for case in cases}:
            raise ValueError("Original audit denominator mismatch")
        score = read(root / "SCORES.json")
        if score["expected_arms"] != [case["arm"] for case in cases] or not score["full_comparison_qualified"]:
            raise ValueError("Canonical method denominator mismatch")
        save(output / (group + "_SCORES.json"), score)
        prior = BATCH / "audit_consolidated_01" / (group + "_SCORES.json")
        if prior.exists():
            if read(prior) != score:
                raise ValueError("Serial and parallel original scorer disagree")
            agreements.append(group)
        for case in cases:
            ident = case["id"]
            destination = output / ident
            destination.mkdir(exist_ok=False)
            binding = sources[ident]
            for name in ("VALIDATION.json", "RECEIPTS.json", "admission_reconstructed.jsonl"):
                path = root / ident / name
                if sha(path) != binding[name]:
                    raise ValueError("Changed audited artifact: " + str(path))
                shutil.copyfile(path, destination / name)
                if sha(destination / name) != binding[name]:
                    raise ValueError("Copied audited artifact differs")
            row = read(destination / "VALIDATION.json")
            if row["status"] != "qualified" or row["source_report_sha256"] != sha(BATCH / "runs" / ident / "REPORT.json"):
                raise ValueError("Original report no longer matches qualification")
            rows[ident], bindings[ident] = row, binding
    identities = [(row["case"], row["call_id"]) for path in BATCH.glob("BATCH_*_INTENT.json") for row in read(path)["calls"]]
    actual = sum(row["actual_model_calls"] for row in rows.values())
    if not (len(rows) == len(plan["cases"]) and completion["all_controller_exits_zero"] and actual == completion["actual_model_calls"] == len(identities) == len(set(identities)) <= plan["model_call_ceiling"]):
        raise ValueError("Original full-batch invocation mismatch")
    save(output / "SOURCE_BINDINGS.json", bindings)
    save(output / "VALIDATION.json", {
        "plan_sha256": plan_sha,
        "all_sessions_qualified": True,
        "registered_sessions": len(plan["cases"]),
        "expected_opportunity_rows": sum(case["opportunities"] for case in plan["cases"]),
        "sessions": [rows[case["id"]] for case in plan["cases"]],
        "audited_actual_model_calls": actual,
        "issued_model_calls": len(identities),
        "unique_generation_batch_seconds": sum(read(path)["compute_seconds"] for path in BATCH.glob("BATCH_*_COMPLETE.json")),
        "engineering_rehearsal": False,
        "independent_confirmation": False,
        "origin": "Original independently verified per-case captures. Three groups use original sequential canonical scorer; final group uses original journal replay parallelized across arms and caches these exact engines for original scorer. A complete 13-arm reference group agrees exactly between both executions. One final case is imported from original automatic audit with provenance. Original automatic and incomplete supplemental audits are preserved separately.",
        "serial_parallel_group_agreements": agreements,
        "timing_limitations": plan["timing"],
    })
    save(output / "COMPLETE.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "all_groups_qualified": True, "new_model_calls": 0})
    print(json.dumps({"passed": True, "sessions": len(rows), "actual_model_calls": actual}), flush=True)


if __name__ == "__main__":
    main()
