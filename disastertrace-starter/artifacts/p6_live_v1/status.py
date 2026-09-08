"""Read local progress only; never launch or resume a worker."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
run = PROJECT / "work/p6-live-v1/model"
result = {"run_exists": run.exists(), "planned_responses": 2160,
          "parsed_records": len(list((run / "parsed").glob("*.json"))),
          "raw_batches": len(list((run / "raw").glob("*.json"))),
          "intent_batches": len(list((run / "intents").glob("*.json")))}
for label, path in (("completion", run / "completion.json"),
                    ("worker", HERE / "acp/model/worker_result.json"),
                    ("submission", HERE / "acp/model/submission.json")):
    if path.exists():
        result[label] = json.loads(path.read_text())
print(json.dumps(result, indent=2))
