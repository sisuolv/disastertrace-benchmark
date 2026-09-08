"""Read-only progress; never loads weights, reads credentials or starts collection."""

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
plan = json.loads((HERE / "execution/execution.json").read_text())
run = Path(plan["run_path"])
rows, incomplete_files = [], []
for path in sorted((run / "captures").glob("*.json")):
    try:
        rows.append(json.loads(path.read_text()))
    except (OSError, ValueError):
        incomplete_files.append(path.name)
completion = run / "completion.json"
observed = HERE / "runtime/observer_completion.json"
print(
    json.dumps(
        {
            "execution_id": plan["execution_id"],
            "planned": plan["planned_responses"],
            "saved_responses": len(rows),
            "schema_status": dict(Counter(r["status"] for r in rows)),
            "finish_reasons": dict(Counter(r["result"]["finish_reason"] for r in rows)),
            "last_capture_at": rows[-1]["captured_at"] if rows else None,
            "temporarily_unreadable_capture_files": incomplete_files,
            "collector_completion": json.loads(completion.read_text())
            if completion.exists()
            else None,
            "observer_completion": json.loads(observed.read_text()) if observed.exists() else None,
            "model_report_present": (HERE / "model_report/report.json").exists(),
            "new_model_calls": 0,
        },
        indent=2,
    )
)
