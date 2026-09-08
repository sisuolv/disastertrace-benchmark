"""Descriptive transport/usage reporting, separate from conservative reservations."""

import math
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median

from .provider import ProviderError
from .provider_capture import parse_capture

PEAK_RULE = "Monday-Friday 01:00-04:00 and 06:00-10:00 UTC; all other times are off-peak"
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _window(start, end):
    try:
        start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if (
            start.utcoffset() != timedelta(0)
            or end.utcoffset() != timedelta(0)
            or not 0 <= (end - start).total_seconds() <= 86400
        ):
            return None
    except (ValueError, TypeError):
        return None
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        if day.weekday() < 5:
            for hour in (1, 4, 6, 10):
                if start < day.replace(hour=hour) <= end:
                    return None
        day += timedelta(days=1)
    peak = start.weekday() < 5 and (1 <= start.hour < 4 or 6 <= start.hour < 10)
    return "peak" if peak else "off_peak"


def estimate_captured_cost(usage, send_intent_at, capture_observed_at, rates):
    """Return a conditional snapshot-rate estimate only with validated cache/window data."""
    result = {"usd": None, "window": None, "status": "unsupported_price_snapshot"}
    if (
        rates.get("schema_version") != "deepseek_price_snapshot_v1"
        or rates.get("currency") != "USD"
        or rates.get("model") != "deepseek-v4-flash"
        or rates.get("window", {}).get("timezone") != "UTC"
        or rates.get("window", {}).get("peak_rule") != PEAK_RULE
        or rates.get("window", {}).get("kind") != "off_peak"
    ):
        return result
    window = _window(send_intent_at, capture_observed_at)
    if window is None:
        return {**result, "status": "unverified_time_window"}
    if (
        not isinstance(usage, dict)
        or any(type(usage.get(k)) is not int or usage[k] < 0 for k in TOKEN_FIELDS)
        or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]
    ):
        return {**result, "window": window, "status": "unverified_usage"}
    hit, miss = usage.get("prompt_cache_hit_tokens"), usage.get("prompt_cache_miss_tokens")
    if (
        type(hit) is not int
        or type(miss) is not int
        or hit < 0
        or miss < 0
        or hit + miss != usage["prompt_tokens"]
    ):
        return {**result, "window": window, "status": "unverified_cache_usage"}
    table = rates["peak_per_million_tokens" if window == "peak" else "per_million_tokens"]
    cost = (
        hit * Decimal(str(table["input_cache_hit"]))
        + miss * Decimal(str(table["input_cache_miss"]))
        + usage["completion_tokens"] * Decimal(str(table["output"]))
    ) / Decimal(1000000)
    return {"usd": str(cost), "window": window, "status": "estimated_from_capture"}


def summarize_observations(plan, audit, slot_indices=None):
    indices = set(range(270) if slot_indices is None else slot_indices)
    records = list(audit["records"])
    if audit["pending"] is not None:
        records.append(audit["pending"])
    records = [r for r in records if r["slot_index"] in indices]
    usage_totals = dict.fromkeys(TOKEN_FIELDS, 0)
    usage_count = attempted = 0
    elapsed, details = [], []
    failures, estimate_statuses = Counter(), Counter()
    subtotal = Decimal(0)
    covered = 0
    for row in records:
        sent = row["phase"] != "reserved"
        attempted += int(sent)
        capture = row.get("capture")
        completion, usage = row.get("completion"), None
        if capture is not None:
            elapsed.append(capture["elapsed_seconds"])
            if capture["error_code"]:
                failures[capture["error_code"]] += 1
            if completion is None:
                try:
                    completion = parse_capture(capture, row["prepared"])
                except ProviderError as exc:
                    if exc.code != capture["error_code"]:
                        failures[exc.code] += 1
        if completion is not None:
            metadata = completion["metadata"]
            candidate = metadata["usage"]
            if metadata["response_model"] != row["prepared"]["config"]["model"]:
                failures["model_mismatch"] += 1
            elif candidate is not None and (
                candidate["prompt_tokens"] <= plan["budget"]["prompt_bound"]
                and candidate["completion_tokens"] <= row["prepared"]["config"]["max_output_tokens"]
            ):
                usage = candidate
                usage_count += 1
                for key in TOKEN_FIELDS:
                    usage_totals[key] += usage[key]
            else:
                failures["usage_unverified"] += 1
            failures["length"] += metadata["finish_reason"] == "length"
            failures["empty"] += not completion["raw_response"].strip()
        failures["schema_invalid"] += row.get("status") == "invalid"
        estimate = estimate_captured_cost(
            usage, row.get("send_intent_at"), row.get("capture_observed_at"), plan["rates"]
        )
        if sent:
            estimate_statuses[estimate["status"]] += 1
        if estimate["usd"] is not None:
            subtotal += Decimal(estimate["usd"])
            covered += 1
        details.append(
            {
                "slot_index": row["slot_index"],
                "attempted": sent,
                "send_intent_at": row.get("send_intent_at"),
                "capture_observed_at": row.get("capture_observed_at"),
                "elapsed_seconds": capture["elapsed_seconds"] if capture else None,
                "usage": usage,
                "cost_estimate": estimate,
            }
        )
    accounting = [r for index, r in enumerate(audit["accounting_rows"]) if index in indices]
    elapsed.sort()
    return {
        "attempted": attempted,
        "usage": {"verified_responses": usage_count, **usage_totals},
        "latency_seconds": {
            "count": len(elapsed),
            "mean": sum(elapsed) / len(elapsed) if elapsed else None,
            "median": median(elapsed) if elapsed else None,
            "p95_nearest_rank": elapsed[math.ceil(0.95 * len(elapsed)) - 1] if elapsed else None,
            "max": max(elapsed) if elapsed else None,
        },
        "failure_counts": dict(sorted(failures.items())),
        "failure_counts_may_overlap": True,
        "settled_conservative_usd": str(sum((Decimal(r["cost"]) for r in accounting), Decimal(0))),
        "unsettled_reservation_usd": str(
            sum(
                (Decimal(r["reservation"]) for r in accounting if r["status"] != "settled"),
                Decimal(0),
            )
        ),
        "unknown_reservation_usd": str(
            sum(
                (Decimal(r["reservation"]) for r in accounting if r["status"] == "unknown"),
                Decimal(0),
            )
        ),
        "cost_estimate": {
            "basis": "diagnostic_simulation"
            if audit["mode"] != "urllib_http"
            else "captured_rates_local_utc_window",
            "subtotal_usd": str(subtotal),
            "covered_attempts": covered,
            "all_attempts_covered": covered == attempted and attempted > 0,
            "statuses": dict(sorted(estimate_statuses.items())),
            "rates_sha256": plan["rates_sha256"],
            "price_snapshot_retrieved_at": plan["rates"]["source"]["retrieved_at"],
            "provider_billing_time_verified": False,
            "total_incurred_usd": None,
            "not_invoice": True,
        },
        "requests": details,
    }
