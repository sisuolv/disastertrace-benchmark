from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import workflow
from .methods import DEFAULT_METHOD, METHODS


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
    run.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    run.add_argument("--event-group", dest="group_ids", action="append")
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
        model_command.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
        model_command.add_argument("--event-group", dest="group_ids", action="append")
        if name == "collect-model":
            model_command.add_argument("--resume-from", type=Path)
            model_command.add_argument("--max-request-bytes", type=int)
            model_command.add_argument("--max-reserved-output-tokens", type=int)
        model_command.add_argument(
            "--split", choices=["development", "heldout"], default="development"
        )
    audit_data = commands.add_parser(
        "audit-dataset", help="Audit frozen data and source similarity"
    )
    audit_data.add_argument("--build", type=Path, required=True)
    audit_data.add_argument("--output", type=Path, required=True)
    audit_log = commands.add_parser(
        "audit-collection", help="Independently verify a collection journal"
    )
    audit_log.add_argument("--build", type=Path, required=True)
    audit_log.add_argument("--collection", type=Path, required=True)
    audit_log.add_argument("--output", type=Path, required=True)
    audit_log.add_argument("--split", choices=["development", "heldout"], default="development")
    audit_log.add_argument("--event-group", dest="group_ids", action="append")
    audit_log.add_argument("--allow-incomplete", action="store_true")
    preflight = commands.add_parser(
        "preflight", help="Run and freeze all network-free pilot checks"
    )
    preflight.add_argument("--build", type=Path, required=True)
    preflight.add_argument("--specification", type=Path, required=True)
    preflight.add_argument("--verification-record", type=Path)
    preflight.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-preflight", help="Verify frozen pilot artifact hashes")
    verify.add_argument("--build", type=Path, required=True)
    verify.add_argument("--package", type=Path, required=True)
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
                method=args.method,
                group_ids=args.group_ids,
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
            options = {}
            if args.command == "collect-model":
                options = {
                    "resume_from": args.resume_from,
                    "max_request_bytes": args.max_request_bytes,
                    "max_reserved_output_tokens": args.max_reserved_output_tokens,
                }
            full = operation(
                args.build,
                args.config,
                args.output,
                split=args.split,
                max_queries=args.max_queries,
                method=args.method,
                group_ids=args.group_ids,
                **options,
            )
            result = {key: value for key, value in full.items() if key != "first_request_only"}
        elif args.command in {"audit-dataset", "audit-collection"}:
            from .common import write_json

            if args.output.exists():
                raise ValueError("audit output exists; choose a new path")
            workflow.verify_build(args.build)
            workflow._require_implementation(args.build)
            if args.command == "audit-dataset":
                from .dataset_audit import audit_dataset

                full = audit_dataset(args.build)
                result = {"audit": str(args.output), "checks": full["checks"]}
            else:
                from .collection_audit import audit_collection

                episodes = workflow.selected_episodes(
                    args.build, args.split, group_ids=args.group_ids
                )
                full = audit_collection(
                    episodes, args.collection, allow_incomplete=args.allow_incomplete
                )
                result = {
                    key: value
                    for key, value in full.items()
                    if key not in {"verified_requests", "verified_outcomes", "responses"}
                }
            write_json(args.output, full)
        elif args.command == "preflight":
            from .preflight import prepare_experiment

            result = prepare_experiment(
                args.build,
                args.specification,
                args.output,
                verification_path=args.verification_record,
            )
        elif args.command == "verify-preflight":
            from .preflight import verify_preflight

            result = verify_preflight(args.build, args.package)
        else:
            workflow.report(args.build, args.scores, args.output)
            result = {"report": str(args.output)}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
