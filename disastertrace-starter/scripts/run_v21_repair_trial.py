"""Run the synthetic Original/Repair/Sham v21 trial."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.repair_trial_v21 import run_repair_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run_repair_trial()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    status = artifact["status"] == "APPLIED" and artifact["sham_matches_original"] and artifact["repair_changes_suffix"]
    print({"status": "PASS" if status else "FAIL", "out": str(args.out)})
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
