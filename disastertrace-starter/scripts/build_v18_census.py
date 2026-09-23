"""Build a v18 evidence census from a previously frozen qualification artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.census_v18 import evidence_census


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.episodes.read_text(encoding="utf-8"))
    report = evidence_census(payload["episodes"])
    report.update(
        {
            "input_schema": payload.get("schema"),
            "input_episode_count": payload.get("episode_count"),
            "outcomes_accessed": payload.get("outcomes_accessed", False),
            "model_calls": payload.get("model_calls", 0),
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "episodes": report["episode_denominator"], "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
