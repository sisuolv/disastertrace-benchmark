"""Build or verify the offline forecast task. No model/network dispatch exists."""

import argparse
import json

from .package import build_execution, verify_execution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source-input", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--project-root", required=True)
    build.add_argument("--tokenizer-dir", required=True)
    build.add_argument("--protocol", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--execution", required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_execution(
            args.source_input, args.output, args.project_root, args.tokenizer_dir, args.protocol
        )
    else:
        result = verify_execution(args.execution)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
