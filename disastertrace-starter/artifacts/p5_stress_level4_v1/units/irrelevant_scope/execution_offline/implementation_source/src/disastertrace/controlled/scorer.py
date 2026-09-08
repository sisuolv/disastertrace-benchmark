"""Fixed-opportunity P2 scoring from actual diagnostic traces, without projections."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy

from disastertrace.automated.common import canonical, fingerprint

from .compiler import reference_at
from .renderer import render_request
from .schema import FIELDS, METHODS, parse_decision, validate_episode

SCORER_VERSION = "controlled_score_v1"
METRICS = {
    "schema_success": ("schema_valid", "checkpoints"),
    "known_value_accuracy": ("known_value_correct", "known"),
    "known_grounded_accuracy": ("known_grounded_correct", "known"),
    "unknown_accuracy": ("unknown_correct", "unknown"),
    "overall_grounding": ("grounded_correct", "fields"),
    "action_accuracy": ("action_correct", "checkpoints"),
    "update_success": ("updates_correct", "updates"),
    "preservation": ("preservations_correct", "preservations"),
    "provenance_refresh": ("refreshes_correct", "refreshes"),
    "support_recovery": ("recoveries_correct", "recoveries"),
    "same_window_correction": ("corrections_correct", "corrections"),
    "stale_replay_preservation": ("stale_correct", "stale"),
    "scope_preservation": ("scope_correct", "scope"),
    "all_correct_checkpoints": ("all_correct", "checkpoints"),
}
COUNT_KEYS = {key for pair in METRICS.values() for key in pair}


def rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _summarize(rows: list[dict]) -> dict:
    counts = {name: sum(r["counts"][name] for r in rows) for name in sorted(COUNT_KEYS)}
    return {
        "counts": counts,
        "metrics": {name: rate(counts[n], counts[d]) for name, (n, d) in METRICS.items()},
    }


def score(episodes: list[dict], traces: list[dict], method: str) -> dict:
    for row in traces:
        if (
            row["model_kind"] != "diagnostic_program"
            or row["eligible_for_llm_leaderboard"] is not False
            or type(row["provider_requests"]) is not int
            or row["provider_requests"] != 0
        ):
            raise ValueError("only offline diagnostic traces admitted by this scorer")
    return {
        **_score_rows(episodes, traces, method),
        "model_calls": 0,
        "model_kind": "diagnostic_program",
        "eligible_for_llm_leaderboard": False,
    }


def _score_rows(episodes, traces, method, *, missing_status=None):
    """Shared metric arithmetic; callers must first establish response provenance."""
    if method not in METHODS:
        raise ValueError("unknown method")
    expected_order = [
        (ep["episode_id"], cp["checkpoint_id"]) for ep in episodes for cp in ep["checkpoints"]
    ]
    if len(set(expected_order)) != len(expected_order):
        raise ValueError("duplicate planned opportunity")
    indexed, previous_position = {}, -1
    for row in traces:
        key = (row["episode_id"], row["checkpoint_id"])
        if key not in expected_order or key in indexed:
            raise ValueError("unexpected or duplicate response")
        position = expected_order.index(key)
        if position <= previous_position:
            raise ValueError("response order changed")
        previous_position = position
        indexed[key] = row
    results = []
    for ep in episodes:
        validate_episode(ep)
        previous, history, prior_gold = None, [], None
        for cp in ep["checkpoints"]:
            key = (ep["episode_id"], cp["checkpoint_id"])
            row = indexed.get(key)
            status, decision = (missing_status or {}).get(key, "unsubmitted"), None
            if row is not None:
                if row["method"] != method:
                    raise ValueError("response method mismatch")
                request = render_request(
                    ep, cp["checkpoint_id"], method=method, previous=previous, history=history
                )
                if canonical(row["request"]) != canonical(request) or row[
                    "request_hash"
                ] != fingerprint(request):
                    raise ValueError("actual request or carrier mismatch")
                try:
                    decision = parse_decision(row["raw_response"])
                except (ValueError, TypeError, KeyError, RecursionError):
                    status = "invalid"
                else:
                    status = "ok"
                    previous = decision
                    history.append(deepcopy(decision))
                if row["status"] != status or canonical(row["state_after"]) != canonical(previous):
                    raise ValueError("response acceptance or carried state mismatch")
            gold = reference_at(ep, cp["checkpoint_id"])
            counts = {name: 0 for name in COUNT_KEYS}
            counts.update(checkpoints=1, fields=len(FIELDS), schema_valid=int(decision is not None))
            counts["action_correct"] = int(
                decision is not None and decision["action"] == gold["action"]
            )
            slots = {}
            for field in FIELDS:
                expected = gold["state"][field]
                submitted = None if decision is None else decision["state"][field]
                known = expected["status"] == "known"
                value_ok = submitted is not None and (submitted["status"], submitted["value"]) == (
                    expected["status"],
                    expected["value"],
                )
                support_ok = value_ok and (
                    not known
                    or bool(submitted["evidence"])
                    and all(ref in expected["evidence"] for ref in submitted["evidence"])
                )
                reason = (
                    status
                    if submitted is None
                    else (
                        "status_or_value_mismatch"
                        if not value_ok
                        else (
                            "supported"
                            if support_ok
                            else "wrong_or_missing_current_version_citation"
                        )
                    )
                )
                counts["known" if known else "unknown"] += 1
                counts["known_value_correct"] += int(known and value_ok)
                counts["known_grounded_correct"] += int(known and support_ok)
                counts["unknown_correct"] += int(not known and support_ok)
                counts["grounded_correct"] += int(support_ok)
                if prior_gold is not None:
                    prior = prior_gold["state"][field]
                    changed = known and prior != expected
                    preserved = known and prior == expected
                    refresh = (
                        changed
                        and prior["status"] == "known"
                        and prior["value"] == expected["value"]
                    )
                    recovery = (
                        known
                        and prior["status"] == "unknown"
                        and ep["family"] == "U3"
                        and cp["checkpoint_id"] == "c3"
                    )
                    for label, opportunity in (
                        ("updates", changed),
                        ("preservations", preserved),
                        ("refreshes", refresh),
                        ("recoveries", recovery),
                    ):
                        counts[label] += int(opportunity)
                        counts[label + "_correct"] += int(opportunity and support_ok)
                if ep["family"] == "U2" and field == "maximum_wind_mph":
                    for label, opportunity in (
                        ("corrections", cp["checkpoint_id"] == "c2" and ep["branch"] == "active"),
                        ("stale", cp["checkpoint_id"] == "c3"),
                        ("scope", cp["checkpoint_id"] == "c4"),
                    ):
                        counts[label] += int(opportunity)
                        counts[label + "_correct"] += int(opportunity and support_ok)
                slots[field] = {
                    "value_correct": value_ok,
                    "grounded_correct": support_ok,
                    "reason": reason,
                }
            counts["all_correct"] = int(
                counts["grounded_correct"] == len(FIELDS) and counts["action_correct"] == 1
            )
            results.append(
                {
                    "episode_id": ep["episode_id"],
                    "root_id": ep["root_id"],
                    "group_id": ep["group_id"],
                    "family": ep["family"],
                    "branch": ep["branch"],
                    "checkpoint_id": cp["checkpoint_id"],
                    "status": status,
                    "slots": slots,
                    "counts": counts,
                }
            )
            prior_gold = gold
    by_group = {
        group: _summarize([row for row in results if row["group_id"] == group])
        for group in sorted({ep["group_id"] for ep in episodes})
    }
    by_family = {
        family: _summarize([row for row in results if row["family"] == family])
        for family in sorted({ep["family"] for ep in episodes})
    }
    pairs = []
    for root in sorted({ep["root_id"] for ep in episodes}):
        members = [ep for ep in episodes if ep["root_id"] == root]
        if len(members) == 2 and {ep["branch"] for ep in members} == {"active", "control"}:
            values = [row for row in results if row["root_id"] == root]
            successes = sum(
                all(
                    row["counts"]["all_correct"] == 1
                    for row in values
                    if row["checkpoint_id"] == cp
                )
                for cp in (f"c{i}" for i in range(5))
            )
            pairs.append({"root_id": root, "both_correct": rate(successes, 5)})
    macro = {}
    for metric in METRICS:
        values = [
            group["metrics"][metric]["value"]
            for group in by_group.values()
            if group["metrics"][metric]["value"] is not None
        ]
        macro[metric] = {
            "contributing_groups": len(values),
            "value": sum(values) / len(values) if values else None,
        }
    return {
        "schema_version": SCORER_VERSION,
        "method": method,
        **_summarize(results),
        "status_counts": dict(Counter(row["status"] for row in results)),
        "by_group": by_group,
        "by_family": by_family,
        "event_macro": macro,
        "matched_pairs": pairs,
        "per_checkpoint": results,
        "interpretation": (
            "Fixed planned opportunities; dependent branches and checkpoints "
            "are not independent weather events."
        ),
    }
