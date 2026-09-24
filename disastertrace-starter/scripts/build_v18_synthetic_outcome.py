"""Exercise the complete-grid outcome adapter with a non-empirical fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    registrations = []
    for target_id, outcome in (("fixture-a", 0), ("fixture-b", 1)):
        for method in ("FOLLOW", "PRIOR_P_FACT"):
            for index, checkpoint_id in enumerate(("t0", "t1")):
                registrations.append(
                    {
                        "target_id": target_id,
                        "method": method,
                        "checkpoint_id": checkpoint_id,
                        "checkpoint_index": index,
                        "base": 0.25,
                        "fallback": 0.25,
                        "outcome": outcome,
                    }
                )
    submissions = [
        {"target_id": "fixture-a", "method": "FOLLOW", "checkpoint_id": "t0", "status": "valid", "probability": 0.1},
        {"target_id": "fixture-a", "method": "FOLLOW", "checkpoint_id": "t1", "status": "invalid"},
        {"target_id": "fixture-b", "method": "FOLLOW", "checkpoint_id": "t0", "status": "valid", "probability": 0.8},
        {"target_id": "fixture-b", "method": "FOLLOW", "checkpoint_id": "t1", "status": "valid", "probability": 0.7},
        {"target_id": "fixture-a", "method": "PRIOR_P_FACT", "checkpoint_id": "t0", "status": "valid", "probability": 0.2},
    ]
    result = score_complete_grid(registrations, submissions)
    payload = {
        # v3 (Batch V4): result.report's field meanings changed, see
        # grid_scoring_v18.py's complete_grid_score.v3 schema note.
        "schema": "disastertrace.v18.synthetic_outcome_score.v3",
        "synthetic": True,
        "empirical": False,
        "outcome_registry": "fixture-only; no provider-bound weather Y",
        "result": result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "registered": result["registered"], "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
