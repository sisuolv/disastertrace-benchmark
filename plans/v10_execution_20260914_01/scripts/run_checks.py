"""Run a bounded command with durable exit, timing, output and test receipts."""

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("Explicit command required")
    args.out.mkdir(exist_ok=False)
    start = time.time()
    record = {
        "command": command,
        "cwd": str(args.cwd),
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (args.out / "COMMAND.json").write_text(json.dumps(record, indent=2) + "\n")
    try:
        with (args.out / "run.log").open("x") as log:
            run = subprocess.run(
                command,
                cwd=args.cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=args.timeout,
                check=False,
            )
        record["exit_code"] = run.returncode
    except subprocess.TimeoutExpired:
        record.update(exit_code=124, timed_out=True)
    record.update(
        seconds=time.time() - start,
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    (args.out / "RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "exit_code": record["exit_code"],
                "seconds": record["seconds"],
                "out": str(args.out),
            }
        ),
        flush=True,
    )
    raise SystemExit(record["exit_code"])


if __name__ == "__main__":
    main()
