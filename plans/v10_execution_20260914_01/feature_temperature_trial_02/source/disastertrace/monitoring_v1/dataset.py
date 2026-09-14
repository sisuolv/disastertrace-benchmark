"""Explicit policy-side file allowlist; evaluator outcomes are loaded elsewhere."""

from __future__ import annotations

import json
from pathlib import Path

from .providers.taf_timeline import target_withdrawals


def load_session(
    dataset,
    *,
    stations,
    hours=None,
    threshold=1000,
    native_version_policy="latest_before_coverage.v2",
):
    dataset = Path(dataset)

    def load(name):
        return json.loads((dataset / name).read_text())

    targets = {t["target_id"]: t for t in load("public/TARGETS.json")}
    opportunities = [
        o
        for o in load("public/OPPORTUNITIES.json")
        if o["threshold_m"] == threshold and targets[o["target_id"]]["entity"] in stations
    ]
    cutoffs = sorted({o["cutoff"] for o in opportunities})
    if hours is not None:
        cutoffs = cutoffs[:hours]
        opportunities = [o for o in opportunities if o["cutoff"] in cutoffs]
    if not opportunities:
        raise ValueError("Selected policy session has no registered opportunities")
    ids = {o["opportunity_id"] for o in opportunities}
    target_ids = {o["target_id"] for o in opportunities}
    catalog = {q["query_id"]: q for q in load("public/QUERY_CATALOG.json")}
    pairs = [p for p in load("public/E_F_PAIRS.json") if p["opportunity_id"] in ids]
    for pair in pairs:
        pair["query_ids"] = [q for q in pair["query_ids"] if catalog[q]["station"] in stations]
        if not pair["query_ids"]:
            raise ValueError("At least two sites required for the neighboring-report E predicate")
        pair["registered_region_sites"] = list(stations)
    query_ids = {q for p in pairs for q in p["query_ids"]}
    return {
        "schema": "disastertrace.monitoring.policy_environment.v1",
        "native_version_policy": native_version_policy,
        "stations": list(stations),
        "targets": [targets[key] for key in sorted(target_ids)],
        "baseline_withdrawals": target_withdrawals(
            load("environment/NATIVE_PRODUCT_INDEX.json"),
            [targets[key] for key in sorted(target_ids)],
            max(cutoffs),
            version_policy=native_version_policy,
        ),
        "opportunities": opportunities,
        "e_f_pairs": pairs,
        "query_catalog": [catalog[q] for q in sorted(query_ids)],
        "query_results": [
            q for q in load("environment/QUERY_RESULTS.json") if q["query_id"] in query_ids
        ],
        "baseline_candidates": [
            b
            for b in load("environment/BASELINE_CANDIDATES.json")
            if b["target_id"] in target_ids and b["available_at"] <= max(cutoffs)
        ],
    }
