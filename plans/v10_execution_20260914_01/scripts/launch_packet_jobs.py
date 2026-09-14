"""Fresh one-use GPU submission and bounded API worker for the frozen study."""

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.absolute()
    plan = read(batch / "PLAN.json")
    if not read(batch / "PREFLIGHT.json")["passed"]:
        raise ValueError("Frozen packet preparation has not passed")
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen files changed before launch")
    if "scorer_preflight_required" in plan:
        qualification = read(batch / plan["scorer_preflight_required"])
        if (
            not qualification["passed"]
            or qualification["plan_sha256"] != digest(batch / "PLAN.json")
            or qualification["scorer_sha256"] != digest(batch / plan["scorer_source"])
        ):
            raise ValueError(
                "Frozen scoring and fallback qualification is required before inference"
            )
    publish(
        batch / "LAUNCH_CLAIM.json",
        {
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "plan_sha256": digest(batch / "PLAN.json"),
            "max_simultaneous_H100": 4,
        },
    )
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_integration_execution_20260914_01/gpu/qwen38_evidence_01"
    gpu = batch / "gpu"
    gpu.mkdir(exist_ok=False)
    shutil.copytree(batch / "policy", gpu / "policy")
    (gpu / "source").mkdir()
    worker_source = (
        batch / plan["gpu_worker_source"]
        if "gpu_worker_source" in plan
        else old / "source/qwen38_worker.py"
    )
    shutil.copyfile(worker_source, gpu / "source/qwen38_worker.py")
    shutil.copyfile(old / "MODEL_MANIFEST.json", gpu / "MODEL_MANIFEST.json")
    gpu_plan = {
        "model": "Qwen/Qwen3.8-27B",
        "model_directory": read(gpu / "MODEL_MANIFEST.json")["directory"],
        "generation": {
            "seed": 20260914,
            "max_new_tokens": plan["max_tokens"],
            "do_sample": False,
            "thinking": False,
            "dtype": "bfloat16",
            "attention": "sdpa",
        },
        "input_token_cap": plan["input_token_cap"],
        "last_worker_time": plan["last_worker_time"],
        "late_start_cutoff": plan.get("late_start_cutoff", "2026-09-14T21:00:00+00:00"),
        "tasks": [
            {**task, "worker": (i // 2 + i % 2) % 4}
            for i, task in enumerate(plan["tasks"])
        ],
        "parent_plan_sha256": digest(batch / "PLAN.json"),
        "scope": plan.get(
            "scope",
            "fresh text-only fixed E/F packet study, four isolated H100 replicas",
        ),
    }
    publish(gpu / "PLAN.json", gpu_plan)
    files = {str(p.relative_to(gpu)): digest(p) for p in gpu.rglob("*") if p.is_file()}
    publish(
        gpu / "QUALIFICATION.json",
        {
            "runtime_versions": read(old / "QUALIFICATION.json")["runtime_versions"],
            "model_manifest_sha256": digest(gpu / "MODEL_MANIFEST.json"),
            "frozen_files": files,
            "previous_compatibility_basis": str(old / "QUALIFICATION.json"),
            "new_smokes_required": 4,
        },
    )
    submission = gpu / "submission_01"
    submission.mkdir()
    epoch = int(dt.datetime.fromisoformat(plan["last_worker_time"]).timestamp())
    worker = [
        "/mnt/afs/260010168/.venvs/disastertrace-qwen38-v9/bin/python",
        str(gpu / "source/qwen38_worker.py"),
        "--batch",
        str(gpu),
    ]
    shell = (
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        f"remaining_seconds=$(({epoch} - $(date -u +%s)))\n"
        'if [ "$remaining_seconds" -le 0 ]; then exit 124; fi\n'
        'timeout --signal=TERM --kill-after=20 "${remaining_seconds}s" env HF_HUB_OFFLINE=1 '
        "TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=6 "
        + shlex.join(worker)
        + " > "
        + shlex.quote(str(gpu / "parent.log"))
        + " 2>&1\n"
        'worker_exit=$?\nprintf \'{"exit_code":%s}\\n\' "$worker_exit" > '
        + shlex.quote(str(submission / "EXIT.json"))
        + '\nexit "$worker_exit"\n'
    )
    (submission / "bounded.sh").write_text(shell)
    command = read(old / "submission_01/CREATE_ARGUMENTS.json")
    job_name = "dt-v10-qwen38-ef-" + dt.datetime.now(dt.timezone.utc).strftime(
        "%Y%m%d-%H%M%S"
    )
    command = [
        "--job-name=" + job_name
        if s.startswith("--job-name=")
        else "--command=bash " + shlex.quote(str(submission / "bounded.sh"))
        if s.startswith("--command=")
        else s
        for s in command
    ]
    publish(submission / "CREATE_ARGUMENTS.json", command)
    try:
        reply = subprocess.run(
            command, capture_output=True, text=True, timeout=90, check=False
        )
    except subprocess.TimeoutExpired:
        publish(
            submission / "SUBMISSION_UNKNOWN.json", {"job_name": job_name, "retries": 0}
        )
        raise
    publish(
        submission / "CREATE_RESPONSE.json",
        {
            "returncode": reply.returncode,
            "stdout": reply.stdout,
            "stderr": reply.stderr,
        },
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
    if reply.returncode or not match:
        raise RuntimeError(
            "GPU submission did not confirm; query original name before any new attempt"
        )
    publish(
        submission / "JOB.json",
        {
            "job_id": match.group(1),
            "job_name": job_name,
            "gpus": 4,
            "cluster": "computing-cluster-01g-02",
            "worker_spec": "N6lS.Iu.I10.4.56c792g",
        },
    )
    api_command = [
        sys.executable,
        str(root / "plans/v10_execution_20260914_01/scripts/run_checks.py"),
        "--out",
        str(batch / "api/runtime"),
        "--cwd",
        str(root),
        "--timeout",
        str(max(1, epoch - int(dt.datetime.now(dt.timezone.utc).timestamp()))),
        "--",
        "timeout",
        "--signal=TERM",
        "--kill-after=20",
        str(max(1, epoch - int(dt.datetime.now(dt.timezone.utc).timestamp()))) + "s",
        sys.executable,
        str(batch / "source/run_fixed_packet_api.py"),
        "--batch",
        str(batch),
    ]
    with (batch / "api/launcher.log").open("x") as handle:
        process = subprocess.Popen(
            api_command,
            env=dict(
                os.environ,
                PYTHONPATH=str(batch / "source"),
                PYTHONDONTWRITEBYTECODE="1",
            ),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    publish(
        batch / "api/LAUNCH.json",
        {
            "pid": process.pid,
            "command": api_command,
            "plan_sha256": digest(batch / "PLAN.json"),
        },
    )
    print(
        json.dumps(
            {"gpu_job": match.group(1), "api_pid": process.pid, "batch": str(batch)}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
