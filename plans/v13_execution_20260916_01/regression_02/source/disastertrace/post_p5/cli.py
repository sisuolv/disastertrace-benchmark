"""Offline P5 diagnostics; no provider or model dispatch command."""

import argparse
import json
from pathlib import Path

from .report import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.project, args.baseline, args.output)
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("status", "counts", "citation_only_primary", "first_exposure_episodes")
            }
        )
    )


if __name__ == "__main__":
    main()
