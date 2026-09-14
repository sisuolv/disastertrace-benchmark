"""Source-defined existential report facts and finite sufficient recipes."""

from __future__ import annotations

import math
from itertools import combinations

from .support import Interval, classify


def interval_from_dict(value):
    def bound(x):
        return math.inf if x == "+inf" else -math.inf if x == "-inf" else x

    return Interval(
        bound(value["lower"]),
        bound(value["upper"]),
        value.get("lower_closed", True),
        value.get("upper_closed", True),
    )


def report_fact_status(result, threshold):
    if result.get("status") == "inconsistent_same_slot_facts":
        return "inconsistent"
    if (
        result.get("status") != "disclosed_product_fact"
        or result.get("reference_kind") != "product_label"
        or result.get("support_assumption") != "product_exact"
        or result.get("visible_information_scope") not in {"policy", "policy_after_query"}
        or len(result.get("reports", [])) != 1
    ):
        return "undetermined"
    report = result["reports"][0]
    if report.get("visibility") is None:
        return "undetermined"
    return classify(interval_from_dict(report["visibility"]), "lt", threshold)


def exists_report_support(query_ids, disclosed_results, threshold):
    if not query_ids or len(set(query_ids)) != len(query_ids):
        raise ValueError("Register a nonempty unique finite slot set")
    statuses = [
        report_fact_status(disclosed_results[q], threshold)
        if q in disclosed_results
        else "undetermined"
        for q in query_ids
    ]
    if "inconsistent" in statuses:
        return "inconsistent"
    if "supported" in statuses:
        return "supported"
    if all(s == "refuted" for s in statuses):
        return "refuted"
    return "undetermined"


def sufficient_recipes(query_ids, archive_results, threshold, *, max_queries=12):
    """Hindsight evaluator reference only; never serialize this into policy views."""
    if len(query_ids) > max_queries:
        raise ValueError("Exact recipe enumeration exceeds registered finite limit")
    recipes = []
    for size in range(len(query_ids) + 1):
        for selected in combinations(query_ids, size):
            chosen = frozenset(selected)
            if any(existing <= chosen for existing in recipes):
                continue
            disclosed = {q: archive_results[q] for q in selected if q in archive_results}
            if exists_report_support(query_ids, disclosed, threshold) in {"supported", "refuted"}:
                recipes.append(chosen)
    return tuple(recipes)


def taf_features(projection, threshold):
    prevailing, conditional = [], []
    operators = set()
    for segment in projection["segments"]:
        prevailing.extend(
            classify(interval_from_dict(state["visibility"]), "lt", threshold)
            for state in segment["prevailing"]
        )
        for condition in segment["conditional"]:
            operators.add(condition["operator"])
            conditional.extend(
                classify(interval_from_dict(state["visibility"]), "lt", threshold)
                for state in condition["states"]
            )

    def category(values):
        return (
            "any_low"
            if "supported" in values
            else "uncertain"
            if "undetermined" in values or "inconsistent" in values
            else "no_low"
        )

    return {
        "prevailing": category(prevailing),
        "conditional": category(conditional),
        "conditional_operators": sorted(operators),
        "has_conditionals": bool(conditional),
    }


def evidence_features(query_ids, disclosed_results, threshold):
    statuses = [
        report_fact_status(disclosed_results[q], threshold)
        for q in query_ids
        if q in disclosed_results
    ]
    return {
        "read": len(statuses),
        "low": statuses.count("supported"),
        "not_low": statuses.count("refuted"),
        "unresolved": statuses.count("undetermined") + statuses.count("inconsistent"),
    }
