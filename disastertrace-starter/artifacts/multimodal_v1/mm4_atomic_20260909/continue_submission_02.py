"""Submit only the three never-attempted shards after the STARTING-count rejection."""

import copy
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from resource_count_v2 import requested_h100
from submit_jobs import ROOT, TERMINAL, digest, jobs, now, read, write


def main():
    retry = ROOT / "acp_continuation_02"
    retry.mkdir(exist_ok=False)
    suites = ET.parse(ROOT / "RESOURCE_TESTS_02.xml").getroot()
    if any(int(s.attrib.get(k, 0)) for s in suites.iter("testsuite") for k in ("failures", "errors", "skipped")):
        raise ValueError("resource accounting regression gate failed")
    execution = read(ROOT / "EXECUTION.json")
    identity = digest((ROOT / "EXECUTION.json").read_bytes())
    for name, expected in execution["bound_files"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("frozen scientific execution changed")
    if time.time() + 3600 >= execution["not_after_unix"]:
        raise ValueError("original frozen window too short; do not reset it")
    original = read(ROOT / "acp/0/INTENT.json")
    first = read(ROOT / "acp/0/JOB.json")
    accepted = {first["job_id"]}
    write(retry / "CLAIM.json", {"at": now(), "execution_sha256": identity,
          "remaining_workers": ["1", "2", "3"], "worker_0_reused": False,
          "reason": "STARTING spec.replicas=0, role.total_replicas=1; reserve requested one card",
          "source_sha256": {name: digest((ROOT / name).read_bytes()) for name in
                            ["resource_count_v2.py", "test_resource_count_v2.py", "continue_submission_02.py"]}})
    for worker in ("1", "2", "3"):
        canonical_dir = ROOT / "acp" / worker
        if any((canonical_dir / name).exists() for name in ("INTENT.json", "JOB.json")):
            raise ValueError("this shard already has a submission attempt")
        directory = retry / worker
        directory.mkdir()
        current = jobs()
        write(directory / "account_before.json", current)
        active = [j for j in current if j["state"] not in TERMINAL]
        if any(j["name"] not in accepted for j in active):
            raise ValueError("unexpected active account job")
        reserved = sum(requested_h100(j) for j in active)
        if reserved + 1 > 4 or len(accepted) >= 4:
            raise ValueError("global H100 cap would be exceeded")
        display = original["display_name"][:-1] + worker
        if any(j["display_name"] == display for j in current):
            raise ValueError("display name already submitted; never duplicate")
        argv = copy.deepcopy(original["argv"])
        argv = ["--job-name=" + display if x.startswith("--job-name=") else x for x in argv]
        command = argv[-1]
        if command.count("--worker 0") != 1 or command.count("worker-0.log") != 1:
            raise ValueError("unexpected original command")
        argv[-1] = command.replace("--worker 0", "--worker " + worker).replace("worker-0.log", "worker-" + worker + ".log")
        intent = {"at": now(), "worker": worker, "display_name": display,
                  "execution_sha256": identity, "argv": argv, "reserved_before": reserved}
        write(directory / "INTENT.json", intent)
        canonical_dir.mkdir(exist_ok=True)
        write(canonical_dir / "INTENT.json", intent)
        try:
            reply = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            write(directory / "UNKNOWN.json", {"at": now(), "display_name": display,
                                              "action": "query by display name; never resubmit"})
            raise
        write(directory / "RESPONSE.json", {"at": now(), "returncode": reply.returncode,
              "stdout": reply.stdout, "stderr": reply.stderr})
        match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
        if reply.returncode or not match:
            raise RuntimeError("unknown/failed submission; inspect saved response, never duplicate")
        accepted.add(match[1])
        record = {"worker": worker, "job_id": match[1], "display_name": display}
        write(directory / "JOB.json", record)
        write(canonical_dir / "JOB.json", record)
        print(worker, match[1], display, "accepted", flush=True)
    write(retry / "SUBMITTED.json", {"at": now(), "all_four_job_ids": sorted(accepted),
                                    "new_jobs": 3, "worker_0_resubmitted": False})


if __name__ == "__main__":
    main()
