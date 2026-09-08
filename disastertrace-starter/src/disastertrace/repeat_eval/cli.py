"""P6 offline prepare, program collection, CPU recovery and report verification."""

import argparse
import json
from pathlib import Path

from . import audit, context, package, runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--project", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--registry", type=Path, required=True)
    prepare.add_argument("--repeats", type=int, default=2)
    for name in ("collect-diagnostic", "report", "verify-report", "context"):
        sub = commands.add_parser(name)
        sub.add_argument("--execution", type=Path, required=True)
        if name != "context":
            sub.add_argument("--run", type=Path, required=True)
        if name in ("report", "verify-report", "context"):
            sub.add_argument("--output", type=Path, required=True)
        if name == "collect-diagnostic":
            sub.add_argument("--mode", choices=runtime.MODES, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = package.prepare(args.project, args.output, args.registry, repeats=args.repeats)
        result = {
            k: result[k]
            for k in (
                "execution_id",
                "planned_responses",
                "planned_trajectories",
                "generation_authorized",
            )
        }
    elif args.command == "collect-diagnostic":
        result = runtime.collect(args.execution, args.run, mode=args.mode)
    elif args.command == "report":
        result = audit.report(args.execution, args.run, args.output)
        result = {k: v for k, v in result.items() if k != "run_files"}
    elif args.command == "verify-report":
        result = audit.verify_report(args.execution, args.run, args.output)
    else:
        result = context.sweep(args.execution, args.output)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
