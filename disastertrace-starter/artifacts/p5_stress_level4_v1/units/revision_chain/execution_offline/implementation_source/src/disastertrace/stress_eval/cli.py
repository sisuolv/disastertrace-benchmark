"""Versioned constrained-track commands; all model dispatch is explicit."""

import argparse
import json

from . import audit, data, execution, runtime


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    dataset = commands.add_parser("prepare-data")
    dataset.add_argument("--base-dataset", required=True)
    dataset.add_argument("--candidates", required=True)
    dataset.add_argument("--factor", choices=data.FACTORS, required=True)
    dataset.add_argument("--output", required=True)
    verify_data = commands.add_parser("verify-data")
    verify_data.add_argument("--dataset", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--parent", required=True)
    freeze.add_argument("--dataset", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--live", action="store_true")
    freeze.add_argument("--run-path")
    freeze.add_argument("--deadline-utc")
    collect = commands.add_parser("collect")
    collect.add_argument("--execution", required=True)
    collect.add_argument("--output", required=True)
    collect.add_argument("--diagnostic", action="store_true")
    report = commands.add_parser("report")
    report.add_argument("--execution", required=True)
    report.add_argument("--run", required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--verify", action="store_true")
    report.add_argument("--require-model", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare-data":
        value = data.prepare(args.base_dataset, args.candidates, args.output, factor=args.factor)
    elif args.command == "verify-data":
        value, _, _ = data.verify(args.dataset)
    elif args.command == "freeze":
        value = execution.freeze(
            args.parent,
            args.dataset,
            args.output,
            live=args.live,
            run_path=args.run_path,
            deadline_utc=args.deadline_utc,
        )
    elif args.command == "collect":
        value = runtime.collect(args.execution, args.output, diagnostic=args.diagnostic)
    else:
        value = audit.report(
            args.execution,
            args.run,
            args.output,
            verify=args.verify,
            require_model=args.require_model,
        )
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
