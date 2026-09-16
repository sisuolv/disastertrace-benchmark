"""Explicit collection, CPU audit and one-use submission commands."""

import argparse
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("collect", "report", "verify-report", "launch-preflight", "launch-model"),
    )
    parser.add_argument("--execution", required=True)
    parser.add_argument("--run")
    parser.add_argument("--output")
    parser.add_argument("--mode", default="correct")
    parser.add_argument("--acceptance")
    args = parser.parse_args()
    if args.command == "collect":
        from .runtime import collect

        result = collect(args.execution, args.run, mode=args.mode)
    elif args.command in ("report", "verify-report"):
        from . import audit

        call = audit.report if args.command == "report" else audit.verify_report
        result = call(args.execution, args.run, args.output)
    else:
        from .launch import submit

        result = submit(
            args.execution,
            args.output,
            args.command.removeprefix("launch-"),
            acceptance=args.acceptance,
            report=args.run,
        )
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
