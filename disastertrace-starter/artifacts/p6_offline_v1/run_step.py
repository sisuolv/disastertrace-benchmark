"""Record actual command intent, output and observed exit without replacing a prior step."""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("command required")
    args.directory.mkdir(parents=True, exist_ok=False)
    record = {
        "command": command,
        "cwd": str(Path.cwd()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment_policy": "offline flags inherited; no credential values recorded",
    }
    (args.directory / "intent.json").write_text(json.dumps(record, indent=2) + "\n")
    start = time.monotonic()
    with (args.directory / "output.log").open("x") as stream:
        result = subprocess.run(
            command, stdout=stream, stderr=subprocess.STDOUT, env=os.environ, check=False
        )
    record.update(
        exit_code=result.returncode,
        ended_at=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.monotonic() - start,
    )
    (args.directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"step": str(args.directory), "exit_code": result.returncode}), flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
