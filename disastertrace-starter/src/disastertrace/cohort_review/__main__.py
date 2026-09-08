"""CPU-only analysis of completed or stopped cohort matrices."""

import argparse
from pathlib import Path

from disastertrace.forecast_task.common import read, write

from .analysis import TRACKS, analyze, compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("analyze")
    item.add_argument("--track", choices=TRACKS, required=True)
    item.add_argument("--execution", type=Path, required=True)
    item.add_argument("--run-root", type=Path, required=True)
    item.add_argument("--report", type=Path, required=True)
    pair = commands.add_parser("compare")
    pair.add_argument("--native", type=Path, required=True)
    pair.add_argument("--default-spacing", type=Path, required=True)
    for command in (item, pair):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = (
        analyze(args.track, args.execution, args.run_root, args.report)
        if args.command == "analyze"
        else compare(read(args.native), read(args.default_spacing))
    )
    if args.verify:
        if result != read(args.output):
            raise ValueError("saved analysis differs from reconstruction")
    else:
        write(args.output, result)
    print(
        {
            "status": "passed",
            **{
                k: result[k]
                for k in ("analysis_id", "comparison_id", "model_profile", "counts", "score_counts")
                if k in result
            },
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
