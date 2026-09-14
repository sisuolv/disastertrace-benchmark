"""Use the first fully verified CPU audit and stop only its redundant peer job."""

import datetime as dt
import subprocess
import time
from pathlib import Path

import integrate_parallel_audit as integration
from accelerate_f_audit import ROOT, digest, read, write

RACE = ROOT / "runtime/audit_race_01"
TERMINAL = {"SUCCEEDED", "FAILED", "STOPPED", "CANCELLED", "TERMINATED"}


def check_candidate(runtime, output):
    receipt = read(runtime / "COMPLETE.json")
    validation = read(output / "VALIDATION.json")
    if not receipt["passed"] or receipt["validation_sha256"] != digest(output / "VALIDATION.json"):
        raise ValueError("Unverified candidate receipt")
    expected = {(p.parent.name, arm) for p in (ROOT / "api_pilot_01").glob("*/CONFIGS.json")
                for arm in read(p)}
    actual = [(r["case"], r["arm"]) for r in validation["records"]]
    if (not validation["passed"] or not validation["all_registered_arms_finished"]
            or validation["unfinished_arms"] or set(actual) != expected or len(actual) != len(expected)):
        raise ValueError("Candidate coverage is incomplete")
    integration.compare_prefix(ROOT / "reports/api_forecast_audit_01", output)


def main():
    registration = read(RACE / "REGISTRATION.json")
    write(RACE / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    deadline = time.monotonic() + 7200
    candidates = registration["candidates"]
    while time.monotonic() < deadline:
        states = {}
        for candidate in candidates:
            states[candidate["job"]] = integration.platform(candidate["job"])
        winners = [c for c in candidates if states[c["job"]]["state"] == "SUCCEEDED"]
        if winners:
            for winner in winners:
                runtime, output = Path(winner["runtime"]), Path(winner["output"])
                try:
                    check_candidate(runtime, output)
                except (ValueError, FileNotFoundError):
                    continue
                write(RACE / "WINNER.json", winner)
                for other in candidates:
                    job = other["job"]
                    if job == winner["job"] or states[job]["state"] in TERMINAL:
                        continue
                    reply = subprocess.run([
                        "/mnt/afs/260010168/bin/sco", "acp", "jobs", "stop",
                        "--workspace-name=share-space", job,
                    ], capture_output=True, text=True, timeout=45, check=True)
                    write(RACE / (job + ".stop.json"), {"job": job, "exit_code": reply.returncode,
                          "reason": "Redundant read-only audit; peer passed complete verification"})
                while time.monotonic() < deadline:
                    states = {c["job"]: integration.platform(c["job"]) for c in candidates}
                    if all(s["state"] in TERMINAL for s in states.values()):
                        break
                    time.sleep(15)
                else:
                    raise RuntimeError("Peer job termination unconfirmed")
                integration.RUNTIME, integration.OUTPUT = runtime, output
                integration.integrate(states[winner["job"]])
                result = {"passed": True, "winner": winner, "all_acceleration_jobs": states,
                          "new_model_calls": 0, "at": dt.datetime.now(dt.timezone.utc).isoformat()}
                write(RACE / "COMPLETE.json", result)
                write(ROOT / "reports/audit_acceleration_01/RESULT.json", result)
                return
        if all(s["state"] in TERMINAL for s in states.values()):
            raise RuntimeError("No acceleration candidate passed; serial audit remains authoritative")
        time.sleep(20)
    raise RuntimeError("Parallel audit race timed out; serial audit remains authoritative")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write(RACE / "ERROR.json", {"type": type(exc).__name__, "reason": str(exc)})
        raise
