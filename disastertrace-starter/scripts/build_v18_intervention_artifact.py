"""Run the bounded synthetic intervention matrix for the v18 mechanism pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.interventions_v18 import apply_intervention


def fixture():
    return [
        {
            "source_id": "fixture-station",
            "source_revision": "r1",
            "kind": "taf",
            "issued_at": 1,
            "available_at": 2,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 8000}]},
        },
        {
            "source_id": "fixture-station",
            "source_revision": "r2",
            "kind": "taf",
            "issued_at": 3,
            "available_at": 4,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 4000}]},
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for intervention in ("identity_repeat", "same_origin_duplicate", "matched_sham", "withhold", "delay", "repair"):
        result = apply_intervention(fixture(), intervention, target_start=100, target_end=200, as_of=10)
        rows.append(
            {
                "intervention": intervention,
                "changed_fields": result.changed_fields,
                "held_fields": result.held_fields,
                "statuses": [row["status"] for row in result.qualification],
            }
        )
    payload = {
        "schema": "disastertrace.v18.synthetic_interventions.v2",
        "scope": "instrument qualification only; synthetic fixture is not empirical weather evidence",
        "interventions": rows,
        "model_calls": 0,
        "outcomes_accessed": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "interventions": len(rows), "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
