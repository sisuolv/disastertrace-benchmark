"""Create a separate X09 live freeze; never dispatch from the offline candidate."""

import datetime
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    candidate = HERE / "joint_targets_candidate_01"
    protocol = HERE / "joint_evaluation_protocol_01"
    output = HERE / "joint_targets_live_01"
    plan, validation = (
        read(candidate / "PLAN.json"),
        read(candidate / "VALIDATION.json"),
    )
    assert not plan["generation_enabled"] and validation["passed"]
    assert validation["plan_sha256"] == sha(candidate / "PLAN.json")
    assert validation["unsent_requests"] == len(plan["tasks"]) == 384
    assert validation["maximum_input_tokens"] <= 15360
    for rel, expected in plan["files"].items():
        assert sha(candidate / rel) == expected, rel
    for rel, expected in read(protocol / "MANIFEST.json").items():
        assert sha(protocol / rel) == expected, rel
    audit = read(HERE.parent / "reports/joint_unlaunched_audit_01/VALIDATION.json")
    assert (
        audit["integrity_passed"]
        and audit["dryrun"]
        and audit["actual_benchmark_requests"] == 0
    )
    assert (
        audit["registered_target_answers"] == 576
        and audit["paired_target_head_conditions"] == 288
    )
    assert (
        read(HERE.parent / "validation/full_joint_targets_24.exit.json")["exit_code"]
        == 0
    )
    output.mkdir(exist_ok=False)
    for folder in ("source", "policy", "evaluator"):
        shutil.copytree(candidate / folder, output / folder)
    shutil.copyfile(
        candidate / "PROGRAM_REHEARSAL.json",
        output / "evaluator/PROGRAM_REHEARSAL.json",
    )
    shutil.copyfile(HERE / "joint_worker.py", output / "source/joint_worker.py")
    for name in ("verify_joint_targets.py", "verify_large_diagnostic.py"):
        shutil.copyfile(protocol / name, output / "source" / name)
    evaluator = {
        str(p.relative_to(output)): sha(p)
        for p in sorted((output / "evaluator").rglob("*"))
        if p.is_file()
    }
    save(output / "EVALUATOR_MANIFEST.json", evaluator)
    plan.update(
        schema="disastertrace.joint_targets_live.v1",
        frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        generation_enabled=True,
        candidate_plan_sha256=sha(candidate / "PLAN.json"),
        evaluator_manifest_sha256=sha(output / "EVALUATOR_MANIFEST.json"),
        last_submission_at="2026-09-14T01:15:00+00:00",
        last_model_dispatch_at="2026-09-14T02:20:00+00:00",
        hard_stop_at="2026-09-14T02:30:00+00:00",
        predecessor_job="pt-ug2dg5ln",
        predecessor_required="Terminal platform state and all52 original adaptive sessions independently qualified; never interrupt the predecessor for this optional extension.",
        retries=0,
        independent_confirmation=False,
        user_authorization="Continue the v8 plan autonomously for12h, at most4 simultaneous H100 GPUs, using larger Qwen/DeepSeek models; authorization ends2026-09-14T02:45:50UTC.",
        files={
            str(p.relative_to(output)): sha(p)
            for folder in ("source", "policy")
            for p in sorted((output / folder).rglob("*"))
            if p.is_file()
        },
    )
    save(output / "PLAN.json", plan)
    save(
        output / "FREEZE_VALIDATION.json",
        {
            "passed": True,
            "plan_sha256": sha(output / "PLAN.json"),
            "candidate_plan_sha256": sha(candidate / "PLAN.json"),
            "candidate_validation_sha256": sha(candidate / "VALIDATION.json"),
            "offline_audit_sha256": sha(
                HERE.parent / "reports/joint_unlaunched_audit_01/VALIDATION.json"
            ),
            "test_receipt_sha256": sha(
                HERE.parent / "validation/full_joint_targets_24.xml"
            ),
            "same384_messages_as_candidate": all(
                read(output / "policy" / (task["call_id"] + ".json"))["messages"]
                == read(candidate / "policy" / (task["call_id"] + ".json"))["messages"]
                for task in plan["tasks"]
            ),
            "worker_does_not_load_evaluator_files": not any(
                rel.startswith("evaluator/") for rel in plan["files"]
            ),
            "benchmark_call_cap": 384,
            "compatibility_call_cap": 1,
            "new_model_calls": 0,
            "submitted": False,
        },
    )
    print(json.dumps(read(output / "FREEZE_VALIDATION.json")))


if __name__ == "__main__":
    main()
