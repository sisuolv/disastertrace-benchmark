"""Observe the original adaptive job without new submissions or model retries."""

import datetime
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE / "adaptive_large_02"
SUBMISSION = BATCH / "submission_01"
OUT = BATCH / "observer_01"


def save(path, row):
    with path.open("x") as handle:
        json.dump(row, handle, indent=2)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    save(
        OUT / "STARTED.json",
        {
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "submits_jobs": False,
        },
    )
    ident = (SUBMISSION / "job-id.txt").read_text().strip()
    deadline = datetime.datetime.fromisoformat("2026-09-14T02:40:00+00:00")
    n = 0
    while datetime.datetime.now(datetime.timezone.utc) < deadline:
        r = subprocess.run(
            [
                "/mnt/afs/260010168/bin/sco",
                "acp",
                "jobs",
                "describe",
                "--workspace-name=share-space",
                ident,
                "--format=json",
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        n += 1
        if r.returncode == 0:
            job = json.loads(r.stdout)
            assert job["name"] == ident and job["ownership"]["user_name"] == "260010168"
            if job["state"] in {"SUCCEEDED", "FAILED", "DELETED"}:
                save(SUBMISSION / "FINAL_JOB.json", job)
                audited = BATCH / "audit_01/VALIDATION.json"
                row = {
                    "job_id": ident,
                    "job_state": job["state"],
                    "audit_exists": audited.exists(),
                    "finished_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                }
                if audited.exists():
                    audit = json.loads(audited.read_text())
                    row.update(
                        all_sessions_qualified=audit["all_sessions_qualified"],
                        audited_actual_model_calls=audit["audited_actual_model_calls"],
                    )
                save(OUT / "COMPLETE.json", row)
                print(json.dumps(row), flush=True)
                return
        else:
            save(
                OUT / ("query_error_" + str(n) + ".json"),
                {"exit_code": r.returncode, "stderr": r.stderr},
            )
        time.sleep(30)
    save(
        OUT / "TIME_LIMIT.json",
        {
            "job_id": ident,
            "action": "Inspect the original job and preserve any pending prefix.",
        },
    )


if __name__ == "__main__":
    main()
