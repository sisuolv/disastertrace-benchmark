"""Retain the command, complete log and observed exit of one offline check."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    target = Path(sys.argv[1])
    command = sys.argv[2:]
    if command and command[0] == "--":
        command.pop(0)
    target.mkdir(parents=True, exist_ok=False)
    record = {
        "command": command,
        "cwd": os.getcwd(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "selected_environment": {
            k: os.environ.get(k)
            for k in (
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "CUDA_VISIBLE_DEVICES",
                "USE_TORCH",
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
            )
        },
    }
    (target / "intent.json").write_text(json.dumps(record, indent=2) + "\n")
    with (target / "output.log").open("x") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    record.update(exit_code=result.returncode, finished_at=datetime.now(timezone.utc).isoformat())
    (target / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"record": str(target), "exit_code": result.returncode}))
    print((target / "output.log").read_text()[-6000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
