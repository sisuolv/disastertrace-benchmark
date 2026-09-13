"""Consume completed independent GPU audits for CPU reports and sealed evidence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
PUBLICATION = REPO / "publication/v7_review_execution_20260912"
OUT = BASE / "delivery_queue_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    helpers = [BASE / name for name in ("analyze_calendar.py", "analyze_wrappers.py", "analyze_static_baselines.py")]
    helpers += [PUBLICATION / name for name in ("build_evidence.py", "evidence_archive.py")]
    helpers += sorted((REPO / "disastertrace-starter/src/disastertrace/monitoring_v1").rglob("*.py"))
    bindings = {str(p): sha(p) for p in helpers}
    (OUT / "HELPER_BINDINGS.json").write_text(json.dumps(bindings, indent=2) + "\n")
    (OUT / "run_delivery_queue.py").write_bytes(Path(__file__).read_bytes())
    env = dict(os.environ, PYTHONPATH=str(REPO / "disastertrace-starter/src"),
               PYTHONDONTWRITEBYTECODE="1")
    records, completed = [], set()
    deadline = datetime.fromisoformat("2026-09-13T02:15:00+00:00")
    models = {
        "front_persistent": ("gpu_front_primary_persistent_01", "model_front_persistent"),
        "replication_base": ("gpu_replication_primary_base_01", "model_replication_base"),
        "replication_persistent": ("gpu_replication_primary_persistent_01", "model_replication_persistent"),
    }

    def verified(batch):
        return BASE / (batch + "_validation_01") / "VERIFIED.json"

    def run(name, script, *arguments):
        for path, expected in bindings.items():
            if sha(Path(path)) != expected:
                raise ValueError("Frozen CPU report helper changed: " + path)
        command = [sys.executable, str(script), *map(str, arguments)]
        started = datetime.now(timezone.utc).isoformat()
        with (OUT / (name + ".log")).open("x") as stream:
            process = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=1800, check=False)
        records.append({"name": name, "command": command, "started_at": started,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "returncode": process.returncode})
        (OUT / "COMMANDS.json").write_text(json.dumps(records, indent=2) + "\n")
        if process.returncode:
            raise ValueError("CPU delivery task failed: " + name)
        completed.add(name)
        print(json.dumps({"completed": name}), flush=True)

    while datetime.now(timezone.utc) < deadline:
        for key, (batch, unit) in models.items():
            name = "archive_" + key
            if name not in completed and verified(batch).exists():
                run(name, PUBLICATION / "build_evidence.py", "--name", unit,
                    "--kind", "model", "--source", BASE / batch,
                    "--verification", verified(batch))
        for key, dataset, region, controls, bank, threshold, batches, output in [
            ("front", "extension_front_range_03", "front_range", "calendar_controls_front_primary_01",
             "calibration_bank_01", 1000,
             ["gpu_front_primary_base_01", "gpu_front_primary_persistent_01"], "calendar_analysis_front_02"),
            ("replication", "replication_2026_01", "front_range_2026", "calendar_controls_replication_primary_01",
             "calibration_bank_2025_01", 1000,
             ["gpu_replication_primary_base_01", "gpu_replication_primary_persistent_01"], "calendar_analysis_replication_01"),
        ]:
            if "analysis_" + key in completed or not all(verified(batch).exists() for batch in batches):
                continue
            analysis = BASE / output
            run("analysis_" + key, BASE / "analyze_calendar.py", "--dataset", BASE / dataset,
                "--region", region, "--model-verifications", *[verified(batch) for batch in batches],
                "--controls", BASE / controls, "--output", analysis)
            run("wrappers_" + key, BASE / "analyze_wrappers.py", "--analysis", analysis,
                "--model-verifications", *[verified(batch) for batch in batches],
                "--output", BASE / ("wrapper_analysis_" + key + "_01"))
            run("static_" + key, BASE / "analyze_static_baselines.py", "--analysis", analysis,
                "--bank", BASE / bank / "BANK.json", "--threshold", threshold,
                "--output", BASE / ("static_baselines_front_02" if key == "front" else "static_baselines_replication_01"))
        (OUT / "STATUS.json").write_text(json.dumps({
            "updated_at": datetime.now(timezone.utc).isoformat(), "completed": sorted(completed),
            "scope": "CPU analysis and packaging only; no GPU/API submissions",
        }, indent=2) + "\n")
        if len(completed) == 9:
            (OUT / "COMPLETE.json").write_text(json.dumps({"completed": sorted(completed),
                "finished_at": datetime.now(timezone.utc).isoformat(), "new_model_calls": 0}, indent=2) + "\n")
            return
        time.sleep(30)
    (OUT / "STOPPED.json").write_text(json.dumps({"reason": "publication_time_reserve",
        "completed": sorted(completed), "new_model_calls": 0}, indent=2) + "\n")


if __name__ == "__main__":
    main()
