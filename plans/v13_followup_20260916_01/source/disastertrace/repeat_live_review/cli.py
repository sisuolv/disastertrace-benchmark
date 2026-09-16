"""CPU-only report and verification for the preserved model captures."""

import argparse

from . import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("report", "verify-report"))
    parser.add_argument("--execution", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    call = audit.report if args.command == "report" else audit.verify_report
    result = call(args.execution, args.run, args.output)
    print({k: v for k, v in result.items() if k not in ("run_files", "runtime")}, flush=True)


if __name__ == "__main__":
    main()
