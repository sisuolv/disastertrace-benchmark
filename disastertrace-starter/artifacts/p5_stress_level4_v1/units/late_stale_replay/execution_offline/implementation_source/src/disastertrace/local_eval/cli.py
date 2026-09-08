"""Explicit preparation, local collection and independent reconstruction commands."""

import argparse
from pathlib import Path

from disastertrace.automated.common import canonical

from . import audit, data, execution, runtime
from .storage import write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--parent", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify-data")
    check.add_argument("--dataset", type=Path, required=True)
    env = sub.add_parser("environment")
    env.add_argument("--output", type=Path, required=True)
    freeze = sub.add_parser("freeze")
    for name in ("dataset", "snapshot", "environment", "output", "run"):
        freeze.add_argument("--" + name, type=Path, required=True)
    freeze.add_argument("--deadline", required=True)
    check = sub.add_parser("verify-execution")
    check.add_argument("--execution", type=Path, required=True)
    check.add_argument("--model-hashes", action="store_true")
    run = sub.add_parser("collect")
    run.add_argument("--execution", type=Path, required=True)
    run.add_argument("--run", type=Path, required=True)
    run.add_argument("--diagnostic", action="store_true")
    for name in ("report", "verify-report"):
        report = sub.add_parser(name)
        for key in ("execution", "run", "output"):
            report.add_argument("--" + key, type=Path, required=True)
        report.add_argument("--require-model", action="store_true")
    args = parser.parse_args()
    if args.command == "build":
        result = data.prepare(args.parent, args.output)
    elif args.command == "verify-data":
        result = data.verify(args.dataset)[0]
    elif args.command == "environment":
        result = runtime.environment()
        write(args.output, result)
    elif args.command == "freeze":
        result = execution.freeze(
            args.dataset,
            args.snapshot,
            args.environment,
            args.output,
            deadline_utc=args.deadline,
            run_path=args.run,
        )
    elif args.command == "verify-execution":
        result = execution.verify(args.execution, full_data=True, model_hashes=args.model_hashes)[0]
    elif args.command == "collect":
        result = runtime.collect(args.execution, args.run, diagnostic=args.diagnostic)
    else:
        result = audit.report(
            args.execution,
            args.run,
            args.output,
            require_model=args.require_model,
            verify=args.command == "verify-report",
        )
    print(canonical(result))


if __name__ == "__main__":
    main()
