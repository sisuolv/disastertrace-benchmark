"""Run the frozen verifier from a fresh node-local copy using system Python."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix="disastertrace-v10-capsule-"))
    capsule = scratch / "capsule"
    shutil.copytree(args.capsule, capsule)
    command = [
        "/usr/bin/python3",
        "-B",
        str(capsule / "verify.py"),
        "--capsule",
        str(capsule),
        "--result",
        str(scratch / "RESULT.json"),
    ]
    (args.out / "COMMAND.json").write_text(
        json.dumps(
            {
                "command": command,
                "original": str(args.capsule),
                "relocated": str(capsule),
            },
            indent=2,
        )
        + "\n"
    )
    with (args.out / "run.log").open("x") as handle:
        response = subprocess.run(
            command,
            cwd=scratch,
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    if (scratch / "RESULT.json").is_file():
        shutil.copyfile(scratch / "RESULT.json", args.out / "RESULT.json")
    (args.out / "EXIT.json").write_text(
        json.dumps({"exit_code": response.returncode}) + "\n"
    )
    raise SystemExit(response.returncode)


if __name__ == "__main__":
    main()
