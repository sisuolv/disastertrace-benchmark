"""Score deterministic source-selection controls on the bounded dev outcomes.

The evaluator is deliberately separate from the actor bridge.  It reads the
source-only TAF qualification artifact and the evaluator-only ASOS binding,
then applies one frozen, shared forecast map to four one-query arms.  It is a
real development diagnostic, not a provider/model result: model_calls and
provider_calls remain zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping

from disastertrace.monitoring_v1.public_query_selectors import query_priority


METHODS = ("fixed", "earliest_source", "hash_source", "active_age")
THRESHOLD_M = 5000.0
SEED = 17


def _projection_probability(projection: Mapping[str, Any], target_start: int, target_end: int) -> float:
    periods = projection.get("periods")
    if not isinstance(periods, list):
        return 0.5
    lower_values: list[float] = []
    for period in periods:
        if not isinstance(period, Mapping):
            continue
        start, end = period.get("valid_start"), period.get("valid_end")
        if not isinstance(start, int) or not isinstance(end, int) or end <= target_start or start >= target_end:
            continue
        interval = period.get("visibility_m")
        if not isinstance(interval, Mapping):
            continue
        lower = interval.get("lower")
        if isinstance(lower, (int, float)) and not isinstance(lower, bool) and math.isfinite(float(lower)):
            lower_values.append(float(lower))
    if not lower_values:
        return 0.5
    return 0.8 if min(lower_values) < THRESHOLD_M else 0.2


def _source_rows(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for qualification in checkpoint.get("qualifications", []):
        if qualification.get("availability") != "available":
            continue
        witness = qualification.get("witness", {})
        identity = witness.get("source_identity")
        projection = witness.get("current_projection")
        if not isinstance(identity, Mapping) or not isinstance(projection, Mapping):
            continue
        query_id, available_at = identity.get("source_id"), witness.get("available_at")
        if not isinstance(query_id, str) or not query_id or not isinstance(available_at, int):
            raise ValueError("available TAF witness has invalid identity or availability")
        rows.setdefault(query_id, {"query_id": query_id, "available_at": available_at, "projection": projection})
    return sorted(rows.values(), key=lambda row: row["query_id"])


def _choose(method: str, rows: list[dict[str, Any]], station: str) -> dict[str, Any] | None:
    if not rows:
        return None
    if method == "earliest_source":
        return min(rows, key=lambda row: (row["available_at"], row["query_id"]))
    if method == "hash_source":
        return min(rows, key=lambda row: hashlib.sha256(f"{SEED}|{row['query_id']}".encode()).hexdigest())
    if method == "active_age":
        common = {station: {"entity": station, "baseline_probability": 0.5, "public_query_ids": [row["query_id"] for row in rows]}}
        return min(rows, key=lambda row: query_priority("public_risk_age.v1", seed=SEED, tick=0, acquired=0, target_id=station, query_id=row["query_id"], common=common, available_at=row["available_at"]))
    raise ValueError(f"unknown method: {method}")


def run(source_artifact: Path, outcome_artifact: Path, out: Path) -> dict[str, Any]:
    source = json.loads(source_artifact.read_text(encoding="utf-8"))
    outcomes = json.loads(outcome_artifact.read_text(encoding="utf-8"))
    if source.get("outcomes_accessed") is not False or source.get("model_calls") != 0:
        raise ValueError("source input must remain source-only")
    if outcomes.get("actor_received_outcomes") is not False or outcomes.get("unbound_count") != 0:
        raise ValueError("outcome input is not a complete evaluator-only dev binding")
    y_by_episode = {row["episode_id"]: int(row["outcome_y"]) for row in outcomes["rows"]}
    rows: list[dict[str, Any]] = []
    for episode in source["episodes"]:
        episode_id, station = episode["episode_id"], episode["station"]
        y = y_by_episode[episode_id]
        for checkpoint in episode["checkpoints"]:
            available = _source_rows(checkpoint)
            for method in METHODS:
                chosen = _choose(method, available, station) if method != "fixed" else None
                probability = 0.5 if chosen is None else _projection_probability(chosen["projection"], episode["target_start"], episode["target_end"])
                rows.append({
                    "episode_id": episode_id,
                    "station": station,
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "as_of": checkpoint["as_of"],
                    "method": method,
                    "selected_query_id": None if chosen is None else chosen["query_id"],
                    "visible_source_count": len(available),
                    "probability": probability,
                    "outcome_y": y,
                    "brier": (probability - y) ** 2,
                    "query_count": 0 if chosen is None else 1,
                })
    summary: dict[str, dict[str, Any]] = {}
    for method in METHODS:
        vals = [row["brier"] for row in rows if row["method"] == method]
        summary[method] = {"cells": len(vals), "mean_brier": fmean(vals), "sum_brier": sum(vals), "query_count": sum(row["query_count"] for row in rows if row["method"] == method)}
    active = summary["active_age"]["mean_brier"]
    best_nonactive = min(summary[method]["mean_brier"] for method in METHODS if method != "active_age")
    artifact = {
        "schema": "disastertrace.v21.real_dev_deterministic_score.v1",
        "evidence_role": "BOUNDED_REAL_DEV_EVALUATOR_DIAGNOSTIC",
        "synthetic": False,
        "empirical": True,
        "source_artifact_schema": source.get("schema"),
        "outcome_artifact_schema": outcomes.get("schema"),
        "methods": list(METHODS),
        "checkpoint_count": len(source["episodes"]) * len(source["episodes"][0]["checkpoints"]),
        "rows": rows,
        "summary": summary,
        "active_minus_fixed": active - summary["fixed"]["mean_brier"],
        "active_minus_best_nonactive": active - best_nonactive,
        "outcomes_accessed_by_actor": False,
        "model_calls": 0,
        "provider_calls": 0,
        "holdout_read": False,
        "quarantine_read": False,
        "interpretation": "A deterministic source-only development diagnostic using ASOS labels; it does not test an LLM provider, and source-selector superiority is not a novelty claim.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--outcome-artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run(args.source_artifact, args.outcome_artifact, args.out)
    print(json.dumps({"status": "PASS", "rows": len(artifact["rows"]), "active_minus_fixed": artifact["active_minus_fixed"], "active_minus_best_nonactive": artifact["active_minus_best_nonactive"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
