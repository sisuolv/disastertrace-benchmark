"""Verify the full historical baseline and unchanged P3 runtime environment."""

import argparse
import sys
from pathlib import Path

from disastertrace.local_eval import execution
from disastertrace.local_eval.runtime import environment
from disastertrace.local_eval.storage import now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
from historical_artifacts import HistoricalFiles  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = read(HERE / "baseline/protected_files.json")
    historical = HistoricalFiles(PROJECT.parent)
    for name, expected in baseline["files"].items():
        if historical.digest(name) != expected:
            raise ValueError("historical file changed: " + name)
    old = read(PROJECT / "artifacts/p3_local_balanced_v1/execution/execution.json")
    if execution.source_inventory() != old["implementation_files"]:
        raise ValueError("historical source inventory changed")
    if environment() != read(PROJECT / "artifacts/p3_local_balanced_v1/execution/environment.json"):
        raise ValueError("historical GPU environment changed")
    result = {
        "status": "passed",
        "verified_at": now(),
        "historical_entries": len(baseline["files"]),
        "historical_source_files": len(old["implementation_files"]),
        "gpu_environment_unchanged": True,
    }
    write(args.output, result)
    print(result)


if __name__ == "__main__":
    main()
