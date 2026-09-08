"""Prepare or verify an offline layout; this module has no GPU submission path."""

import argparse
from pathlib import Path

from disastertrace.local_eval.storage import read, seal, verify_seal, write
from disastertrace.repeat_live import package

from .layout import prepare, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify"))
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 4), default=4)
    args = parser.parse_args()
    plan, _, slots = package.verify(args.execution)
    layout = prepare(plan, slots, args.workers)
    if args.command == "verify":
        verify_seal(args.output)
        saved = read(args.output / "layout.json")
        validate(saved, slots)
        if saved != layout:
            raise ValueError("saved layout differs from deterministic reconstruction")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        write(args.output / "layout.json", layout)
        seal(args.output)
    print(
        {
            "status": "passed",
            "layout_id": layout["layout_id"],
            "workers": args.workers,
            "opportunities_per_worker": [w["opportunities"] for w in layout["workers"]],
            "whole_episodes_per_worker": [len(w["base_episode_ids"]) for w in layout["workers"]],
            "model_generations": 0,
            "gpu_submissions": 0,
            "dispatch_compatible": False,
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
