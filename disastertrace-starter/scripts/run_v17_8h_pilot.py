"""CLI for the fresh v17 Y-blind pilot; never runs outcome freeze/disclose."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from disastertrace.revision_v1.pilot_v17.runner import run_e2, run_e3, run_main, smoke


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["smoke", "main", "e2", "e3"])
    parser.add_argument("--run", required=True)
    parser.add_argument("--round", type=int, choices=range(4), default=0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.command == "smoke":
        result = smoke(args.run, args.round, {"max_tokens": args.max_tokens, "temperature": 0.2, "stream": False})
        print(json.dumps({"round": args.round, "responses": len(result)}))
    else:
        fn = {"main": lambda run: run_main(run, args.workers), "e2": run_e2, "e3": run_e3}[args.command]
        print(json.dumps(fn(args.run)))


if __name__ == "__main__":
    main()
