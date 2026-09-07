"""Record a detached offline finalization's command, process IDs and final exit status."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    folder = Path(__file__).resolve().parent
    command = [
        str(root / ".venv/bin/python"),
        str(folder / "finalize_interrupted.py"),
        "--experiment",
        str(folder.parent / "experiment.json"),
        "--source-root",
        str(root / "work/p1-deepseek-development-v1"),
        "--output-root",
        str(root / "work/p1-deepseek-development-v1-interrupted-finalization"),
    ]
    status_path = folder / "execution.json"
    log_path = folder / "execution.log"
    status = {
        "schema_version": "offline_finalization_supervisor_v1",
        "command": command,
        "working_directory": str(root),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "supervisor_pid": os.getpid(),
        "session_id": os.getsid(0),
        "status": "starting",
        "stdin": "DEVNULL",
        "new_provider_calls_authorized": 0,
        "log_path": str(log_path),
        "script_sha256": hashlib.sha256(
            (folder / "finalize_interrupted.py").read_bytes()
        ).hexdigest(),
    }
    if status_path.exists() or log_path.exists():
        raise ValueError("execution records exist; no implicit retry")

    def save() -> None:
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    save()
    environment = dict(os.environ)
    environment.pop("DEEPSEEK_API_KEY", None)
    with log_path.open("xb") as log:
        child = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        status.update(status="running", child_pid=child.pid)
        save()
        exit_code = child.wait()
    status.update(
        status="completed" if exit_code == 0 else "failed",
        finished_at=datetime.now(timezone.utc).isoformat(),
        exit_code=exit_code,
        log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest(),
    )
    save()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
