"""One launch claim, four exact disjoint shards, no automatic resubmission."""

import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "source/src"))

from disastertrace.multimodal_v1.storage import digest, now, read, write

SCO = "/mnt/afs/260010168/bin/sco"
TERMINAL = {"SUCCEEDED", "FAILED", "DELETED"}
IMAGE = "registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image"


def jobs():
    argv = [SCO, "acp", "jobs", "list", "--workspace-name=share-space",
            "--user-name=260010168", "--page-size=500", "--format=json"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=True)
    data = json.loads(result.stdout)
    if len(data) >= 500:
        raise ValueError("account pagination unresolved")
    return data


def main():
    mount = subprocess.check_output(["findmnt", "-n", "-T", str(ROOT), "-o", "TARGET,FSTYPE"], text=True).split()
    if mount != ["/mnt/afs", "fuse.quarkfs_client"]:
        raise ValueError("AFS mapping differs")
    acp = ROOT / "acp"
    acp.mkdir(exist_ok=False)
    execution = read(ROOT / "EXECUTION.json")
    identity = digest((ROOT / "EXECUTION.json").read_bytes())
    for name, expected in execution["bound_files"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("frozen input changed: " + name)
    if time.time() + 3600 >= execution["not_after_unix"]:
        raise ValueError("insufficient frozen window for launch")
    write(acp / "LAUNCH_CLAIM.json", {"at": now(), "execution_sha256": identity,
                                    "workers": 4, "h100_global_cap": 4})
    before = jobs()
    write(acp / "account_before.json", before)
    if any(j["state"] not in TERMINAL for j in before):
        raise ValueError("unexpected existing active account reservation")
    accepted = set()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    for worker in ("0", "1", "2", "3"):
        directory = acp / worker
        directory.mkdir()
        current = jobs()
        write(directory / "account_before.json", current)
        active = [j for j in current if j["state"] not in TERMINAL]
        if any(j["name"] not in accepted for j in active) or len(accepted) >= 4:
            raise ValueError("global reservation gate failed")
        if any(sum(int(spec["requests"]["nvidia.com/gpu"]) * int(spec["replicas"])
                   for role in j["roles"] for spec in role["resource_spec"]) != 1 for j in active):
            raise ValueError("existing shard does not reserve exactly one GPU")
        display = "dt-mm4-atomic-" + stamp + "-w" + worker
        command = shlex.join([
            "timeout", "--signal=TERM", "--kill-after=30s", "3600s", "env",
            "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "TOKENIZERS_PARALLELISM=false",
            "PYTHONDONTWRITEBYTECODE=1", "OMP_NUM_THREADS=4", "MKL_NUM_THREADS=4",
            "PYTHONPATH=" + str(ROOT / "source/src"),
            "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python", "-u", "-m",
            "disastertrace.multimodal_atomic_v1.worker", "--batch", str(ROOT),
            "--execution-sha", identity, "--worker", worker,
        ]) + " > " + shlex.quote(str(ROOT / ("worker-" + worker + ".log"))) + " 2>&1"
        argv = [SCO, "acp", "jobs", "create", "--workspace-name=share-space",
                "--aec2-name=computing-cluster-01g-02", "--job-name=" + display,
                "--container-image-url=" + IMAGE, "--training-framework=pytorch", "--worker-nodes=1",
                "--worker-spec=N6lS.Iu.I10.1.8c128g",
                "--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs",
                "--quota-type=reserved", "--priority=NORMAL", "--retry-times=0", "--command=" + command]
        write(directory / "INTENT.json", {"at": now(), "display_name": display,
              "execution_sha256": identity, "worker": worker, "argv": argv})
        try:
            reply = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            write(directory / "SUBMISSION_UNKNOWN.json", {"at": now(), "display_name": display,
                  "action": "Query this unique display name; never relaunch this worker or launcher."})
            raise
        write(directory / "RESPONSE.json", {"at": now(), "returncode": reply.returncode,
                                            "stdout": reply.stdout, "stderr": reply.stderr})
        match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
        if reply.returncode or not match:
            raise RuntimeError("inspect response and query unique display name; submission may be unknown")
        accepted.add(match[1])
        write(directory / "JOB.json", {"worker": worker, "job_id": match[1], "display_name": display})
        print(worker, match[1], display, "accepted; completion not yet verified", flush=True)
    write(acp / "SUBMITTED.json", {"at": now(), "job_ids": sorted(accepted), "workers": 4})


if __name__ == "__main__":
    main()
