"""Read-only observer for the constrained local matrix; never launches or repairs it."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


plan = read(HERE / "execution_live/execution.json")
result = {"phase": "p4_constrained_output_v1", "live_frozen": plan is not None}
if plan:
    run = Path(plan["run_path"])
    result.update(
        execution_id=plan["execution_id"],
        run=str(run),
        initial_launch_consumed=(HERE / "runtime").exists() or run.exists(),
        persisted_responses=len(list((run / "captures").glob("*.json"))),
        planned=plan["planned_responses"],
        completion=read(run / "completion.json"),
        observer_process=read(HERE / "runtime/observer_process.json"),
        observer_completion=read(HERE / "runtime/observer_completion.json"),
    )
print(json.dumps(result, ensure_ascii=True, indent=2))
