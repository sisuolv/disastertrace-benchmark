"""Drain excess public fetchers at their sleep boundaries after HTTP 429.

Only descendants of the recorded batch launcher are eligible. Never suspend a
fetcher while it has a live curl child; resume all owned suspensions on exit.
"""

import argparse
import json
import os
import signal
import time
from pathlib import Path


def processes(root):
    rows = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            stat = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            rows[int(directory.name)] = (int(stat[1]), stat[0])
        except (OSError, ValueError, IndexError):
            continue
    descendants = {root}
    while True:
        expanded = descendants | {
            pid for pid, (parent, _) in rows.items() if parent in descendants
        }
        if expanded == descendants:
            break
        descendants = expanded
    return {pid: rows[pid] for pid in descendants if pid in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-pid", type=int, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=18000)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    allowed_script = str(args.batch.absolute() / "source/fetch_public.py")
    paused, active = set(), None

    def record(event):
        with (args.out / "EVENTS.jsonl").open("a") as handle:
            handle.write(json.dumps({"wall_ns": time.time_ns(), **event}) + "\n")

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    deadline = time.monotonic() + args.seconds
    try:
        while Path(f"/proc/{args.root_pid}").exists() and time.monotonic() < deadline:
            descendants = processes(args.root_pid)
            fetchers = {}
            for pid, (_, state) in descendants.items():
                try:
                    argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                    if allowed_script.encode() in argv:
                        fetchers[pid] = state
                except OSError:
                    continue
            paused.intersection_update(fetchers)
            if active not in fetchers:
                active = min(
                    (pid for pid in fetchers if pid not in paused),
                    default=min(paused, default=None),
                )
                if active in paused:
                    os.kill(active, signal.SIGCONT)
                    paused.remove(active)
                    record({"event": "resume_original_fetcher", "pid": active})
            for pid in sorted(fetchers):
                if (
                    pid == active
                    or pid in paused
                    or any(parent == pid for parent, _ in descendants.values())
                ):
                    continue
                try:
                    channel = Path(f"/proc/{pid}/wchan").read_text().strip()
                    # Python 3.10 time.sleep uses select. The frozen downloader
                    # delegates all HTTP to curl, so no-child select is a pause.
                    if "nanosleep" in channel or channel == "do_select":
                        os.kill(pid, signal.SIGSTOP)
                        paused.add(pid)
                        record(
                            {
                                "event": "pause_between_requests",
                                "pid": pid,
                                "wchan": channel,
                            }
                        )
                except (OSError, ProcessLookupError):
                    continue
            time.sleep(0.2)
    finally:
        for pid in paused:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        record(
            {"event": "supervisor_exit", "resumed_owned_suspensions": sorted(paused)}
        )


if __name__ == "__main__":
    main()
