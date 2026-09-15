"""Run before/after in fresh processes on one CPU node and compare all score bytes."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    out = args.run / "profile_01"
    out.mkdir(exist_ok=False)
    case = args.repo / "plans/v10_execution_20260914_01/seasonal_controls_01/new_york__2025-03-03__1000"
    sources = {
        "before": args.repo / "plans/v10_execution_20260914_01/seasonal_controls_01/source",
        "after": args.run / "fullweek_01/source",
    }
    results = {}
    for kind, source in sources.items():
        command = [sys.executable, "-B", str(args.run / "profile_replay.py"), "--case", str(case),
                   "--out", str(out / kind)]
        with (out / (kind + ".log")).open("x") as log:
            result = subprocess.run(command, env=dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1"),
                                    cwd=args.repo, stdout=log, stderr=subprocess.STDOUT, timeout=7200)
        results[kind] = {"exit_code": result.returncode, "command": command}
        if result.returncode:
            break
        results[kind].update(json.loads((out / kind / "RESULT.json").read_text()))
    passed = (len(results) == 2 and all(r["exit_code"] == 0 for r in results.values())
              and results["before"]["score_sha256"] == results["after"]["score_sha256"]
              and results["before"]["from_journal_calls"] == 19 and results["after"]["from_journal_calls"] == 9)
    record = {"passed": passed, "runs": results, "claim": "one measured case; no general speedup or cache-isolation claim"}
    (out / "RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
