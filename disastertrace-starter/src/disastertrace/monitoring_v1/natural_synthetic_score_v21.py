"""Synthetic Natural scoring and denominator probe for v21."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from .grid_scoring_v18 import score_complete_grid
from .synthetic_natural_v21 import METHODS, run_method_case


CHECKPOINTS = ("T-60", "T-40", "T-20")


def _registration(case_id: str, outcome: int | None) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        for index, checkpoint_id in enumerate(CHECKPOINTS):
            rows.append(
                {
                    "target_id": case_id,
                    "method": method,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_index": index,
                    "base": 0.5,
                    "fallback": 0.5,
                    "outcome": outcome,
                    "checkpoint_weight": 1.0,
                    "baseline_kind": "synthetic_baseline",
                }
            )
    return rows


def _submissions(case: dict[str, Any]) -> list[dict[str, Any]]:
    case_id = str(case["case_id"])
    rows = []
    # Active deliberately omits T-20: the scorer must retain the opportunity
    # and carry forward the last valid prediction.
    for method in METHODS:
        probability = float(case["method_probabilities"][method])
        checkpoints = CHECKPOINTS[:2] if method == "active" else CHECKPOINTS
        for index, checkpoint_id in enumerate(checkpoints):
            # Fixed has one malformed cell. It is a process failure and uses
            # the prior valid probability for scoring, while remaining in the
            # denominator.
            invalid = method == "fixed" and checkpoint_id == "T-40"
            row = {
                "target_id": case_id,
                "method": method,
                "checkpoint_id": checkpoint_id,
                "checkpoint_index": index,
                "status": "invalid" if invalid else "valid",
            }
            if not invalid:
                row["probability"] = probability
            rows.append(row)
    return rows


def _method_losses(rows: list[dict[str, Any]]) -> dict[str, float]:
    losses: dict[str, list[float]] = {}
    for row in rows:
        if row["outcome"] is None:
            continue
        losses.setdefault(str(row["method"]), []).append((row["prediction"] - row["outcome"]) ** 2)
    return {method: mean(values) for method, values in sorted(losses.items())}


def run_score(out: Path | None = None) -> dict[str, Any]:
    cases = []
    for case_id, signal, outcome in (
        ("signal_low", 4000.0, 1),
        ("signal_high", 9000.0, 0),
        # A deliberately adversarial fixture checks that active value is
        # conditional on source informativeness rather than guaranteed.
        ("signal_mismatch", 4000.0, 0),
    ):
        method_cases = {
            method: run_method_case(case_id, signal, method=method, outcome=outcome)
            for method in METHODS
        }
        active = method_cases["active"]
        active["method_probabilities"] = {
            method: float(result["probability"]) for method, result in method_cases.items()
        }
        active["method_cases"] = method_cases
        cases.append(active)
    settled: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    per_case = []
    for case in cases:
        regs = _registration(case["case_id"], case["evaluator_y"])
        subs = _submissions(case)
        report = score_complete_grid(regs, subs)
        per_case.append(
            {
                "case_id": case["case_id"],
                "method_losses": _method_losses(report["rows"]),
                "submission_status_counts": report["submission_status_counts"],
                "carry_forward": report["carry_forward"],
                "active_carry_forward": sum(
                    row["prediction_source"] == "carry_forward" and row["method"] == "active"
                    for row in report["rows"]
                ),
                "fixed_carry_forward": sum(
                    row["prediction_source"] == "carry_forward" and row["method"] == "fixed"
                    for row in report["rows"]
                ),
                "comparison_eligible": report["comparison_eligible"],
            }
        )
        settled.extend(regs)
        missing.extend(_registration(case["case_id"], None))
    # The missing-Y run uses the same predictions and roster but no outcomes.
    missing_submissions = []
    for case in cases:
        missing_submissions.extend(_submissions(case))
    missing_report = score_complete_grid(missing, missing_submissions)
    method_losses = {
        method: [row["method_losses"][method] for row in per_case]
        for method in METHODS
    }
    artifact = {
        "schema": "disastertrace.v21.natural_synthetic_score.v2",
        "evidence_role": "SYNTHETIC_PROTOCOL_CHECK",
        "synthetic": True,
        "empirical": False,
        "cases": per_case,
        "settled": {
            "methods": list(METHODS),
            "mean_loss_by_method": {method: mean(values) for method, values in method_losses.items()},
            "active_mean_loss": mean(method_losses["active"]),
            "fixed_mean_loss": mean(method_losses["fixed"]),
            "active_minus_fixed": mean(method_losses["active"]) - mean(method_losses["fixed"]),
            "active_minus_best_non_active": mean(method_losses["active"]) - min(
                mean(values) for method, values in method_losses.items() if method != "active"
            ),
            "comparison_eligible": all(item["comparison_eligible"] for item in per_case),
        },
        "failure_denominator": {
            "registered": sum(sum(item["submission_status_counts"].values()) for item in per_case),
            "active_carry_forward_cells": sum(item["active_carry_forward"] for item in per_case),
            "fixed_carry_forward_cells": sum(item["fixed_carry_forward"] for item in per_case),
            "fixed_invalid_cells": 3,
            "methods": list(METHODS),
        },
        "missing_y_probe": {
            "opportunities": missing_report["report"]["opportunities"],
            "missing": missing_report["report"]["missing"],
            "lower": missing_report["report"]["full_population_gain_bounds"][0],
            "upper": missing_report["report"]["full_population_gain_bounds"][1],
            "missing_target_groups": missing_report["report"]["missing_target_groups"],
        },
        "interpretation": "All methods share the same synthetic evidence stream and F; active value is conditional on the signal, and the mismatch case is retained as harm evidence.",
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact
