"""Bounded receipt-driven reporting; never launch models or repeat experiments."""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def snapshot():
    jobs = []
    for p in sorted((RUN / "runtime").glob("*/JOB.json")):
        exit_path = p.parent / "EXIT.json"
        jobs.append({**read(p), "runtime": p.parent.name,
                     "worker_exit": read(exit_path)["exit_code"] if exit_path.exists() else None})
    catalog_results = [read(p) for p in (RUN / "annual_catalog_01").glob("*/RESULT.json")]
    progress = {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "fullweek": read(RUN / "STATUS_02.json") if (RUN / "STATUS_02.json").exists() else {"state": "not_started"},
        "annual_catalog": {"expected_region_months": 72,
            "completed_region_months": sum(r["complete"] for r in catalog_results),
            "failed_region_months": sum(not r["complete"] for r in catalog_results)},
        "annual_native_sample": [read(p) for p in (RUN / "annual_native_sample_01").glob("*/RESULT.json")],
        "fullweek_completed_shards": len(list((RUN / "fullweek_02").glob("COMPLETE_*.json"))),
        "regression": read(RUN / "REGRESSION_RESULT_02.json"),
        "new_model_calls": 0, "confirmation_opened": False, "jobs": jobs}
    for row in progress["annual_native_sample"]:
        row.pop("dataset_files", None)
    temporary = RUN / "DASHBOARD.writing"
    temporary.write_text(json.dumps(progress, indent=2) + "\n")
    temporary.replace(RUN / "DASHBOARD.json")
    return progress


def platform_receipts(jobs):
    records = []
    for job in jobs:
        command = ["/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe", job["job_id"],
                   "--workspace-name=share-space", "--format=json"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            record = {"job_id": job["job_id"], "exit_code": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            record = {"job_id": job["job_id"], "status": "platform_observation_timed_out"}
        records.append(record)
    return records


def main():
    write(RUN / "FINISH_CLAIM.json", {"pid": os.getpid(), "max_hours": 10, "model_calls": 0})
    deadline = time.monotonic() + 36000
    analysis_attempted = False
    while True:
        progress = snapshot()
        result = RUN / "fullweek_02/RESULT.json"
        if result.exists() and read(result)["passed"] and not analysis_attempted:
            analysis_attempted = True
            command = [sys.executable, str(RUN / "analyze_fullweek.py"), "--batch", str(RUN / "fullweek_02"),
                       "--out", str(RUN / "fullweek_analysis_01")]
            write(RUN / "ANALYSIS_COMMAND.json", {"command": command})
            with (RUN / "ANALYSIS.log").open("x") as log:
                try:
                    completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(RUN / "fullweek_02/source")),
                        cwd=REPO, timeout=1200)
                    code = completed.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            write(RUN / "ANALYSIS_EXIT.json", {"exit_code": code})
        required = [RUN / "ADVANCE_RESULT_02.json", RUN / "annual_catalog_01/RESULT.json",
                    RUN / "annual_native_sample_01/RESULT.json"]
        receipts = all(p.exists() for p in required)
        worker_terminal = all(j["worker_exit"] is not None for j in progress["jobs"])
        if (receipts and worker_terminal) or time.monotonic() >= deadline:
            proofs = {str(p.relative_to(RUN)): read(p).get("passed") if p.exists() else None for p in required}
            write(RUN / "PLATFORM_FINAL_OBSERVATION.json", platform_receipts(progress["jobs"]))
            analysis = RUN / "ANALYSIS_EXIT.json"
            passed = receipts and worker_terminal and all(proofs.values()) and analysis.exists() and read(analysis)["exit_code"] == 0
            write(RUN / "BATCH_RESULT.json", {"passed_current_scope": passed,
                "at": dt.datetime.now(dt.timezone.utc).isoformat(), "required_receipts": proofs,
                "worker_exits_observed": worker_terminal, "scientific_report": "fullweek_analysis_01/REPORT_CN.md" if analysis.exists() else None,
                "full_year_native_complete": False, "annual_fit_complete": False, "C2_branch_experiment_complete": False,
                "new_model_calls": 0, "confirmation_opened": False,
                "historical_failed_pilot_retained": True, "platform_terminal_states_require_reading": "PLATFORM_FINAL_OBSERVATION.json"})
            break
        time.sleep(120)


if __name__ == "__main__":
    main()
