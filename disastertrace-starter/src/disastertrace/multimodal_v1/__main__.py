"""Small CLI; deliberately no live model or GPU launch command in this phase."""

import argparse
import json
from pathlib import Path

from .build import build_seed
from .diagnostics import reconstruct, run_diagnostics
from .seed_sources import acquire_seed
from .storage import read, write


def main():
    parser = argparse.ArgumentParser(description="DisasterTrace multimodal offline seed")
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("acquire-seed")
    acquire.add_argument("--project", type=Path, required=True)
    acquire.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build-seed")
    build.add_argument("--sources", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    diagnostic = commands.add_parser("diagnose")
    diagnostic.add_argument("--build", type=Path, required=True)
    diagnostic.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-report")
    verify.add_argument("--build", type=Path, required=True)
    verify.add_argument("--diagnostics", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire-seed":
        result = acquire_seed(args.project, args.output)
        print(
            json.dumps(
                {"records": len(result["records"]), "new_body_bytes": result["new_body_bytes"]}
            )
        )
    elif args.command == "build-seed":
        result = build_seed(args.sources, args.output)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "status",
                        "event_count",
                        "branch_count",
                        "planned_checkpoints",
                        "selected_valid_at",
                    )
                }
            )
        )
    elif args.command == "diagnose":
        result = run_diagnostics(args.build, args.output)
        print(json.dumps(result["summaries"], sort_keys=True))
    else:
        result = reconstruct(args.build, args.diagnostics / "runs")
        if result != read(args.diagnostics / "report.json"):
            raise ValueError("report does not reconstruct")
        receipt = {"status": "passed", "model_calls": 0, "policies": len(result["summaries"])}
        write(args.receipt, receipt)
        print(json.dumps(receipt))


if __name__ == "__main__":
    main()
