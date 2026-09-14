"""Continue only never-launched frozen units on an ACP CPU worker."""

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "runtime/cpu_handoff_01"
PILOT = ROOT / "api_pilot_01"


def read(path):
    return json.loads(path.read_text())


def publish(path, value):
    encoded = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    # link is an atomic no-overwrite commit on the same filesystem.
    os.link(temporary, path)
    temporary.unlink()


def status(phase, **details):
    value = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": phase, **details}
    with (HANDOFF / "EVENTS.jsonl").open("a") as handle:
        handle.write(json.dumps(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary = HANDOFF / "STATUS.next"
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(HANDOFF / "STATUS.json")
    print(json.dumps(value), flush=True)


def execute(item):
    case, arm = PILOT / item["case"], item["arm"]
    folder = case / arm
    if (folder / "RUN_CLAIM.json").exists() or (folder / "run.log").exists():
        raise RuntimeError("Handoff refused a previously launched unit")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(PILOT / "source"),
               DISASTERTRACE_FOLLOWUP_ROOT=str(ROOT), OMP_NUM_THREADS="1")
    command = [sys.executable, str(PILOT / "source/run_api_pilot.py"),
               "--case", str(case), "--arm", arm]
    publish(folder / "HANDOFF_LAUNCH.json", {
        "host": socket.gethostname(), "command": command,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "logical_retry": False,
    })
    started = time.monotonic()
    with (folder / "run.log").open("x") as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    row = {"case": case.name, "arm": arm, "exit_code": result.returncode}
    publish(folder / "EXIT.json", row)
    publish(folder / "HANDOFF_FINISH.json", {**row, "elapsed_seconds": time.monotonic()-started})
    print(json.dumps(row), flush=True)
    return row


def validate_local_rows(registration):
    deadline = time.monotonic() + 1800
    while not (HANDOFF / "DRAIN_COMPLETE.json").exists():
        if (HANDOFF / "DRAIN_FAILED.json").exists() or time.monotonic() > deadline:
            raise RuntimeError("Original CCI units have not drained successfully")
        time.sleep(15)
    rows = []
    for item in registration["local_units"]:
        folder = PILOT / item["case"] / item["arm"]
        row = read(folder / "EXIT.json")
        if row["exit_code"] == 0:
            assert read(folder / "COMPLETE.json")["snapshots"] == 72
        rows.append(row)
    return rows


def run_rare(registration):
    script = ROOT / "scripts/run_api_rare_pilot.py"
    assert hashlib.sha256(script.read_bytes()).hexdigest() == registration["rare_variant_sha256"]
    assert not (ROOT / "api_rare_pilot_01").exists(), "Rare batch already consumed"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT.parents[1] / "disastertrace-starter/src"))
    commands = [
        ("rare_pilot", [sys.executable, str(script)]),
        ("rare_audit", [sys.executable, str(ROOT / "scripts/analyze_api_followup.py"),
                        "F", "--pilot", "api_rare_pilot_01"]),
    ]
    for name, command in commands:
        status(name.upper() + "_RUNNING")
        with (ROOT / "runtime" / (name + ".log")).open("x") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        publish(ROOT / "runtime" / (name + ".exit.json"), {"exit_code": result.returncode})
        if result.returncode:
            publish(ROOT / "runtime/RARE_STOPPED.json", {
                "reason": "stage failure", "stage": name, "exit_code": result.returncode})
            raise RuntimeError(name + " failed; original attempts retained")
    publish(ROOT / "runtime/RARE_COMPLETE.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "one outcome-selected exposed weather day; not population evaluation",
        "orchestration": "cpu_handoff_01",
    })


def main():
    registration = read(HANDOFF / "REGISTRATION.json")
    assert socket.gethostname() != registration["cci_host"], "ACP worker required"
    assert sys.version_info[:2] == (3, 10), "Preserve Python 3.10 runtime family"
    publish(HANDOFF / "WORKER_CLAIM.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "pid": os.getpid(),
        "hostname": socket.gethostname(), "python": sys.version,
        "cgroup_limits": {p: Path(p).read_text().strip() for p in [
            "/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/memory.max",
            "/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
            "/sys/fs/cgroup/memory/memory.limit_in_bytes"] if Path(p).exists()},
        "visible_cuda": os.environ.get("CUDA_VISIBLE_DEVICES"),
    })
    for name, expected in registration["bound_files"].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, "Handoff input changed"
    try:
        status("PROGRAM_HANDOFF_RUNNING", units=len(registration["program_units"]), concurrency=32)
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            new_rows = list(pool.map(execute, registration["program_units"]))
        local_rows = validate_local_rows(registration)
        rows = local_rows + new_rows
        assert len(rows) == 120 and len({(r["case"], r["arm"]) for r in rows}) == 120
        publish(PILOT / "PROGRAM_COMPLETE.json", rows)
        assert all(row["exit_code"] == 0 for row in rows), "Program gate failed; no API calls"
        status("MODEL_HANDOFF_RUNNING", units=len(registration["model_units"]), concurrency=4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            model_rows = list(pool.map(execute, registration["model_units"]))
        all_completed = all(row["exit_code"] == 0 for row in model_rows)
        publish(PILOT / "COMPLETE.json", {
            "programs": rows, "models": model_rows, "all_completed": all_completed,
            "budget": read(PILOT / "BUDGET.json"), "orchestration": "cpu_handoff_01",
        })
        status("ORDINARY_PILOT_COMPLETE", all_completed=all_completed)
        if not all_completed:
            publish(ROOT / "runtime/RARE_STOPPED.json", {"reason": "ordinary pilot incomplete"})
            raise RuntimeError("Ordinary model units incomplete")
        run_rare(registration)
        status("REGISTERED_HANDOFF_COMPLETE")
        publish(HANDOFF / "COMPLETE.json", {"passed": True, "gpu_cards": 0})
    except Exception as exc:
        status("STOPPED_AT_HANDOFF_FAILURE", error_type=type(exc).__name__, reason=str(exc))
        if not (ROOT / "runtime/RARE_STOPPED.json").exists() and not (ROOT / "runtime/RARE_COMPLETE.json").exists():
            publish(ROOT / "runtime/RARE_STOPPED.json", {"reason": "handoff failed", "error_type": type(exc).__name__})
        raise


if __name__ == "__main__":
    main()
