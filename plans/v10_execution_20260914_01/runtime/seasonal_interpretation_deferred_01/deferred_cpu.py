"""Launch one bounded CPU audit at its recorded dependency milestone."""

import argparse
import datetime as dt
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-file", type=Path, action="append", required=True)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    while not all(path.exists() for path in args.wait_file):
        if dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(args.deadline):
            raise TimeoutError(
                "Dependency deadline reached; no duplicate submission or retries"
            )
        time.sleep(20)
    print(
        "All registered dependency markers exist; submitting the original CPU task.",
        flush=True,
    )
    raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
