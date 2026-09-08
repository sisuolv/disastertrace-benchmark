"""Read-only local view of the three actual ACP jobs and their capture counts."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTORS = ("revision_chain", "irrelevant_scope", "late_stale_replay")


def read_if(path):
    return json.loads(path.read_text()) if path.exists() else None


def main():
    rows = []
    for factor in FACTORS:
        directory = HERE / "acp/phase_001" / factor
        submitted = read_if(directory / "submission.json") or {}
        plan = read_if(HERE / "units" / factor / "execution_live/execution.json") or {}
        run = Path(plan["run_path"]) if plan else None
        observations = sorted((directory / "observations").glob("*.json"))
        latest = read_if(observations[-1]) if observations else {}
        row = {
            "factor": factor,
            "job_id": submitted.get("job_id"),
            "last_observed_acp_state": latest.get("job", {}).get("state"),
            "acp_observation_at": latest.get("at"),
            "planned": 540,
            "captured": len(list((run / "captures").glob("*.json"))) if run else 0,
            "submitted_batch_files": len(list((run / "batches").glob("*.json"))) if run else 0,
            "completion": read_if(run / "completion.json") if run else None,
            "worker_result": read_if(directory / "worker_result.json"),
        }
        rows.append(row)
    print(
        json.dumps(
            {
                "units": rows,
                "captured_total": sum(r["captured"] for r in rows),
                "planned_total": 1620,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
