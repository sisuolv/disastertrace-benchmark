"""Run the v21 synthetic Natural score and denominator probe."""

from __future__ import annotations

import argparse
from pathlib import Path

from disastertrace.monitoring_v1.natural_synthetic_score_v21 import run_score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run_score(args.out)
    print(
        {
            "status": "PASS",
            "out": str(args.out),
            "active_mean_loss": artifact["settled"]["active_mean_loss"],
            "fixed_mean_loss": artifact["settled"]["fixed_mean_loss"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
