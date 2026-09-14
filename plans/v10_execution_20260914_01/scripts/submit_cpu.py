"""Submit one bounded CPU task; retain ambiguous submissions without retrying."""

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--spec", default="n6ls.iu.i40.16c64g")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.seconds <= 0:
        raise ValueError("A command and positive timeout are required")
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    run = Path(__file__).resolve().parents[1]
    template = json.loads(
        (run / "runtime/dependency_audit_01/CREATE_ARGUMENTS.json").read_text()
    )
    worker = out / "bounded.sh"
    worker.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        "timeout --signal=TERM --kill-after=20 "
        + str(args.seconds)
        + "s "
        + shlex.join(command)
        + " > "
        + shlex.quote(str(out / "worker.log"))
        + " 2>&1\n"
        'worker_exit=$?\nprintf \'{"exit_code":%s}\\n\' "$worker_exit" > '
        + shlex.quote(str(out / "EXIT.json"))
        + '\nexit "$worker_exit"\n'
    )
    replacement = {
        "--job-name=": args.name,
        "--worker-spec=": args.spec,
        "--command=": "bash " + shlex.quote(str(worker)),
    }
    argv = [
        next(
            (
                prefix + value
                for prefix, value in replacement.items()
                if arg.startswith(prefix)
            ),
            arg,
        )
        for arg in template
    ]
    (out / "CREATE_ARGUMENTS.json").write_text(json.dumps(argv, indent=2) + "\n")
    (out / "LAUNCH_CLAIM.json").write_text(
        json.dumps(
            {
                "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "seconds": args.seconds,
                "retries": 0,
                "gpus": 0,
                "command": command,
            }
        )
        + "\n"
    )
    try:
        response = subprocess.run(
            argv, capture_output=True, text=True, timeout=90, check=False
        )
    except subprocess.TimeoutExpired:
        (out / "SUBMISSION_UNKNOWN.json").write_text(
            json.dumps({"job_name": args.name, "retries": 0}) + "\n"
        )
        raise
    (out / "CREATE_RESPONSE.json").write_text(
        json.dumps(
            {
                "returncode": response.returncode,
                "stdout": response.stdout,
                "stderr": response.stderr,
            },
            indent=2,
        )
        + "\n"
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", response.stdout)
    if response.returncode or not match:
        raise RuntimeError(
            "Submission not confirmed; inspect the original name before a new attempt"
        )
    record = {
        "job_id": match.group(1),
        "job_name": args.name,
        "gpus": 0,
        "spec": args.spec,
    }
    (out / "JOB.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
