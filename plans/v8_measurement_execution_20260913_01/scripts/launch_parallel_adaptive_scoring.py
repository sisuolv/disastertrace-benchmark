"""Use four CPU processes in the existing GPU container, with no new GPU job."""

import datetime as dt
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BATCH = HERE / "gpu/adaptive_large_02"


def main():
    if socket.gethostname() != "pt-45149fa42ad9486ba289a5491590e7ba-worker-0":
        raise ValueError("Only the already allocated 56-CPU container may run this launcher")
    affinity = len(os.sched_getaffinity(0))
    if affinity < 4:
        raise ValueError("Insufficient CPU affinity for four processes")
    deadline = dt.datetime(2026, 9, 14, 2, 33, tzinfo=dt.timezone.utc)
    remaining = int((deadline - dt.datetime.now(dt.timezone.utc)).total_seconds())
    if remaining <= 0:
        raise ValueError("Scoring window is over")
    output = BATCH / "audit_parallel_scores_01"
    output.mkdir(exist_ok=False)
    groups = sorted({row["data_case"] for row in json.loads((BATCH / "PLAN.json").read_text())["cases"]})
    script = HERE / "scripts/score_completed_adaptive_group.py"
    receipt = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname(), "cpu_affinity": affinity, "existing_gpu_job": "pt-ug2dg5ln", "new_gpu_jobs": 0, "new_model_calls": 0, "processes": 4, "hard_stop": deadline.isoformat(), "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest()}
    with (output / "LAUNCH_INTENT.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
    children = []
    for group in groups:
        command = ["timeout", "--signal=TERM", "--kill-after=20", str(remaining) + "s", "nice", "-n", "10", "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python", str(script), "--group", group]
        with (output / (group + ".log")).open("x") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=dict(os.environ, PYTHONPATH=str(BATCH / "source"), PYTHONDONTWRITEBYTECODE="1", CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1"))
        children.append({"group": group, "pid": child.pid, "command": command})
    receipt["children"] = children
    with (output / "LAUNCHED.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
    print("PARALLEL_SCORING_LAUNCHED", flush=True)


if __name__ == "__main__":
    main()
