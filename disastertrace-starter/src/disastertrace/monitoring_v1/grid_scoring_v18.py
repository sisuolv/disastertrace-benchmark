"""Complete-grid scoring adapter for the v18 current-v13 port.

This adapter keeps the established :func:`scoring.brier_report` definition
and adds a fixed registration denominator plus submission-quality accounting.
It never deletes an opportunity because a model did not submit a valid value.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping

from .scoring import brier_report


_VALID_STATUSES = {"valid", "invalid", "late", "not_dispatched", "stop", "missing"}


def _prob(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Probability must be finite")
    if not 0 <= value <= 1:
        raise ValueError("Probability must be in [0, 1]")
    return float(value)


def _weight(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Checkpoint weight must be finite")
    if value < 0:
        raise ValueError("Checkpoint weight must be nonnegative")
    return float(value)


def _key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    required = ("target_id", "method", "checkpoint_id")
    if any(not row.get(name) for name in required):
        raise ValueError("Grid rows need target_id, method and checkpoint_id")
    return tuple(str(row[name]) for name in required)


def materialize_grid(
    registrations: Iterable[Mapping[str, Any]],
    submissions: Iterable[Mapping[str, Any]],
    *,
    carry_forward: bool = True,
    expected_methods: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Materialize every registered cell and preserve invalid/missing status.

    Registration rows must contain ``base`` and ``fallback`` probabilities.
    ``outcome`` may be ``None`` while an outcome is pending.  A prior valid
    probability may be carried forward, but the cell still records that its
    current submission was missing or invalid.
    """

    regs = [dict(row) for row in registrations]
    if not regs:
        raise ValueError("A registered grid is required")
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_target_method: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    expected_method_set = None if expected_methods is None else {
        str(method) for method in expected_methods
    }
    if expected_method_set is not None and not expected_method_set:
        raise ValueError("expected_methods must not be empty")
    fallback_by_checkpoint: dict[tuple[str, str, int], float] = {}
    contract_hash_by_target: dict[str, str] = {}
    for row in regs:
        key = _key(row)
        if key in by_key:
            raise ValueError(f"Duplicate registered grid cell: {key}")
        row["base"] = _prob(row["base"])
        row["fallback"] = _prob(row["fallback"])
        row["checkpoint_weight"] = _weight(row.get("checkpoint_weight", 1.0))
        if (
            "checkpoint_index" not in row
            or isinstance(row["checkpoint_index"], bool)
            or not isinstance(row["checkpoint_index"], int)
            or row["checkpoint_index"] < 0
        ):
            raise ValueError("Every grid cell needs an integer checkpoint_index")
        row.setdefault("outcome", None)
        if row["outcome"] is not None and (
            type(row["outcome"]) is not int or row["outcome"] not in (0, 1)
        ):
            raise ValueError("Outcome must be None, 0 or 1")
        row["registered"] = True
        row.setdefault("opportunity_id", "|".join(key))
        if "event_contract_hash" in row:
            contract_hash = row["event_contract_hash"]
            if not isinstance(contract_hash, str) or len(contract_hash) != 64:
                raise ValueError("event contract hash must be a 64-character string")
            target_id = str(row["target_id"])
            previous_hash = contract_hash_by_target.setdefault(target_id, contract_hash)
            if previous_hash != contract_hash:
                raise ValueError("event contract hash differs within one target")
        fallback_key = (str(row["target_id"]), str(row["checkpoint_id"]), int(row["checkpoint_index"]))
        prior_fallback = fallback_by_checkpoint.setdefault(fallback_key, row["fallback"])
        if prior_fallback != row["fallback"]:
            raise ValueError("frozen fallback must be identical across arms")
        by_key[key] = row
        by_target_method[(key[0], key[1])].append(row)
    for rows in by_target_method.values():
        rows.sort(key=lambda item: item["checkpoint_index"])
        if len({item["checkpoint_index"] for item in rows}) != len(rows):
            raise ValueError("Checkpoint indices must be unique within a target/method trajectory")
        weight_total = sum(item["checkpoint_weight"] for item in rows)
        if weight_total <= 0:
            raise ValueError("Checkpoint weights must have a positive trajectory total")
        for item in rows:
            item["score_weight"] = item["checkpoint_weight"] / weight_total

    current: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in submissions:
        row = dict(raw)
        key = _key(row)
        if key not in by_key:
            raise ValueError(f"Submission is not registered: {key}")
        if key in current:
            raise ValueError(f"Duplicate submission: {key}")
        status = str(row.get("status", "valid"))
        if status not in _VALID_STATUSES:
            raise ValueError(f"Unknown submission status: {status}")
        if status == "valid":
            try:
                row["probability"] = _prob(row["probability"])
            except (KeyError, TypeError, ValueError):
                status = "invalid"
                row.pop("probability", None)
        # A valid payload that was only available after this checkpoint is a
        # late update.  It must never backfill an earlier cutoff.
        registration = by_key[key]
        if status == "valid" and row.get("available_at") is not None and registration.get("cutoff") is not None:
            if row["available_at"] > registration["cutoff"]:
                status = "late"
                row.pop("probability", None)
        row["status"] = status
        current[key] = row

    out: list[dict[str, Any]] = []
    last_valid: dict[tuple[str, str], float] = {}
    # Materialization follows the declared temporal trajectory, never caller
    # insertion order.  This keeps carry-forward deterministic for a replayed
    # roster that was serialized or concatenated in a different order.
    ordered_regs = sorted(
        regs,
        key=lambda item: (str(item["target_id"]), str(item["method"]), item["checkpoint_index"], str(item["checkpoint_id"])),
    )
    for row in ordered_regs:
        key = _key(row)
        submission = current.get(key)
        status = "missing" if submission is None else str(submission["status"])
        submitted_probability = None if submission is None else submission.get("probability")
        source = "fallback"
        prediction = row["fallback"]
        if status == "valid":
            prediction = submitted_probability
            source = "submission"
            last_valid[(key[0], key[1])] = prediction
        elif carry_forward and (key[0], key[1]) in last_valid:
            prediction = last_valid[(key[0], key[1])]
            source = "carry_forward"
        scored_status = status if status in {"valid", "invalid", "late", "not_dispatched", "stop"} else "missing"
        materialized = dict(row)
        materialized.update(
            {
                "prediction": prediction,
                "submission_status": status,
                "scoring_status": scored_status if source == "submission" else f"{scored_status}_{source}",
                "submission_valid": status == "valid",
                "prediction_source": source,
            }
        )
        out.append(materialized)
    return out


def score_complete_grid(
    registrations: Iterable[Mapping[str, Any]],
    submissions: Iterable[Mapping[str, Any]],
    *,
    carry_forward: bool = True,
    expected_methods: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Score the complete registered grid and report process failures separately."""

    rows = materialize_grid(
        registrations,
        submissions,
        carry_forward=carry_forward,
        expected_methods=expected_methods,
    )
    score_rows = []
    for row in rows:
        score = dict(row)
        score_rows.append(score)
    report = brier_report(score_rows)
    statuses = defaultdict(int)
    for row in rows:
        statuses[row["submission_status"]] += 1
    # A method comparison is meaningful only on a complete common roster.
    # Preserve every supplied row for process accounting, but explicitly gate
    # comparative claims when a target/method cell is absent or its weights
    # differ from the other methods.
    target_methods: defaultdict[str, defaultdict[str, set[tuple[int, str]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    target_weights: defaultdict[str, dict[str, dict[int, float]]] = defaultdict(dict)
    for row in rows:
        target = str(row["target_id"])
        method = str(row["method"])
        target_methods[target][method].add((int(row["checkpoint_index"]), str(row["checkpoint_id"])))
        target_weights[target].setdefault(method, {})[int(row["checkpoint_index"])] = float(row["score_weight"])
    comparison_eligible = True
    comparison_exclusion_reason = None
    expected_method_set = None if expected_methods is None else {
        str(method) for method in expected_methods
    }
    if expected_method_set is not None:
        observed_methods = {str(row["method"]) for row in rows}
        if not expected_method_set.issubset(observed_methods):
            comparison_eligible = False
            comparison_exclusion_reason = "missing_expected_arm"
        for target, methods in target_methods.items():
            if set(methods) != expected_method_set:
                comparison_eligible = False
                comparison_exclusion_reason = comparison_exclusion_reason or "missing_expected_arm"
    for methods in target_methods.values():
        rosters = list(methods.values())
        if rosters and any(roster != rosters[0] for roster in rosters[1:]):
            comparison_eligible = False
    for methods in target_weights.values():
        weights = list(methods.values())
        if weights and any(roster != weights[0] for roster in weights[1:]):
            comparison_eligible = False
    return {
        # v3 (Batch V4): a conflicting target's rows are now excluded from every
        # qualified/primary field instead of merely being flagged while still
        # contributing to them; see legacy_all_rows_including_conflicts in the
        # nested report and OPUS_REVIEW_OF_SONNET.md for the full account.
        "schema": "disastertrace.v18.complete_grid_score.v3",
        "registered": len(rows),
        "scored": len(rows),
        "submission_status_counts": dict(sorted(statuses.items())),
        "valid_submissions": sum(row["submission_valid"] for row in rows),
        "carry_forward": sum(row["prediction_source"] == "carry_forward" for row in rows),
        "fallback": sum(row["prediction_source"] == "fallback" for row in rows),
        "comparison_eligible": comparison_eligible,
        "comparison_exclusion_reason": comparison_exclusion_reason,
        "report": report,
        "rows": rows,
    }
