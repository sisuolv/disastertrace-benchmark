from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import workflow


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Automatically scored offline DisasterTrace first work package"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build", help="Verify source snapshots and construct public/private datasets"
    )
    build.add_argument("--references", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    run = commands.add_parser(
        "run", help="Run diagnostic fixtures or consume externally supplied responses"
    )
    run.add_argument("--build", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--track", choices=["disasterbench", "dynamic"], required=True)
    run.add_argument(
        "--backend",
        choices=[
            "reference-fixture",
            "empty-control",
            "rule",
            "last-arrival",
            "no-update",
            "submissions",
        ],
        required=True,
    )
    run.add_argument("--predictions", type=Path)
    run.add_argument("--max-queries", type=int, default=20)
    score = commands.add_parser("score", help="Independently validate and score a saved run")
    score.add_argument("--build", type=Path, required=True)
    score.add_argument("--run", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    report = commands.add_parser(
        "report", help="Write a report with source coverage and diagnostic limitations"
    )
    report.add_argument("--build", type=Path, required=True)
    report.add_argument("--scores", type=Path, nargs="+", required=True)
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = workflow.build(args.references, args.output)
        elif args.command == "run":
            result = workflow.run(
                args.build,
                args.output,
                track=args.track,
                backend=args.backend,
                predictions_path=args.predictions,
                max_queries=args.max_queries,
            )
        elif args.command == "score":
            full = workflow.score(args.build, args.run, args.output)
            result = {
                key: value
                for key, value in full.items()
                if key not in {"per_task", "per_checkpoint"}
            }
        else:
            workflow.report(args.build, args.scores, args.output)
            result = {"report": str(args.output)}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
