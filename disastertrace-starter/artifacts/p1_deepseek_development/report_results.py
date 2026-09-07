"""Create an offline, source-bound descriptive report for a development matrix."""

from __future__ import annotations

import argparse
import itertools
import math
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    strict_json,
    write_json,
)
from disastertrace.automated.provider import ProviderConfig
from disastertrace.automated.rescoring import verify_rescore

METHODS = ("snapshot", "structured_state", "answer_history")
FIXED_METRICS = (
    "schema_success",
    "state_accuracy",
    "grounded_state",
    "known_value_accuracy",
    "known_grounded_accuracy",
    "action_accuracy",
    "unknown_accuracy",
    "known_answer_coverage",
    "gold_transition_success",
    "gold_transition_value_success",
    "gold_preservation",
    "gold_preservation_grounded",
    "provenance_refresh",
    "all_correct_checkpoints",
)
USAGE_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "reasoning_tokens",
)
LATENCY_DEFINITION = (
    "metadata.elapsed_seconds: monotonic time immediately before HTTP transport "
    "through return of all response bytes; excludes response parsing, scoring and "
    "inter-request work. Failed transport attempts have no saved latency. "
    "p50/p95 use linear interpolation at (n-1)*q on sorted observed durations."
)
INTERPRETATION = (
    "Descriptive development calibration: one model and one repeat; event count is explicit. "
    "All methods see all delivered evidence. Branches and checkpoints within a storm "
    "are dependent. No statistical significance, universal ranking, causal memory "
    "benefit, heldout result or certified leaderboard claim is established. "
    "Fixed-denominator rates retain unsuccessful and unsubmitted checkpoints. "
    "Conditional self-error recovery is reported separately. Fixed method order "
    "can confound latency and provider-cache comparisons with execution order."
)


def read_object(path: Path) -> dict:
    value = strict_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + str(path))
    return value


def rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def v1_metrics(metrics: dict) -> dict:
    result = dict(metrics)
    known = metrics["known_answer_coverage"]["denominator"]
    unknown_correct = metrics["unknown_accuracy"]["numerator"]
    for name, source in (
        ("known_value_accuracy", "state_accuracy"),
        ("known_grounded_accuracy", "grounded_state"),
    ):
        result[name] = rate(metrics[source]["numerator"] - unknown_correct, known)
    return result


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def summarize_usage(outcomes: list[dict], attempts_started: int) -> dict:
    totals = {name: 0 for name in USAGE_FIELDS}
    available = {name: 0 for name in USAGE_FIELDS}
    rows = []
    inconsistencies = []
    completions = 0
    for outcome in outcomes:
        metadata = outcome.get("metadata")
        if not isinstance(metadata, dict):
            continue
        completions += 1
        usage = metadata.get("usage")
        observed = dict(usage) if isinstance(usage, dict) else {}
        details = observed.get("completion_tokens_details")
        observed["reasoning_tokens"] = (
            details.get("reasoning_tokens") if isinstance(details, dict) else None
        )
        row = {"episode_id": outcome["episode_id"], "checkpoint_id": outcome["checkpoint_id"]}
        for name in USAGE_FIELDS:
            value = observed.get(name)
            row[name] = value if nonnegative_integer(value) else None
            if row[name] is not None:
                totals[name] += value
                available[name] += 1
        if all(
            row[name] is not None for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        ):
            if row["prompt_tokens"] + row["completion_tokens"] != row["total_tokens"]:
                inconsistencies.append({**row, "reason": "total_does_not_equal_input_plus_output"})
        if all(
            row[name] is not None
            for name in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
        ):
            if (
                row["prompt_cache_hit_tokens"] + row["prompt_cache_miss_tokens"]
                != row["prompt_tokens"]
            ):
                inconsistencies.append({**row, "reason": "cache_counts_do_not_equal_input"})
        if row["reasoning_tokens"] is not None and row["completion_tokens"] is not None:
            if row["reasoning_tokens"] > row["completion_tokens"]:
                inconsistencies.append({**row, "reason": "reasoning_exceeds_output"})
        rows.append(row)
    return {
        "totals_where_reported": {
            name: totals[name] if available[name] else None for name in USAGE_FIELDS
        },
        "responses_reporting_field": available,
        "completions_received": completions,
        "attempts_without_completion_metadata": attempts_started - completions,
        "per_completion": rows,
        "inconsistencies": inconsistencies,
        "reasoning_is_already_in_completion_tokens": True,
        "missing_counts_are_not_imputed_as_zero": True,
    }


def summarize_latency(outcomes: list[dict], attempts_started: int) -> dict:
    values = []
    for outcome in outcomes:
        value = outcome.get("metadata", {}).get("elapsed_seconds")
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            values.append(value)
    return {
        "definition": LATENCY_DEFINITION,
        "observed_requests": len(values),
        "attempts_without_observed_latency": attempts_started - len(values),
        "mean_seconds": sum(values) / len(values) if values else None,
        "p50_seconds": quantile(values, 0.50),
        "p95_seconds": quantile(values, 0.95),
        "sum_observed_transport_seconds": sum(values) if values else None,
        "is_end_to_end_matrix_wall_time": False,
    }


def citation_diagnostics(score: dict) -> dict:
    slot_reasons, citation_reasons = Counter(), Counter()
    invalid_citation_reasons = Counter()
    failures = []
    for row in score["per_checkpoint"]:
        for field, slot in row["slots"].items():
            slot_reasons[slot["reason"]] += 1
            for citation in slot["citation_checks"]:
                citation_reasons[citation["reason"]] += 1
                if not citation["valid"]:
                    invalid_citation_reasons[citation["reason"]] += 1
            if not slot["grounded_correct"]:
                failures.append(
                    {
                        "episode_id": row["episode_id"],
                        "checkpoint_id": row["checkpoint_id"],
                        "field": field,
                        "value_correct": slot["value_correct"],
                        "reason": slot["reason"],
                        "citations": [
                            {key: citation[key] for key in ("citation", "valid", "reason")}
                            for citation in slot["citation_checks"]
                        ],
                    }
                )
    return {
        "slot_reason_counts": dict(sorted(slot_reasons.items())),
        "citation_reason_counts": dict(sorted(citation_reasons.items())),
        "invalid_citation_reason_counts": dict(sorted(invalid_citation_reasons.items())),
        "failed_slots": failures,
        "interpretation": "Unsupported evaluator grammar is not automatically a false model claim.",
    }


def paired_method_differences(methods: dict) -> list[dict]:
    result = []
    for left, right in itertools.combinations(methods, 2):
        events = {
            method: {row["group_id"]: row for row in methods[method]["v2"]["per_event"]}
            for method in (left, right)
        }
        if events[left].keys() != events[right].keys():
            raise ValueError("cannot pair methods with different event coverage")
        differences = []
        for event_id in sorted(events[left]):
            row = {"group_id": event_id, "metrics": {}}
            for metric in FIXED_METRICS:
                before = events[left][event_id]["metrics"][metric]
                after = events[right][event_id]["metrics"][metric]
                if before["denominator"] != after["denominator"]:
                    raise ValueError("fixed opportunity denominators differ across methods")
                row["metrics"][metric] = (
                    after["value"] - before["value"]
                    if before["value"] is not None and after["value"] is not None
                    else None
                )
            differences.append(row)
        macro = {}
        for metric in FIXED_METRICS:
            values = [row["metrics"][metric] for row in differences]
            defined = [value for value in values if value is not None]
            macro[metric] = {
                "value": sum(defined) / len(defined) if defined else None,
                "n_paired_events_defined": len(defined),
                "n_paired_events_total": len(differences),
            }
        result.append(
            {
                "difference": right + " minus " + left,
                "per_event": differences,
                "event_macro": macro,
                "inference": "descriptive paired event differences; no significance test",
            }
        )
    return result


def validate_rates(path: Path) -> dict:
    rates = read_object(path)
    if rates.get("currency") != "USD":
        raise ValueError("this report requires explicitly captured USD rates")
    if not isinstance(rates.get("model"), str) or not rates["model"]:
        raise ValueError("captured rates must identify the applicable model")
    source = Path(rates["source"]["path"])
    if not source.is_absolute() or file_hash(source) != rates["source"]["sha256"]:
        raise ValueError("captured pricing source hash mismatch")
    for name in ("input_cache_hit", "input_cache_miss", "output"):
        number = Decimal(str(rates["per_million_tokens"][name]))
        if not number.is_finite() or number < 0:
            raise ValueError("invalid token price")
    return rates


def cost_estimate(usage: dict, outcomes: list[dict], rates: dict) -> dict:
    prices = {key: Decimal(str(value)) for key, value in rates["per_million_tokens"].items()}
    cache_aware = Decimal(0)
    uncached_upper = Decimal(0)
    cache_known = input_output_known = 0
    for row in usage["per_completion"]:
        prompt, completion = row["prompt_tokens"], row["completion_tokens"]
        if prompt is None or completion is None:
            continue
        input_output_known += 1
        uncached_upper += prompt * prices["input_cache_miss"] + completion * prices["output"]
        hit, miss = row["prompt_cache_hit_tokens"], row["prompt_cache_miss_tokens"]
        if hit is None or miss is None or hit + miss != prompt:
            continue
        cache_known += 1
        cache_aware += hit * prices["input_cache_hit"] + miss * prices["input_cache_miss"]
        cache_aware += completion * prices["output"]
    window = rates.get("window", {})
    in_window = outside_window = missing_timestamp = 0
    matching_models = 0
    bounds_available = "start_utc" in window and "end_utc" in window
    if bounds_available:
        start = datetime.fromisoformat(window["start_utc"])
        end = datetime.fromisoformat(window["end_utc"])
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise ValueError("pricing window must have ordered timezone-aware bounds")
    for outcome in outcomes:
        metadata = outcome.get("metadata")
        if not isinstance(metadata, dict):
            continue
        matching_models += int(metadata.get("response_model") == rates.get("model"))
        envelope = strict_json(metadata["raw_response_body"])
        created = envelope.get("created")
        if not nonnegative_integer(created) or not bounds_available:
            missing_timestamp += 1
        elif start <= datetime.fromtimestamp(created, timezone.utc) < end:
            in_window += 1
        else:
            outside_window += 1
    all_requests_accounted = usage["attempts_without_completion_metadata"] == 0
    n = usage["completions_received"]
    window_verified = in_window == n and n > 0
    model_verified = matching_models == n and n > 0
    return {
        "currency": "USD",
        "estimated_usd": float(cache_aware / 1_000_000)
        if cache_known == n and all_requests_accounted and window_verified and model_verified
        else None,
        "cache_aware_subtotal_at_declared_rates_usd": float(cache_aware / 1_000_000)
        if cache_known
        else None,
        "responses_with_valid_cache_accounting": cache_known,
        "all_input_as_cache_miss_upper_estimate_at_declared_rates_usd": float(
            uncached_upper / 1_000_000
        )
        if input_output_known == n and all_requests_accounted
        else None,
        "responses_with_input_output_usage": input_output_known,
        "response_created_timestamps_in_pricing_window": in_window,
        "response_created_timestamps_outside_pricing_window": outside_window,
        "responses_without_verifiable_pricing_timestamp": missing_timestamp,
        "pricing_window_verified_from_provider_timestamp": window_verified,
        "response_models_match_priced_model": model_verified,
        "responses_matching_priced_model": matching_models,
        "priced_model": rates.get("model"),
        "per_million_tokens": rates["per_million_tokens"],
        "source": rates["source"],
        "window": window,
        "is_billing_receipt": False,
        "reasoning_tokens_charged_again": False,
        "note": "Usage-based estimate; missing usage/provider failures can leave total expense unknown.",
    }


def read_method(
    method: str, run_root: Path, rescore_root: Path, experiment: dict, rates: dict
) -> tuple[dict, list[dict], dict]:
    run = run_root / method
    derived = rescore_root / method
    verification = verify_rescore(derived)
    migration = read_object(derived / "manifest.json")
    context = read_object(run / "build_context.json")
    expected = experiment["expected_requests_per_method"]
    for key in ("build_id", "implementation_id", "provider_config_sha256"):
        if context[key] != experiment[key]:
            raise ValueError("collection differs from frozen experiment: " + key)
    if context["method"] != method or context["split"] != "development":
        raise ValueError("report accepts only the declared development method")
    if (
        Path(migration["original_inputs"]["run"]["path"]).resolve()
        != (run / "imported_run").resolve()
    ):
        raise ValueError("derived score does not bind this collection's imported run")
    if (
        Path(migration["original_inputs"]["build"]["path"]).resolve()
        != Path(experiment["build_path"]).resolve()
    ):
        raise ValueError("derived score does not bind the frozen build")
    v1 = read_object(run / "score.json")
    if v1 != read_object(derived / "baseline_v1.json"):
        raise ValueError("collection score differs from replayed baseline")
    v2 = read_object(derived / "score_v2.json")
    if v2["method"] != method or v1["method"] != method:
        raise ValueError("method score labels disagree")
    if any(score["metrics"]["schema_success"]["denominator"] != expected for score in (v1, v2)):
        raise ValueError("score omits frozen checkpoint opportunities")
    if set(row["group_id"] for row in v2["per_event"]) != set(experiment["development_event_ids"]):
        raise ValueError("score event coverage differs from frozen experiment")
    summary = read_object(run / "collection/summary.json")
    audit = read_object(run / "collection_audit.json")
    outcomes = read_jsonl(run / "collection/outcomes.jsonl")
    result = read_object(run / "result.json")
    if not audit["valid"] or summary != result["collection"]:
        raise ValueError("collection result/summary/audit mismatch")
    if summary["planned_checkpoints"] != expected or summary["attempts_started"] > expected:
        raise ValueError("collection request accounting differs from frozen protocol")
    for key, value in audit["counters"].items():
        if summary[key] != value:
            raise ValueError("saved audit counter differs from collection: " + key)
    if audit["verified_outcomes"] != outcomes:
        raise ValueError("saved collection outcomes differ from saved audit")
    if context["provider_config_sha256"] != file_hash(Path(experiment["provider_config_path"])):
        raise ValueError("frozen provider config bytes changed")
    config = asdict(ProviderConfig.from_dict(read_object(Path(experiment["provider_config_path"]))))
    if read_object(run / "collection/plan.json")["config"] != config:
        raise ValueError("actual collection provider configuration differs from frozen config")
    usage = summarize_usage(outcomes, summary["attempts_started"])
    response_models = Counter(
        row["metadata"]["response_model"] for row in outcomes if "metadata" in row
    )
    cost = cost_estimate(usage, outcomes, rates)
    v1_events = [
        {**row, "metrics": v1_metrics(row["metrics"])} for row in v1["event_summary"]["per_event"]
    ]
    v1_macro = dict(v1["event_summary"]["overall"]["event_macro"])
    for name in ("known_value_accuracy", "known_grounded_accuracy"):
        event_metrics = [row["metrics"][name] for row in v1_events]
        defined = [metric["value"] for metric in event_metrics if metric["value"] is not None]
        v1_macro[name] = {
            "value": sum(defined) / len(defined) if defined else None,
            "n_events_defined": len(defined),
            "n_events_total": len(event_metrics),
            "numerator_sum": sum(metric["numerator"] for metric in event_metrics),
            "denominator_sum": sum(metric["denominator"] for metric in event_metrics),
        }
    payload = {
        "method": method,
        "collection_status": summary["status"],
        "request_accounting": {
            key: summary[key]
            for key in (
                "planned_checkpoints",
                "attempts_started",
                "completions_received",
                "accepted_decisions",
                "invalid_decisions",
                "unsubmitted_checkpoints",
                "reserved_output_tokens",
                "request_bytes_sent",
                "stop_error",
                "stop_guard",
            )
        },
        "status_counts": v2["status_counts"],
        "finish_reasons": dict(
            sorted(
                Counter(
                    row.get("metadata", {}).get("finish_reason", "no_completion")
                    for row in outcomes
                ).items()
            )
        ),
        "provider_error_codes": dict(
            sorted(
                Counter(
                    row["error"]["code"] for row in outcomes if row["status"] == "provider_error"
                ).items()
            )
        ),
        "response_models": dict(sorted(response_models.items())),
        "v1": {
            "metrics": v1_metrics(v1["metrics"]),
            "per_event": v1_events,
            "event_macro": v1_macro,
            "conditional_metrics_are_model_dependent": True,
        },
        "v2": {
            key: v2[key]
            for key in (
                "scorer_version",
                "evidence_policy_version",
                "counts",
                "metrics",
                "per_event",
                "event_macro",
                "paired_delay_minus_base",
            )
        },
        "scoring_difference": read_object(derived / "comparison.json"),
        "evidence_diagnostics": citation_diagnostics(v2),
        "failed_checkpoints": [
            {key: row[key] for key in ("episode_id", "checkpoint_id", "status", "action_correct")}
            for row in v2["per_checkpoint"]
            if not row["all_correct"]
        ],
        "reported_usage": usage,
        "transport_latency": summarize_latency(outcomes, summary["attempts_started"]),
        "cost_estimate": cost,
        "verification": verification,
    }
    bindings = {
        str(path.resolve()): file_hash(path)
        for root, names in (
            (
                run,
                (
                    "build_context.json",
                    "result.json",
                    "score.json",
                    "collection_audit.json",
                    "collection/summary.json",
                    "collection/outcomes.jsonl",
                ),
            ),
            (derived, ("manifest.json", "baseline_v1.json", "score_v2.json", "comparison.json")),
        )
        for name in names
        for path in (root / name,)
    }
    return payload, outcomes, bindings


def format_rate(metric: dict) -> str:
    value = metric["value"]
    suffix = f" ({100 * value:.2f}%)" if value is not None else " (undefined)"
    return str(metric["numerator"]) + "/" + str(metric["denominator"]) + suffix


def budget_accounting(runs_root: Path, experiment: dict, methods: dict) -> dict | None:
    path = runs_root.parent / "budget_ledger.json"
    if not path.exists():
        return None
    ledger = read_object(path)
    if ledger.get("experiment_id") != experiment["experiment_id"]:
        raise ValueError("budget ledger belongs to a different experiment")
    if ledger.get("budget") != experiment["budget"]:
        raise ValueError("budget ledger differs from the frozen budget")
    rows = ledger["attempts"]
    if ledger["provider_attempts_started"] != len(rows):
        raise ValueError("budget ledger provider attempt count mismatch")
    if [row["attempt_number"] for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("budget ledger attempt sequence mismatch")
    observed = Counter(
        (method, request["prepared"]["request_sha256"])
        for method in methods
        for request in read_jsonl(runs_root / method / "collection/requests.jsonl")
    )
    admitted = Counter((row["method"], row["request_sha256"]) for row in rows)
    if any(admitted[key] > observed[key] for key in admitted):
        raise ValueError("budget ledger contains an attempt absent from collection journals")
    collector_count = sum(
        method["request_accounting"]["attempts_started"] for method in methods.values()
    )
    if collector_count != len(rows) + ledger["guard_denials_before_provider"]:
        raise ValueError("collector/admitted/guard-denied request accounting mismatch")
    completions = sum(
        method["request_accounting"]["completions_received"] for method in methods.values()
    )
    if ledger["provider_completions_received"] != completions:
        raise ValueError("ledger completion count differs from collection")
    return {
        "path": str(path.resolve()),
        "sha256": file_hash(path),
        "collector_attempts_started": collector_count,
        "provider_calls_admitted": len(rows),
        "provider_calls_admitted_per_method": dict(Counter(row["method"] for row in rows)),
        **{
            key: ledger[key]
            for key in (
                "guard_denials_before_provider",
                "provider_completions_received",
                "conservative_reported_cost_usd",
                "pending_reservation_usd",
                "halted",
                "halt_reason",
                "conditional_budget_assumptions_satisfied",
                "monetary_cap_enforced",
                "billing_guarantee",
                "started_at",
                "updated_at",
                "elapsed_seconds",
                "interpretation",
            )
        },
        "provider_receipt_authenticated": False,
    }


def markdown(report: dict) -> str:
    methods = report["methods"]
    lines = [
        "# DeepSeek development method calibration",
        "",
        "Status: " + report["matrix_status"] + ".",
        "",
        report["interpretation"],
        "",
        f"Independent storms: {report['independent_event_count']}; "
        f"collector attempts: {report['collector_attempts']}/{report['expected_provider_attempts']}; "
        f"provider calls admitted by external ledger: {report['provider_calls_admitted']}; "
        f"methods present: {len(methods)}/{len(report['declared_methods'])}. "
        "This report itself makes zero provider requests.",
        "",
        "## V2 metrics",
        "",
        "| Metric | " + " | ".join(methods) + " |",
        "| --- | " + " | ".join("---" for _ in methods) + " |",
    ]
    if methods:
        for metric in next(iter(methods.values()))["v2"]["metrics"]:
            lines.append(
                "| "
                + metric
                + " | "
                + " | ".join(
                    format_rate(methods[method]["v2"]["metrics"][metric]) for method in methods
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "V1 conditional change/preservation and V2 conditional self-error recovery "
            "are not interchangeable with fixed opportunity metrics. Zero opportunities "
            "are undefined, not perfect performance.",
            "",
            "## Per-event grounding",
            "",
            "| Method | Storm | V1 known grounding | V2 known grounding | V2 unknown |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for method, result in methods.items():
        before = {row["group_id"]: row for row in result["v1"]["per_event"]}
        for row in result["v2"]["per_event"]:
            event = row["group_id"]
            lines.append(
                f"| {method} | {event} | "
                + format_rate(before[event]["metrics"]["known_grounded_accuracy"])
                + " | "
                + format_rate(row["metrics"]["known_grounded_accuracy"])
                + " | "
                + format_rate(row["metrics"]["unknown_accuracy"])
                + " |"
            )
    lines.extend(
        [
            "",
            "## Telemetry",
            "",
            "| Method | Collector attempts | Accepted / invalid | Prompt / completion tokens | "
            "Mean / p50 / p95 seconds | Estimated USD |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for method, result in methods.items():
        counts = result["request_accounting"]
        usage = result["reported_usage"]["totals_where_reported"]
        latency = result["transport_latency"]
        seconds = " / ".join(
            "unknown" if latency[key] is None else f"{latency[key]:.3f}"
            for key in ("mean_seconds", "p50_seconds", "p95_seconds")
        )
        cost = result["cost_estimate"]["estimated_usd"]
        lines.append(
            f"| {method} | {counts['attempts_started']} | "
            f"{counts['accepted_decisions']} / {counts['invalid_decisions']} | "
            f"{usage['prompt_tokens']} / {usage['completion_tokens']} | {seconds} | "
            + (f"{cost:.9f}" if cost is not None else "unknown")
            + " |"
        )
    totals = report["reported_usage"]["totals_where_reported"]
    lines.extend(
        [
            "",
            LATENCY_DEFINITION,
            "",
            "Reported totals: "
            + ", ".join(f"{key}={value}" for key, value in totals.items())
            + ".",
            "Reasoning tokens are included in completion tokens and are not charged again.",
            "Cost uses the captured pricing file and returned cache hit/miss counts. "
            "It is an estimate, not an invoice; unknown usage is not replaced with zero.",
            "",
            "## Paired method differences",
            "",
            "| Difference | Event-macro V2 known grounding difference | Paired events |",
            "| --- | --- | --- |",
        ]
    )
    for difference in report["paired_method_differences"]:
        metric = difference["event_macro"]["known_grounded_accuracy"]
        value = metric["value"]
        lines.append(
            "| "
            + difference["difference"]
            + " | "
            + (f"{100 * value:+.2f} percentage points" if value is not None else "undefined")
            + f" | {metric['n_paired_events_defined']}/{metric['n_paired_events_total']} |"
        )
    lines.extend(
        [
            "",
            "Full numerator/denominator metrics, event macro values, branch differences, "
            "failed checkpoints, citation reason counts and input hashes are in report.json. "
            "All received invalid answers and all unsubmitted checkpoints stay in scoring denominators.",
            "",
            "Original collection/score artifacts are preserved. Each derived package was "
            "independently replayed and verified before aggregation. No heldout calls or "
            "additional model repeats are represented here.",
            "",
        ]
    )
    return "\n".join(lines)


def create_report(
    experiment_path: Path,
    runs_root: Path,
    rescores_root: Path,
    rates_path: Path,
    output: Path,
    *,
    allow_partial: bool = False,
) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("report output exists; choose a fresh directory")
    if any(output.resolve().is_relative_to(root.resolve()) for root in (runs_root, rescores_root)):
        raise ValueError("report output must be outside collection and rescore roots")
    experiment = read_object(experiment_path)
    if experiment.get("experiment_id") != fingerprint(
        {key: value for key, value in experiment.items() if key != "experiment_id"}
    ):
        raise ValueError("frozen experiment fingerprint mismatch")
    declared = experiment["methods"]
    if declared != list(METHODS) or experiment["repeats"] != 1:
        raise ValueError("report supports the declared three-method, one-repeat protocol")
    expected = experiment["expected_requests_per_method"]
    if (
        not nonnegative_integer(expected)
        or expected == 0
        or experiment["total_requests"] != expected * len(declared)
    ):
        raise ValueError("invalid frozen request matrix")
    if (
        Path(experiment["rates_path"]).resolve() != rates_path.resolve()
        or file_hash(rates_path) != experiment["rates_sha256"]
    ):
        raise ValueError("pricing file differs from frozen experiment")
    rates = validate_rates(rates_path)
    frozen_config = read_object(Path(experiment["provider_config_path"]))
    if rates["model"] != frozen_config["model"]:
        raise ValueError("pricing model differs from frozen provider model")
    methods, all_outcomes, input_hashes = {}, [], {}
    input_hashes[str(experiment_path.resolve())] = file_hash(experiment_path)
    input_hashes[str(rates_path.resolve())] = file_hash(rates_path)
    input_hashes[str(Path(rates["source"]["path"]).resolve())] = rates["source"]["sha256"]
    config_path = Path(experiment["provider_config_path"])
    input_hashes[str(config_path.resolve())] = file_hash(config_path)
    missing_methods = []
    for method in declared:
        if not (runs_root / method).exists() and not (rescores_root / method).exists():
            if not allow_partial:
                raise ValueError("required method collection/rescore is missing: " + method)
            missing_methods.append(method)
            continue
        payload, outcomes, bindings = read_method(
            method, runs_root, rescores_root, experiment, rates
        )
        methods[method] = payload
        all_outcomes.extend(outcomes)
        input_hashes.update(bindings)
    if not methods:
        raise ValueError("no verified method results to report")
    attempts = sum(row["request_accounting"]["attempts_started"] for row in methods.values())
    ledger = budget_accounting(runs_root, experiment, methods)
    admitted = ledger["provider_calls_admitted"] if ledger is not None else None
    if ledger is not None:
        input_hashes[ledger["path"]] = ledger["sha256"]
        for method, result in methods.items():
            count = ledger["provider_calls_admitted_per_method"].get(method, 0)
            result["request_accounting"]["provider_calls_admitted"] = count
            outcomes = read_jsonl(runs_root / method / "collection/outcomes.jsonl")
            result["reported_usage"] = summarize_usage(outcomes, count)
            result["transport_latency"] = summarize_latency(outcomes, count)
            result["cost_estimate"] = cost_estimate(result["reported_usage"], outcomes, rates)
    usage = summarize_usage(all_outcomes, admitted if admitted is not None else attempts)
    complete = not missing_methods and all(
        row["collection_status"] == "completed" for row in methods.values()
    )
    report = {
        "schema_version": "deepseek_development_report_v1",
        "experiment_id": experiment["experiment_id"],
        "build_id": experiment["build_id"],
        "implementation_id": experiment["implementation_id"],
        "matrix_status": "completed" if complete else "incomplete_descriptive_only",
        "declared_methods": declared,
        "missing_methods": missing_methods,
        "independent_event_count": len(experiment["development_event_ids"]),
        "development_event_ids": experiment["development_event_ids"],
        "repeats": 1,
        "collector_attempts": attempts,
        "provider_calls_admitted": admitted,
        "provider_call_accounting": ledger,
        "expected_provider_attempts": experiment["total_requests"],
        "new_provider_requests_by_report": 0,
        "methods": methods,
        "paired_method_differences": paired_method_differences(methods),
        "reported_usage": usage,
        "transport_latency": summarize_latency(
            all_outcomes, admitted if admitted is not None else attempts
        ),
        "cost_estimate": cost_estimate(usage, all_outcomes, rates),
        "input_sha256": input_hashes,
        "interpretation": INTERPRETATION,
        "eligible_for_llm_leaderboard": False,
    }
    if any(file_hash(Path(path)) != digest for path, digest in input_hashes.items()):
        raise ValueError("report inputs changed during aggregation")
    output.mkdir(parents=True)
    write_json(output / "report.json", report)
    (output / "REPORT.md").write_text(markdown(report), encoding="ascii")
    manifest = {
        "schema_version": "offline_development_report_manifest_v1",
        "experiment_id": experiment["experiment_id"],
        "report_script_sha256": file_hash(Path(__file__)),
        "input_sha256": input_hashes,
        "new_provider_requests": 0,
        "files": {name: file_hash(output / name) for name in ("report.json", "REPORT.md")},
    }
    manifest["report_id"] = fingerprint(manifest)
    write_json(output / "manifest.json", manifest)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--rescores-root", type=Path, required=True)
    parser.add_argument("--rates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-partial", action="store_true", help="label missing methods explicitly"
    )
    args = parser.parse_args()
    report = create_report(
        args.experiment,
        args.runs_root,
        args.rescores_root,
        args.rates,
        args.output,
        allow_partial=args.allow_partial,
    )
    print(
        "Offline report: "
        + report["matrix_status"]
        + f"; collector attempts={report['collector_attempts']}; "
        + f"provider calls admitted={report['provider_calls_admitted']}; "
        "new requests by report=0"
    )


if __name__ == "__main__":
    main()
