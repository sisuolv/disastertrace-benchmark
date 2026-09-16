"""Submit the frozen M01 worker after a verified CPU quota release."""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


RUN = Path(__file__).resolve().parent
RUNTIME = RUN / "runtime"
CONTROL = RUNTIME / "submission_wait"
SCO = "/mnt/afs/260010168/bin/sco"
DISPLAY_NAME = "dt-v13-m01-0916-01"
TERMINAL = {"SUCCEEDED", "FAILED", "SUSPENDED", "STOPPED", "CANCELED", "CANCELLED", "TERMINATED"}
DEADLINE = dt.datetime(2026, 9, 16, 20, tzinfo=dt.timezone.utc).timestamp()
POLL_SECONDS = 120


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write(path, value, *, replace=False):
    if not replace:
        with path.open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    else:
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, indent=2) + "\n")
        os.replace(temp, path)


def verify(files):
    for name, expected in files.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen file mismatch: " + name)


def command(argv):
    start = now()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=90)
        return {"argv": argv, "started_at": start, "finished_at": now(),
                "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        return {"argv": argv, "started_at": start, "finished_at": now(),
                "returncode": None, "timeout": True,
                "stdout": decode(exc.stdout), "stderr": decode(exc.stderr)}


def parse_jobs(reply):
    if reply["returncode"] != 0:
        raise ValueError("Could not establish existing ACP jobs")
    if reply["stdout"].strip() == "No jobs found":
        return []
    jobs = json.loads(reply["stdout"])
    if not isinstance(jobs, list):
        raise ValueError("Unexpected job listing schema")
    return [job for job in jobs if job["display_name"] == DISPLAY_NAME]


def validate_job(job, argv):
    values = {arg.split("=", 1)[0]: arg.split("=", 1)[1] for arg in argv if "=" in arg}
    if job["display_name"] != DISPLAY_NAME or not re.fullmatch(r"pt-[a-z0-9]+", job["name"]):
        raise ValueError("Existing job has a different identity")
    if job["resource_pool"]["name"] != values["--aec2-name"]:
        raise ValueError("Existing job uses another resource pool")
    roles = job["roles"]
    if len(roles) != 1 or roles[0]["startup_script"] != values["--command"]:
        raise ValueError("Existing job command differs")
    role = roles[0]
    specs = role["resource_spec"]
    if (role["total_replicas"] != 1 or role["image_path"] != values["--container-image-url"]
            or len(specs) != 1 or specs[0]["name"] != values["--worker-spec"]
            or specs[0]["replicas"] != 1):
        raise ValueError("Existing job resources differ")


def classify_submission(reply):
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply["stdout"])
    if reply["returncode"] == 0 and match:
        return "accepted", match.group(1)
    if (reply["returncode"] is not None and reply["returncode"] != 0 and not match
            and "429" in reply["stderr"] and "MEMBER_QUOTA_EXCEEDED" in reply["stderr"]):
        return "quota_rejected", None
    # Unknown transport outcomes must never authorize a second create request.
    return "unknown", None


def release_signature(states):
    return tuple(sorted(row["job_id"] for row in states if row.get("state") in TERMINAL))


def may_submit(states, prior_release, ambiguous, seconds):
    freed = [row for row in states if row.get("state") in TERMINAL and row["job_id"] not in prior_release]
    return not ambiguous and seconds < DEADLINE and sum(row["CPU"] for row in freed) >= 8


def probe(row):
    reply = command([SCO, "acp", "jobs", "describe", row["job_id"],
                     "--workspace-name=share-space", "--format=json"])
    result = dict(row)
    result["reply"] = reply
    if reply["returncode"] == 0:
        result["state"] = json.loads(reply["stdout"])["state"]
    return result


def submit_once(argv, attempt_dir, dispatch=command):
    attempt_dir.mkdir(exist_ok=False)
    write(attempt_dir / "CLAIM.json", {"at": now(), "argv": argv, "one_create_request": True})
    reply = dispatch(argv)
    write(attempt_dir / "RESPONSE.json", reply)
    status, job_id = classify_submission(reply)
    write(attempt_dir / "RESULT.json", {"at": now(), "status": status, "job_id": job_id})
    return status, job_id


def accepted(job_id, evidence):
    value = {"at": now(), "job_id": job_id, "CPU": 8, "H100": 1,
             "cluster": "computing-cluster-01g-02", "submission_evidence": str(evidence),
             "worker_gates_still_required": True, "local_GPU_inference": False}
    write(RUNTIME / "JOB.json", value)
    write(CONTROL / "STOP.json", {"at": now(), "reason": "submission_accepted", "job_id": job_id})


def main():
    write(CONTROL / "CLAIM.json", {"at": now(), "pid": os.getpid(), "poll_seconds": POLL_SECONDS,
                                   "deadline_utc": "2026-09-16T20:00:00+00:00", "model_calls": 0})
    verify(read(CONTROL / "FREEZE.json")["files"])
    verify(read(RUNTIME / "LAUNCH_FREEZE.json")["files"])
    original = {"returncode": read(RUNTIME / "CREATE_EXIT.json")["exit_code"],
                "stdout": (RUNTIME / "CREATE.stdout").read_text(),
                "stderr": (RUNTIME / "CREATE.stderr").read_text()}
    if classify_submission(original)[0] != "quota_rejected":
        raise ValueError("Original create request is not a definitive quota rejection")
    argv = read(RUNTIME / "CREATE_ARGUMENTS.json")
    jobs = read(CONTROL / "DEPENDENCIES.json")
    last_release = ()
    ambiguous = False
    iteration = 0
    attempts = 0
    while time.time() < DEADLINE:
        iteration += 1
        directory = CONTROL / f"poll-{iteration:04d}"
        directory.mkdir(exist_ok=False)
        listing = command([SCO, "acp", "jobs", "list", "--workspace-name=share-space",
                           "--display-name=" + DISPLAY_NAME, "--format=json"])
        write(directory / "LIST.json", listing)
        try:
            existing = parse_jobs(listing)
        except (ValueError, KeyError):
            write(CONTROL / "STATUS.json", {"at": now(), "status": "job_query_unavailable",
                                            "submission_unknown": ambiguous}, replace=True)
            time.sleep(POLL_SECONDS)
            continue
        if len(existing) > 1:
            raise ValueError("Multiple jobs already use the registered display name")
        if existing:
            validate_job(existing[0], argv)
            accepted(existing[0]["name"], directory / "LIST.json")
            return
        if (RUN / "CLAIM.json").exists() or (RUNTIME / "JOB.json").exists():
            raise ValueError("Execution authority already consumed without matching platform listing")
        with ThreadPoolExecutor(max_workers=7) as pool:
            states = list(pool.map(probe, jobs))
        write(directory / "DEPENDENCIES.json", states)
        released = release_signature(states)
        state = {"at": now(), "status": "waiting_CPU_release", "attempts_after_original": attempts,
                 "submission_unknown": ambiguous, "released_job_ids": list(released),
                 "states": [{k: v for k, v in row.items() if k != "reply"} for row in states]}
        if may_submit(states, last_release, ambiguous, time.time()):
            verify(read(CONTROL / "FREEZE.json")["files"])
            verify(read(RUNTIME / "LAUNCH_FREEZE.json")["files"])
            attempts += 1
            status, job_id = submit_once(argv, CONTROL / f"attempt-{attempts + 1:02d}")
            state.update(status=status, attempts_after_original=attempts)
            write(CONTROL / "STATUS.json", state, replace=True)
            if status == "accepted":
                accepted(job_id, CONTROL / f"attempt-{attempts + 1:02d}" / "RESPONSE.json")
                receipt = command([SCO, "acp", "jobs", "describe", job_id,
                                   "--workspace-name=share-space", "--format=json"])
                write(CONTROL / "ACCEPTED_PLATFORM.json", receipt)
                return
            ambiguous = status == "unknown"
            last_release = released
        else:
            if ambiguous:
                state["status"] = "submission_unknown_lookup_only"
            write(CONTROL / "STATUS.json", state, replace=True)
        time.sleep(POLL_SECONDS)
    stop = {"at": now(), "reason": "submission_unknown_deadline" if ambiguous else "CPU_quota_wait_deadline",
            "model_calls_by_submitter": 0, "attempts_after_original": attempts}
    write(CONTROL / "STOP.json", stop)
    if not ambiguous and not (RUN / "CLAIM.json").exists():
        write(RUN / "NOT_LAUNCHED.json", {**stop, "HTTP_intents": 0})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if not (CONTROL / "ERROR.json").exists():
            write(CONTROL / "ERROR.json", {"at": now(), "type": type(exc).__name__, "message": str(exc)})
        raise
