"""Offline diagnostics, native GPU collection and CPU-only independent reports."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("verify", "collect", "report", "verify-report", "submit")
    )
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--worker", type=int)
    parser.add_argument("--mode", choices=("diagnostic", "model"), default="diagnostic")
    parser.add_argument("--policy", default="latest_explicit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from . import package

    if args.command == "verify":
        result = {"execution_id": package.verify(args.execution, code=True)[0]["execution_id"]}
    elif args.command == "collect":
        from .runtime import collect

        if args.mode == "diagnostic":
            from .backend import ProgramBackend

            tokenizer = package.tokenizer_for(args.execution)
            result = collect(
                args.execution,
                args.run_root,
                args.worker,
                tokenizer=tokenizer,
                backend=ProgramBackend(tokenizer, args.policy),
            )
        else:
            if args.policy != "latest_explicit":
                raise ValueError("model collector cannot select a diagnostic policy")
            result = collect(args.execution, args.run_root, args.worker, mode="model")
        print(result, flush=True)
        return 0 if result["stop_reason"] == "complete" else 1
    elif args.command in ("report", "verify-report"):
        from .audit import report

        result = report(
            args.execution, args.run_root, args.output, verify=args.command == "verify-report"
        )
    else:
        from .launch import submit_phase

        result = submit_phase(args.execution, args.output)
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
