"""Run the registered monthly program extension and its independent score audit."""

import datetime as dt
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime/temperature_fullcalendar_01"


def write(name, row):
    with (RUNTIME / name).open("x") as handle:
        json.dump(row, handle, indent=2)


def main():
    registration = json.loads((ROOT / "TEMPERATURE_FULLCALENDAR_EXTENSION.json").read_text())
    write("WORKER_CLAIM.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "host": socket.gethostname(),
        "python": sys.version, "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
    })
    assert sys.version_info[:2] == (3, 10)
    for name, expected in registration["files"].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT.parents[1] / "disastertrace-starter/src"),
               DISASTERTRACE_FOLLOWUP_ROOT=str(ROOT))
    for label, name in [
        ("program", "run_temperature_fullcalendar.py"),
        ("audit", "analyze_temperature_fullcalendar.py"),
    ]:
        command = [sys.executable, str(ROOT / "scripts" / name)]
        write(label + ".command.json", command)
        with (RUNTIME / (label + ".log")).open("x") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        write(label + ".exit.json", {"exit_code": result.returncode})
        if result.returncode:
            write("STOPPED.json", {"stage": label, "exit_code": result.returncode})
            raise RuntimeError(label + " failed; all original outputs retained")
    # Count target labels once, independently of repeated lead-time opportunities.
    unique = {}
    for case in (ROOT / "temperature_fullcalendar_01").glob("20??-??"):
        rows = json.loads((case / "POLICY.json").read_text())["rows"]
        outcomes = {r["opportunity_id"]: r for r in json.loads((case / "OUTCOMES.json").read_text())}
        for row in rows:
            outcome = outcomes[row["opportunity_id"]]
            value = {"event": row["event"], "value": outcome["value"], "status": outcome["status"]}
            tid = row["target"]["target_id"]
            assert tid not in unique or unique[tid] == value
            unique[tid] = value
    groups = {}
    for row in unique.values():
        g = groups.setdefault(row["event"], {"targets": 0, "mature": 0, "positive": 0})
        g["targets"] += 1
        g["mature"] += row["status"] == "mature"
        g["positive"] += row["status"] == "mature" and row["value"] == 1
    write("COVERAGE.json", {"unique_targets": len(unique), "by_event": groups})
    write("COMPLETE.json", {"passed": True, "model_calls": 0, "gpu_cards": 0,
                            "at": dt.datetime.now(dt.timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
