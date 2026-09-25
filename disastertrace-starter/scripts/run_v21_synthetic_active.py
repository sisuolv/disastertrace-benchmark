"""Run the v21 fully synthetic active Natural gate."""

from __future__ import annotations

import argparse
from pathlib import Path

from disastertrace.monitoring_v1.synthetic_natural_v21 import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run_experiment(args.out)
    print({"status": artifact["active_gate"]["status"], "out": str(args.out), "cases": len(artifact["cases"])})
    return 0 if artifact["active_gate"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
