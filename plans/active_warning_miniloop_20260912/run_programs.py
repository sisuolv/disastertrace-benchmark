"""Run and independently reconstruct the predeclared program baseline matrix."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.active_forecast.provenance import load_json, write_json
from disastertrace.active_warning_v1 import Episode, Outcome
from disastertrace.active_warning_v1.policies import run_episode, scenario_episode
from disastertrace.active_warning_v1.scoring import aggregate, score

BASE = Path(__file__).resolve().parent
METHODS = (
    ("initial", "official"),
    ("initial_persistence", "persistence"),
    ("latest", "official"),
    ("observe", "persistence"),
    ("forecast_then_observe", "blend"),
    ("observe_then_forecast", "blend"),
    ("all_read", "blend"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=BASE / "dataset_v2")
    parser.add_argument("--output", type=Path, default=BASE / "programs_01")
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    start = time.monotonic()
    episodes = [Episode.model_validate(row) for row in load_json(args.dataset / "episodes.json")]
    outcomes = {
        row["episode_id"]: Outcome.model_validate(row)
        for row in load_json(args.dataset / "outcomes_private.json")
    }
    pilot_ids = set(load_json(args.dataset / "pilot_ids.json"))
    rows = []
    with (args.output / "traces.jsonl").open("x") as stream:
        for scenario in ("clean", "duplicate", "stale", "delayed"):
            for original in episodes:
                episode = scenario_episode(original, scenario)
                for budget in (0, 2, 4):
                    for policy, fusion in METHODS:
                        trace = run_episode(episode, budget, policy, fusion)
                        rows.append(score(episode, outcomes[episode.id], trace))
                        stream.write(json.dumps(trace, sort_keys=True, allow_nan=False) + "\n")
            print("Completed scenario", scenario, "traces", len(rows), flush=True)
    with (args.output / "scores.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    write_json(args.output / "SUMMARY_ALL.json", aggregate(rows))
    write_json(
        args.output / "SUMMARY_MODEL_PILOT.json",
        aggregate([r for r in rows if r["episode_id"] in pilot_ids]),
    )
    manifest = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "seconds": time.monotonic() - start,
        "targets": len(episodes),
        "pilot_targets": len(pilot_ids),
        "traces": len(rows),
        "trace_reconstructions": len(rows),
        "model_calls": 0,
        "scenarios": ["clean", "duplicate", "stale", "delayed"],
        "budgets": [0, 2, 4],
        "methods": METHODS,
        "primary_metric": "within-family group-macro continuous MAE",
        "probability_warning": "Point-threshold 0/1 scores are diagnostic; no calibrated NHC probability baseline.",
        "inference": "development only; four exposed storms and one recent river segment; no significance claim",
    }
    write_json(args.output / "COMPLETE.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
