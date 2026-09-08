"""Compile and verify the isolated six-storm development task on CPU."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--source-input", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--qwen-tokenizer", type=Path)
    parser.add_argument("--deepseek-tokenizer", type=Path)
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    from .package import build_execution, verify_execution

    if args.command == "verify":
        result = verify_execution(args.execution)
    else:
        result = build_execution(
            args.source_input,
            args.execution,
            args.project,
            {"qwen3": args.qwen_tokenizer, "deepseek_r1": args.deepseek_tokenizer},
            args.protocol,
        )
    print(result, flush=True)


if __name__ == "__main__":
    main()
