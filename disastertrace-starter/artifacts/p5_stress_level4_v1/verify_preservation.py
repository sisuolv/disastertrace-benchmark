"""Verify all prior bytes and the unchanged pinned GPU runtime inventory."""

import argparse
import sys
from pathlib import Path

from disastertrace.constrained_eval import execution
from disastertrace.local_eval.runtime import environment
from disastertrace.local_eval.storage import now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
from historical_artifacts import HistoricalFiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    files = read(HERE / "baseline/protected_files.json")["files"]
    historical = HistoricalFiles(PROJECT.parent)
    for name, expected in files.items():
        if historical.digest(name) != expected:
            raise ValueError("historical file changed: " + name)
    old = PROJECT / "artifacts/p4_constrained_output_v1/execution_live"
    if execution.source_inventory() != read(old / "execution.json")["implementation_files"]:
        raise ValueError("frozen P4 source inventory changed")
    if environment() != read(old / "environment.json"):
        raise ValueError("historical GPU environment changed")
    result = {
        "status": "passed",
        "verified_at": now(),
        "historical_entries": len(files),
        "historical_source_files": len(execution.source_inventory()),
        "gpu_environment_unchanged": True,
    }
    write(args.output, result)
    print(result)


if __name__ == "__main__":
    main()
