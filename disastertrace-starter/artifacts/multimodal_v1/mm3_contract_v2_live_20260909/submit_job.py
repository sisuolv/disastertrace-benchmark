"""One-use ACP submission; a timeout is unknown and is never retried."""

import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent
SCO = "/mnt/afs/260010168/bin/sco"


def save(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    assert subprocess.check_output(["findmnt", "-n", "-T", str(ROOT), "-o", "TARGET,FSTYPE"], text=True).split() == ["/mnt/afs", "fuse.quarkfs_client"]
    job_root = ROOT / "acp"
    job_root.mkdir(exist_ok=False)
    list_argv = [SCO, "acp", "jobs", "list", "--workspace-name=share-space", "--user-name=260010168", "--page-size=500", "--format=json"]
    listed = subprocess.run(list_argv, capture_output=True, text=True, timeout=60)
    if listed.returncode:
        raise RuntimeError("cannot verify current account GPU reservations")
    jobs = json.loads(listed.stdout)
    if len(jobs) >= 500:
        raise ValueError("pagination must be resolved before reserving")
    # This account has no active work at this stage. Stop on any new reservation.
    active = [x for x in jobs if x.get("state") not in {"SUCCEEDED", "FAILED", "DELETED"}]
    save(job_root / "account_jobs_before.json", jobs)
    if active:
        raise ValueError("new active account jobs require explicit slot accounting")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    name = "dt-mm3-v2-" + stamp
    identity = hashlib.sha256((ROOT / "EXECUTION.json").read_bytes()).hexdigest()
    command = shlex.join([
        "timeout", "--signal=TERM", "--kill-after=30s", "3600s", "env",
        "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "TOKENIZERS_PARALLELISM=false",
        "PYTHONDONTWRITEBYTECODE=1", "OMP_NUM_THREADS=4", "MKL_NUM_THREADS=4",
        "PYTHONPATH=" + str(ROOT / "source/src"),
        "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python", "-u",
        "-m", "disastertrace.multimodal_live_v1.worker", "--batch", str(ROOT), "--execution-sha", identity,
    ]) + " > " + shlex.quote(str(ROOT / "worker.log")) + " 2>&1"
    image = "registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image"
    argv = [SCO, "acp", "jobs", "create", "--workspace-name=share-space",
            "--aec2-name=computing-cluster-01g-02", "--job-name=" + name,
            "--container-image-url=" + image, "--training-framework=pytorch", "--worker-nodes=1",
            "--worker-spec=N6lS.Iu.I10.1.8c128g", "--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs",
            "--quota-type=reserved", "--priority=NORMAL", "--retry-times=0", "--command=" + command]
    save(job_root / "submission_intent.json", {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "display_name": name, "execution_sha256": identity, "argv": argv})
    try:
        reply = subprocess.run(argv, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        save(job_root / "SUBMISSION_UNKNOWN.json", {"display_name": name, "action": "query this display name; never duplicate"})
        raise
    save(job_root / "submission_response.json", {"returncode": reply.returncode, "stdout": reply.stdout, "stderr": reply.stderr})
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
    if reply.returncode or not match:
        raise RuntimeError("inspect saved response and query display name before any further action")
    save(job_root / "JOB.json", {"job_id": match.group(1), "display_name": name})
    print(match.group(1), name, "submission accepted; completion is not yet established", flush=True)


if __name__ == "__main__":
    main()
