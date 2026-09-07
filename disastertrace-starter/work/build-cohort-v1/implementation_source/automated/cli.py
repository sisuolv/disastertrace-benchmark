from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import workflow


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Automatically scored DisasterTrace weather evaluation"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build", help="Verify source snapshots and construct public/private datasets"
    )
    build.add_argument("--references", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--nhc-snapshot", type=Path)
    acquire = commands.add_parser(
        "acquire-nhc", help="Fetch a frozen catalogue of official NHC records"
    )
    acquire.add_argument("--catalogue", type=Path, required=True)
    acquire.add_argument("--output", type=Path, required=True)
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
    run.add_argument("--split", choices=["all", "development", "heldout"], default="all")
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
    for name, help_text in (
        (
            "prepare-model",
            "Validate model configuration and prepare the first request without network calls",
        ),
        ("collect-model", "Collect actual sequential model responses, then import and score them"),
    ):
        model_command = commands.add_parser(name, help=help_text)
        model_command.add_argument("--build", type=Path, required=True)
        model_command.add_argument("--config", type=Path, required=True)
        model_command.add_argument("--output", type=Path, required=True)
        model_command.add_argument("--max-queries", type=int, required=True)
        model_command.add_argument(
            "--split", choices=["development", "heldout"], default="development"
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "acquire-nhc":
            from .acquisition import fetch_cohort

            manifest = fetch_cohort(args.catalogue, args.output)
            result = {
                "snapshot": str(args.output),
                "successful_records": len(manifest["files"]),
                "planned_records": len(manifest["records"]),
            }
        elif args.command == "build":
            result = workflow.build(args.references, args.output, nhc_snapshot=args.nhc_snapshot)
        elif args.command == "run":
            result = workflow.run(
                args.build,
                args.output,
                track=args.track,
                backend=args.backend,
                predictions_path=args.predictions,
                max_queries=args.max_queries,
                split=args.split,
            )
        elif args.command == "score":
            full = workflow.score(args.build, args.run, args.output)
            result = {
                key: value
                for key, value in full.items()
                if key not in {"per_task", "per_checkpoint", "event_summary"}
            }
        elif args.command in {"prepare-model", "collect-model"}:
            from .model_workflow import collect_from_build, prepare_model

            operation = prepare_model if args.command == "prepare-model" else collect_from_build
            full = operation(
                args.build, args.config, args.output, split=args.split, max_queries=args.max_queries
            )
            result = {key: value for key, value in full.items() if key != "first_request_only"}
        else:
            workflow.report(args.build, args.scores, args.output)
            result = {"report": str(args.output)}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
