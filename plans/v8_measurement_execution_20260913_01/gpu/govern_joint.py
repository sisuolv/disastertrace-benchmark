"""Launch X09 at most once after the original adaptive job and audit finish."""

import datetime
import hashlib
import json
import re
import shlex
import subprocess
import time
from pathlib import Path

from index_preservation import verify_index

HERE = Path(__file__).resolve().parent
BATCH = HERE / "joint_targets_live_01"
OUT = BATCH / "submission_01"
SCO = "/mnt/afs/260010168/bin/sco"
PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def submit(plan):
    latest = datetime.datetime.fromisoformat(plan["last_submission_at"])
    if now() >= latest:
        save(
            "NOT_SUBMITTED.json",
            {"reason": "Latest start reached; no truncated replacement experiment."},
        )
        return
    gate = read(BATCH / "cpu_preflight_01/VALIDATION.json")
    assert (
        gate["integrity_passed"]
        and gate["dryrun"]
        and gate["actual_benchmark_requests"] == 0
    )
    assert gate["plan_sha256"] == sha(BATCH / "PLAN.json")
    assert len(plan["tasks"]) == 384 and plan["maximum_total_calls"] == 385
    for path, expected in plan["files"].items():
        assert sha(BATCH / path) == expected, path
    assert sha(BATCH / "EVALUATOR_MANIFEST.json") == plan["evaluator_manifest_sha256"]
    for path, expected in read(BATCH / "EVALUATOR_MANIFEST.json").items():
        assert sha(BATCH / path) == expected, path
    save("INDEX_CONTENT_CHECK.json", verify_index())
    reply = subprocess.run(
        [
            SCO,
            "acp",
            "jobs",
            "list",
            "--workspace-name=share-space",
            "--user-name=260010168",
            "--page-size=500",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=True,
    )
    jobs = json.loads(reply.stdout)
    assert len(jobs) < 500 and all(
        job["ownership"]["user_name"] == "260010168" for job in jobs
    )
    active = [
        job for job in jobs if job["state"] not in {"SUCCEEDED", "FAILED", "DELETED"}
    ]
    gpus = sum(
        int(role["total_replicas"])
        * int(role["resource_spec"][0]["requests"]["nvidia.com/gpu"])
        for job in active
        for role in job["roles"]
    )
    save("ACCOUNT_BEFORE.json", {"active_requested_gpus": gpus, "active_jobs": active})
    if gpus:
        save(
            "NOT_SUBMITTED.json",
            {"reason": "GPU envelope occupied; never allocate beyond four cards."},
        )
        return
    if now() >= latest:
        save(
            "NOT_SUBMITTED.json",
            {"reason": "Latest start reached during final checks."},
        )
        return
    env = [
        "env",
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "VLLM_WORKER_MULTIPROC_METHOD=spawn",
        "OMP_NUM_THREADS=4",
        "TOKENIZERS_PARALLELISM=false",
        "PYTHONPATH=" + str(BATCH / "source"),
    ]
    worker = env + [
        PYTHON,
        str(BATCH / "source/joint_worker.py"),
        "--batch",
        str(BATCH),
        "--model",
        "qwen235b_fp8",
    ]
    audit = env + [
        "CUDA_VISIBLE_DEVICES=",
        "OMP_NUM_THREADS=1",
        PYTHON,
        str(BATCH / "source/verify_joint_targets.py"),
        "--batch",
        str(BATCH),
        "--output",
        str(BATCH / "audit_01"),
    ]
    runner = OUT / "run.sh"
    runner.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -uo pipefail",
                shlex.join(worker)
                + " > "
                + shlex.quote(str(BATCH / "worker.log"))
                + " 2>&1",
                "worker_rc=$?",
                "printf '%s\\n' \"$worker_rc\" > "
                + shlex.quote(str(BATCH / "worker.exit.txt")),
                shlex.join(audit)
                + " > "
                + shlex.quote(str(BATCH / "audit.log"))
                + " 2>&1",
                "audit_rc=$?",
                "printf '%s\\n' \"$audit_rc\" > "
                + shlex.quote(str(BATCH / "audit.exit.txt")),
                'if [ "$worker_rc" -ne 0 ] || [ "$audit_rc" -ne 0 ]; then exit 1; fi',
            ]
        )
        + "\n"
    )
    end = datetime.datetime.fromisoformat(plan["hard_stop_at"])
    outer = OUT / "bounded.sh"
    outer.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        + f"deadline_epoch={int(end.timestamp())}\n"
        + "remaining_seconds=$((deadline_epoch - $(date -u +%s)))\n"
        + 'if [ "$remaining_seconds" -le 0 ]; then exit 124; fi\n'
        + 'timeout --signal=TERM --kill-after=20 "${remaining_seconds}s" '
        + shlex.join(["bash", str(runner)])
        + "\n"
    )
    subprocess.run(["bash", "-n", str(runner)], check=True)
    subprocess.run(["bash", "-n", str(outer)], check=True)
    name = "dtv8-x09-235b-4h100-" + now().strftime("%Y%m%dt%H%M%Sz")
    command = [
        SCO,
        "acp",
        "jobs",
        "create",
        "--workspace-name=share-space",
        "--aec2-name=computing-cluster-01g-02",
        "--job-name=" + name,
        "--container-image-url=registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image",
        "--training-framework=pytorch",
        "--worker-nodes=1",
        "--worker-spec=N6lS.Iu.I10.4.56c792g",
        "--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs",
        "--quota-type=reserved",
        "--priority=NORMAL",
        "--retry-times=0",
        "--command=bash " + shlex.quote(str(outer)),
    ]
    save(
        "SUBMISSION_INTENT.json",
        {
            "name": name,
            "command": command,
            "at": now().isoformat(),
            "plan_sha256": sha(BATCH / "PLAN.json"),
            "maximum_new_jobs": 1,
            "maximum_calls": 385,
            "maximum_concurrent_gpus": 4,
        },
    )
    try:
        reply = subprocess.run(
            command, capture_output=True, text=True, timeout=90, check=False
        )
    except subprocess.TimeoutExpired:
        save(
            "SUBMISSION_UNKNOWN.json",
            {
                "name": name,
                "reason": "Inspect this exact display name; do not resubmit.",
            },
        )
        raise
    save(
        "SUBMISSION_RESPONSE.json",
        {"exit_code": reply.returncode, "stdout": reply.stdout, "stderr": reply.stderr},
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
    assert reply.returncode == 0 and match
    (OUT / "job-id.txt").write_text(match.group(1) + "\n")
    print(
        json.dumps(
            {"job_id": match.group(1), "submitted_at": now().isoformat(), "gpus": 4}
        ),
        flush=True,
    )


def main():
    plan = read(BATCH / "PLAN.json")
    OUT.mkdir(exist_ok=False)
    save(
        "GOVERNOR_STARTED.json",
        {
            "at": now().isoformat(),
            "script_sha256": sha(Path(__file__)),
            "plan_sha256": sha(BATCH / "PLAN.json"),
            "last_submission_at": plan["last_submission_at"],
            "predecessor_job": plan["predecessor_job"],
            "no_interruption_or_resubmission": True,
        },
    )
    errors = 0
    while now() < datetime.datetime.fromisoformat(plan["last_submission_at"]):
        try:
            reply = subprocess.run(
                [
                    SCO,
                    "acp",
                    "jobs",
                    "describe",
                    "--workspace-name=share-space",
                    plan["predecessor_job"],
                    "--format=json",
                ],
                capture_output=True,
                text=True,
                timeout=45,
                check=True,
            )
            predecessor = json.loads(reply.stdout)
            assert (
                predecessor["name"] == plan["predecessor_job"]
                and predecessor["ownership"]["user_name"] == "260010168"
            )
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            errors += 1
            save(
                "QUERY_ERROR_" + str(errors) + ".json",
                {"at": now().isoformat(), "kind": type(exc).__name__},
            )
            time.sleep(30)
            continue
        if predecessor["state"] in {"SUCCEEDED", "FAILED", "DELETED"}:
            audit = HERE / "adaptive_large_02/audit_01/VALIDATION.json"
            save("PREDECESSOR_TERMINAL.json", predecessor)
            if (
                predecessor["state"] != "SUCCEEDED"
                or not audit.exists()
                or not read(audit)["all_sessions_qualified"]
            ):
                save(
                    "NOT_SUBMITTED.json",
                    {
                        "reason": "Original adaptive job/audit did not finish completely qualified; preserve its result first."
                    },
                )
                return
            save(
                "PREDECESSOR_AUDIT.json",
                {
                    "path": str(audit),
                    "sha256": sha(audit),
                    "all_sessions_qualified": True,
                },
            )
            submit(plan)
            return
        time.sleep(30)
    save(
        "NOT_SUBMITTED.json",
        {
            "reason": "Original four-GPU job still active at latest X09 start; no new job or changed deadline."
        },
    )


if __name__ == "__main__":
    main()
