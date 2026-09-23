"""Exercise the typed Natural Track without provider or outcome access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    environment = NaturalKernel(
        [
            NaturalSource("q1", 10, {"visibility_m": 4000}),
            NaturalSource("q2", 30, {"visibility_m": 9000}),
        ],
        start=0,
        deadline=60,
    )
    for action in (
        NaturalAction("RETRIEVE", 0, query_id="q1"),
        NaturalAction("WAIT", 0, wake_at=10),
        NaturalAction("RETRIEVE", 10, query_id="q1"),
        NaturalAction("UPDATE", 10, probability=0.4),
        NaturalAction("WAIT", 10, wake_at=30),
        NaturalAction("RETRIEVE", 30, query_id="q2"),
        NaturalAction("STOP", 30),
    ):
        environment.step(action)
    payload = {
        "schema": "disastertrace.v18.natural_synthetic.v2",
        "synthetic": True,
        "empirical": False,
        "public_state": environment.public_state(),
        "actions": environment.actions,
        "outcome_accessed": False,
        "model_calls": 0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "actions": len(environment.actions), "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
