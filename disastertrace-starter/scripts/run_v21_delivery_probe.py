"""Run the synthetic Natural delivery intervention probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.delivery_intervention_v21 import run_delivery_probe
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    parent = NaturalKernel(
        [NaturalSource("q0", 0, {"visibility_m": 4000}), NaturalSource("q1", 0, {"visibility_m": 3000})],
        start=0,
        deadline=20,
        target=target_card(),
    )
    parent.step(NaturalAction("RETRIEVE", 0, query_id="q0"))
    artifact = run_delivery_probe(parent.snapshot())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print({"status": "PASS" if artifact["catalogue_equal"] and artifact["withhold_changes_delivery_only"] else "FAIL", "out": str(args.out)})
    return 0 if artifact["catalogue_equal"] and artifact["withhold_changes_delivery_only"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
