"""Read-only independent comparison of final report, saved scores and accounting."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/p1_deepseek_development"
LIVE = ROOT / "work/p1-deepseek-background-continuation-v1"
DEST = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def main():
    target = DEST / "report_review.json"
    if target.exists():
        raise ValueError("Preserve existing report review")
    report = read(LIVE / "report/report.json")
    manifest = read(LIVE / "report/manifest.json")
    accounting = read(DEST / "result.json")
    checks = []

    def check(name, actual, expected):
        equal = actual == expected
        if isinstance(actual, float) and isinstance(expected, float):
            equal = math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        checks.append({"name": name, "actual": actual, "expected": expected, "passed": equal})

    check(
        "manifest_fingerprint",
        fingerprint({k: v for k, v in manifest.items() if k != "report_id"}),
        manifest["report_id"],
    )
    for path, expected in manifest["input_sha256"].items():
        check("input:" + path, digest(path), expected)
    check("report_input_inventory", report["input_sha256"], manifest["input_sha256"])
    for name, expected in manifest["files"].items():
        check("output:" + name, digest(LIVE / "report" / name), expected)
    reporter = ART / "continuation_report/report_continuation.py"
    check("reporter_source", digest(reporter), manifest["report_script_sha256"])
    tests = read(ART / "continuation_report/checks.json")
    for path, expected in tests["sources_sha256"].items():
        check("tested_source:" + path, digest(ROOT / path), expected)
    for command in tests["commands"]:
        check("check_exit:" + " ".join(command["argv"]), command["exit_code"], 0)
        check(
            "check_log:" + command["log_path"],
            digest(ROOT / command["log_path"]),
            command["log_sha256"],
        )
    check(
        "23_tests_passed",
        "23 passed" in (ART / "continuation_report/pytest_final.log").read_text(),
        True,
    )
    check("matrix_complete", report["matrix_status"], "completed_amended_continuation")
    check("api_calls_by_report", report["new_provider_requests_by_report"], 0)
    check("accounting_audit_passed", accounting["passed"], True)
    check(
        "all_usage", report["reported_usage"]["totals_where_reported"], accounting["reported_usage"]
    )
    check(
        "unknown_usage_attempt", report["reported_usage"]["attempts_without_completion_metadata"], 1
    )
    check("total_cost_unknown", report["cost_estimate"]["estimated_usd"], None)
    check(
        "received_cost",
        report["cost_estimate"]["cache_aware_subtotal_at_declared_rates_usd"],
        float(accounting["all_received_cost_estimate_usd"]),
    )
    check(
        "captured_window",
        report["cost_estimate"]["response_created_timestamps_in_pricing_window"],
        90,
    )
    counts = report["provider_call_accounting"]
    for key, value in (
        ("cumulative_provider_calls_admitted", 91),
        ("new_provider_calls_admitted", 12),
        ("benchmark_collection_attempts", 90),
        ("benchmark_response_count", 90),
        ("benchmark_scoring_opportunities", 90),
        ("original_pending_reservation_usd", 0.46678016),
        ("spent_plus_pending_usd", 0.82095816),
        ("allowance_remaining_usd", 0.67904184),
    ):
        check("accounting:" + key, counts[key], value)

    all_latencies = []
    for method, result in report["methods"].items():
        v1 = read(LIVE / "runs" / method / "score.json")
        v2 = read(LIVE / "rescores" / method / "score_v2.json")
        check(method + ":v1_metrics", result["v1"]["metrics"], v1["metrics"])
        for name in ("counts", "metrics", "per_event", "event_macro", "paired_delay_minus_base"):
            check(method + ":v2:" + name, result["v2"][name], v2[name])
        collection = LIVE / "runs" / method / "collection"
        outcomes = rows(collection / "outcomes.jsonl")
        requests = rows(collection / "requests.jsonl")
        check(
            method + ":storm_branch_coverage",
            dict(Counter(r["episode_id"] for r in requests)),
            {
                f"{storm}:controlled:{branch}": 5
                for storm in ("al052019", "al062018", "al092021")
                for branch in ("base", "delay")
            },
        )
        invalid = [r for r in outcomes if r["status"] == "invalid"]
        failures = result["failure_diagnostics"]["failures"]
        check(
            method + ":failed_keys",
            [(r["episode_id"], r["checkpoint_id"]) for r in failures],
            [(r["episode_id"], r["checkpoint_id"]) for r in invalid],
        )
        check(
            method + ":no_unsubmitted", result["failure_diagnostics"]["unsubmitted_checkpoints"], 0
        )
        check(
            method + ":price",
            result["cost_estimate"]["cache_aware_subtotal_at_declared_rates_usd"],
            float(accounting["methods"][method]["received_cost_estimate_usd"]),
        )
        for name, macro in result["v2"]["event_macro"].items():
            values = [
                r["metrics"][name]["value"]
                for r in v2["per_event"]
                if r["metrics"][name]["value"] is not None
            ]
            check(
                method + ":event_macro_recomputed:" + name,
                macro["value"],
                statistics.mean(values) if values else None,
            )
        values = sorted(r["metadata"]["elapsed_seconds"] for r in outcomes)
        all_latencies.extend(values)
        for quantile in (0.50, 0.95):
            position = (len(values) - 1) * quantile
            lower = int(position)
            value = values[lower] + (values[math.ceil(position)] - values[lower]) * (
                position - lower
            )
            check(
                method + f":latency_p{int(quantile * 100)}",
                result["transport_latency"][f"p{int(quantile * 100)}_seconds"],
                value,
            )
        check(
            method + ":latency_mean",
            result["transport_latency"]["mean_seconds"],
            statistics.mean(values),
        )
        check(method + ":latency_observed", result["transport_latency"]["observed_requests"], 30)
        check(
            method + ":unknown_latency",
            result["transport_latency"]["attempts_without_observed_latency"],
            int(method == "answer_history"),
        )
    check(
        "overall_latency_mean",
        report["transport_latency"]["mean_seconds"],
        statistics.mean(all_latencies),
    )
    for comparison in report["paired_method_differences"]:
        left, right = comparison["difference"].split(" minus ")
        source_events = {
            method: {r["group_id"]: r for r in report["methods"][method]["v2"]["per_event"]}
            for method in (left, right)
        }
        for event in comparison["per_event"]:
            for name, observed in event["metrics"].items():
                a, b = [
                    source_events[m][event["group_id"]]["metrics"][name]["value"]
                    for m in (left, right)
                ]
                check(
                    f"paired:{left}:{right}:{event['group_id']}:{name}",
                    observed,
                    a - b if a is not None and b is not None else None,
                )
    output = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": digest(__file__),
        "reporter_sha256": digest(reporter),
        "report_id": manifest["report_id"],
        "new_model_api_calls": 0,
        "code_review_findings": [],
        "resolved_before_report": [
            "Explicit authorization scope and launch hash/fingerprint are independently validated by reporter.",
            "Per-call reservation, request size and cumulative conditional allowance are validated by reporter.",
        ],
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }
    with target.open("x") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "checks": len(checks),
                "failed": [c["name"] for c in checks if not c["passed"]],
                "report_id": manifest["report_id"],
            }
        )
    )
    raise SystemExit(0 if output["passed"] else 1)


if __name__ == "__main__":
    main()
