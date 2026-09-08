"""Render reproducible descriptive tables from a verified P2 captured report."""

import argparse
import json
from pathlib import Path

import runner


def rate(value):
    n, d = value["numerator"], value["denominator"]
    return f"{n}/{d} ({100 * value['value']:.2f}%)" if d else "0/0 (N/A)"


def render(report):
    lines = [
        "# P2 Captured Result Tables",
        "",
        f"Mode: `{report['mode']}`. Model calls: {report['model_calls']}. "
        f"Complete audited matrix: {report['complete']}.",
        "",
        f"Execution: `{report['execution_id']}`.",
        f"Audit: `{report['audit_id']}`.",
        "",
        "## Source Groups",
        "",
        "Source groups, matched branches and checkpoints are dependent observations. "
        "AL092021 and AL062018 use primary cases; AL052019 uses secondary cases.",
        "",
        "| Source | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    selected = (
        "schema_success",
        "known_value_accuracy",
        "known_grounded_accuracy",
        "unknown_accuracy",
        "all_correct_checkpoints",
    )
    groups = sorted(next(iter(report["methods"].values()))["by_group"])
    for group in groups:
        for method, score in report["methods"].items():
            metrics = score["by_group"][group]["metrics"]
            lines.append(
                "| " + " | ".join([group, method, *(rate(metrics[key]) for key in selected)]) + " |"
            )
    lines += ["", "## Pooled Fixed-Denominator Scores", ""]
    methods = list(report["methods"])
    lines += ["| Metric | " + " | ".join(methods) + " |", "| --- | --- | --- | --- |"]
    for metric in next(iter(report["methods"].values()))["metrics"]:
        values = [rate(report["methods"][method]["metrics"][metric]) for method in methods]
        lines.append("| " + " | ".join([metric, *values]) + " |")
    lines += [
        "",
        "## Predeclared Family By Method Format Screen",
        "",
        "Complete audited matrix, at least 29/30 schema-valid, at most one length finish.",
        "",
        "| Family | Method | Schema | Length | Cell Passed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cell in report["reliability"]["cells"]:
        lines.append(
            f"| {cell['family']} | {cell['method']} | {cell['schema_valid']}/{cell['planned']} "
            f"| {cell['length_finishes']} | {cell['passed']} |"
        )
    lines += [
        "",
        f"Overall thresholds passed: {report['reliability']['thresholds_passed']}. "
        f"Measured model screen passed: {report['reliability']['model_screen_passed']}.",
        "",
        "## Family Scores",
        "",
        "| Family | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for family in ("U1", "U2", "U3"):
        for method, score in report["methods"].items():
            metrics = score["by_family"][family]["metrics"]
            lines.append(
                "| "
                + " | ".join([family, method, *(rate(metrics[key]) for key in selected)])
                + " |"
            )
    operations = report["operations"]
    observed = {
        "planned": report["planned"],
        "attempted": report["attempted"],
        "received": report["received"],
        "completed": report["completed"],
        "unsubmitted": report["unsubmitted"],
        "stop_reason": report["stop_reason"],
        **{key: value for key, value in operations.items() if key != "attempts"},
    }
    lines += [
        "",
        "## Operations",
        "",
        "Failure categories may overlap. Conditional cost estimates are not invoices. "
        "P1's unknown original attempt 79 is outside this P2 ledger.",
        "",
        "```json",
        json.dumps(observed, indent=2),
        "```",
        "",
        "Generated without extra model calls, score repair, human item labels or an LLM judge.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    runner.verify()
    _, _, reporter, _ = runner.frozen_modules()
    verification = reporter.verify_report(runner.HERE / "execution", args.run, args.report)
    report = runner.read(args.report / "report.json")
    if (report["mode"] != "model_http") != args.diagnostic:
        raise ValueError("table origin mismatch")
    content = render(report)
    if args.verify:
        if args.output.read_text() != content:
            raise ValueError("tables differ from captured report reconstruction")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
    print(
        json.dumps(
            {
                "status": "verified" if args.verify else "generated",
                "report_package_id": verification["package_id"],
                "table_script_sha256": runner.sha(Path(__file__)),
                "additional_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
