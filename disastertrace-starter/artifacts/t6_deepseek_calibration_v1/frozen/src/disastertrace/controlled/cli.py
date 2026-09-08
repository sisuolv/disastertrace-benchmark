"""Offline P2 preparation, semantic verification and diagnostic rehearsal."""

import argparse
from pathlib import Path

from disastertrace.automated.common import canonical, read_jsonl, write_json, write_jsonl

from . import package, public_oracle, runtime, scorer
from .schema import METHODS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--source-build", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--dataset", type=Path, required=True)
    run = commands.add_parser("rehearse")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--method", choices=METHODS, required=True)
    run.add_argument(
        "--backend", choices=(*public_oracle.backends, "invalid-control"), default="correct"
    )
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = package.prepare(args.source_build, args.output)
    elif args.command == "verify":
        result = package.verify(args.dataset)
    else:
        if args.output.exists():
            raise ValueError("rehearsal output exists")
        verification = package.verify(args.dataset)
        episodes = read_jsonl(args.dataset / "episodes.jsonl")
        rows = runtime.rehearse(episodes, args.method, args.backend)
        result = scorer.score(episodes, rows, args.method)
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / "dataset_verification.json", verification)
        write_jsonl(args.output / "trace.jsonl", rows)
        write_json(args.output / "score.json", result)
        result = {
            "status": "completed_diagnostic",
            "responses": len(rows),
            "model_calls": 0,
            "known_grounding": result["metrics"]["known_grounded_accuracy"],
        }
    print(canonical(result))


if __name__ == "__main__":
    main()
