"""Collect the real exit status of drained children, then retire paused dispatchers."""

import datetime as dt
import json
import os
from pathlib import Path
import shlex
import signal
import time

from run_cpu_handoff import HANDOFF, PILOT, ROOT, publish, read


def main():
    publish(HANDOFF / "DRAIN_CLAIM.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    paused = read(HANDOFF / "PAUSE.json")
    children = {r["pid"]: r for r in paused["active_children"]}
    rows = []
    deadline = time.monotonic() + 1800
    while children:
        if time.monotonic() > deadline:
            raise RuntimeError("CCI drain time limit")
        for pid, row in list(children.items()):
            stat = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
            assert int(stat[1]) == 292859, "Original child identity changed"
            if stat[0] != "Z":
                continue
            argv = shlex.split(row["command"])
            case, arm = Path(argv[argv.index("--case")+1]), argv[argv.index("--arm")+1]
            assert case.parent == PILOT
            raw_wait = int(stat[49])
            exit_code = os.waitstatus_to_exitcode(raw_wait)
            item = {"case": case.name, "arm": arm, "exit_code": exit_code}
            if exit_code == 0:
                assert read(case / arm / "COMPLETE.json")["snapshots"] == 72
            publish(case / arm / "EXIT.json", item)
            rows.append({**item, "pid": pid, "proc_wait_status": raw_wait})
            del children[pid]
        if children:
            time.sleep(15)
    # The stopped schedulers cannot submit queued or newly completed work.
    for pid in [292859, 236473, 266865]:
        proc = Path("/proc") / str(pid)
        command = proc.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode()
        expected = {292859: "scripts/run_api_pilot.py", 236473: "continue_pipeline.py", 266865: "continue_rare_mechanism.py"}[pid]
        assert expected in command
        os.kill(pid, signal.SIGTERM)
        os.kill(pid, signal.SIGCONT)
    publish(HANDOFF / "DRAIN_COMPLETE.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "rows": rows,
        "superseded_scheduler_pids": [292859, 236473, 266865],
        "terminated_only_after_all_original_children_exited": True,
        "ordinary_and_rare_launch_claims_preserved": True,
    })
    state = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": "N4_CPU_HANDOFF_ACTIVE",
             "orchestration": "runtime/cpu_handoff_01", "original_schedulers": "retired after child drain"}
    temp = ROOT / "runtime/PIPELINE_STATUS.handoff"
    temp.write_text(json.dumps(state, indent=2)+"\n")
    temp.replace(ROOT / "runtime/PIPELINE_STATUS.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        publish(HANDOFF / "DRAIN_FAILED.json", {"error_type": type(exc).__name__, "reason": str(exc)})
        raise
