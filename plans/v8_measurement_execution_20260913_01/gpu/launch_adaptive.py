"""Submit one frozen adaptive development matrix within the four-H100 envelope."""

import datetime
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

from index_preservation import verify_index

HERE = Path(__file__).resolve().parent
BATCH = HERE / "adaptive_large_02"
OUT = BATCH / "submission_01"
SCO = "/mnt/afs/260010168/bin/sco"
PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, row):
    with path.open("x") as handle:
        json.dump(row, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    now = datetime.datetime.now(datetime.timezone.utc)
    plan, gates = read(BATCH / "PLAN.json"), read(BATCH / "CPU_PREFLIGHT.json")
    assert now < datetime.datetime.fromisoformat("2026-09-13T23:00:00+00:00")
    assert not plan["engineering_rehearsal"] and plan["maximum_concurrent_gpus"] == 4
    assert plan["model_call_ceiling"] == 5376 and len(plan["cases"]) == 52
    assert gates["passed"] and gates["plan_sha256"] == sha(BATCH / "PLAN.json")
    for path, expected in gates["evidence_files"].items():
        assert sha(Path(path)) == expected, path
    for path, expected in plan["files"].items():
        assert sha(BATCH / path) == expected, path
    save(OUT / "INDEX_CONTENT_CHECK.json", verify_index())
    query = [
        SCO,
        "acp",
        "jobs",
        "list",
        "--workspace-name=share-space",
        "--user-name=260010168",
        "--page-size=500",
        "--format=json",
    ]
    result = subprocess.run(
        query, capture_output=True, text=True, timeout=60, check=True
    )
    jobs = json.loads(result.stdout)
    assert len(jobs) < 500 and all(
        j["ownership"]["user_name"] == "260010168" for j in jobs
    )
    active = [j for j in jobs if j["state"] not in {"SUCCEEDED", "FAILED", "DELETED"}]
    count = sum(
        int(role["total_replicas"])
        * int(role["resource_spec"][0]["requests"]["nvidia.com/gpu"])
        for job in active
        for role in job["roles"]
    )
    save(
        OUT / "ACCOUNT_BEFORE.json",
        {"active_requested_gpus": count, "active_jobs": active},
    )
    if count:
        save(
            OUT / "NOT_SUBMITTED.json",
            {
                "reason": "The four-card account envelope is occupied; no duplicate allocation."
            },
        )
        return
    environment = [
        "env",
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "VLLM_WORKER_MULTIPROC_METHOD=spawn",
        "OMP_NUM_THREADS=4",
        "TOKENIZERS_PARALLELISM=false",
        "PYTHONPATH=" + str(BATCH / "source"),
    ]
    command = environment + [
        PYTHON,
        str(BATCH / "source/adaptive_worker.py"),
        "worker",
        "--batch",
        str(BATCH),
    ]
    audit = environment + [
        PYTHON,
        str(BATCH / "source/run_adaptive_audit.py"),
        "--batch",
        str(BATCH),
        "--output",
        str(BATCH / "audit_01"),
        "--workers",
        "4",
    ]
    runner = OUT / "run.sh"
    end = datetime.datetime.fromisoformat("2026-09-14T02:35:00+00:00")
    # Model startup and source verification are outside each session's dispatch clock.
    lines = [
        "#!/usr/bin/env bash",
        "set -uo pipefail",
        shlex.join(command) + " > " + shlex.quote(str(BATCH / "worker.log")) + " 2>&1",
        "worker_rc=$?",
        "printf '%s\\n' \"$worker_rc\" > "
        + shlex.quote(str(BATCH / "worker.exit.txt")),
        shlex.join(audit) + " > " + shlex.quote(str(BATCH / "audit.log")) + " 2>&1",
        "audit_rc=$?",
        "printf '%s\\n' \"$audit_rc\" > " + shlex.quote(str(BATCH / "audit.exit.txt")),
        'if [ "$worker_rc" -ne 0 ] || [ "$audit_rc" -ne 0 ]; then exit 1; fi',
    ]
    runner.write_text("\n".join(lines) + "\n")
    outer = OUT / "bounded.sh"
    outer.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        + f"deadline_epoch={int(end.timestamp())}\n"
        + "remaining_seconds=$((deadline_epoch - $(date -u +%s)))\n"
        + 'if [ "$remaining_seconds" -le 0 ]; then exit 124; fi\n'
        + shlex.join(
            [
                "timeout",
                "--signal=TERM",
                "--kill-after=30",
            ]
        )
        + ' "${remaining_seconds}s" '
        + shlex.join(["bash", str(runner)])
        + "\n"
    )
    subprocess.run(["bash", "-n", str(runner)], check=True)
    subprocess.run(["bash", "-n", str(outer)], check=True)
    name = "dtv8-adaptive235b-4h100-" + now.strftime("%Y%m%dt%H%M%Sz")
    argv = [
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
        OUT / "SUBMISSION_INTENT.json",
        {
            "name": name,
            "argv": argv,
            "plan_sha256": sha(BATCH / "PLAN.json"),
            "gates_sha256": sha(BATCH / "CPU_PREFLIGHT.json"),
            "max_model_calls": plan["model_call_ceiling"],
            "maximum_concurrent_gpus": 4,
            "created_at": now.isoformat(),
            "retry_times": 0,
        },
    )
    try:
        reply = subprocess.run(
            argv, capture_output=True, text=True, timeout=90, check=False
        )
    except subprocess.TimeoutExpired:
        save(
            OUT / "SUBMISSION_UNKNOWN.json",
            {
                "name": name,
                "reason": "Inspect this exact display name; never resubmit blindly.",
            },
        )
        raise
    save(
        OUT / "SUBMISSION_RESPONSE.json",
        {"exit_code": reply.returncode, "stdout": reply.stdout, "stderr": reply.stderr},
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
    assert reply.returncode == 0 and match
    (OUT / "job-id.txt").write_text(match.group(1) + "\n")
    print(
        json.dumps({"job_id": match.group(1), "status": "submitted", "gpus": 4}),
        flush=True,
    )


if __name__ == "__main__":
    main()
