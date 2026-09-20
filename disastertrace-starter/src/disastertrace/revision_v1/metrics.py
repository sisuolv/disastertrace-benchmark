"""Fixed grid trajectory scorer for DisasterTrace v14 (P0-04).

Implements metrics from plan section 9:
- Q: Trajectory score = (1/N) * sum_j sum_k w_jk * L(p_eff(j, t_k), Y_j)
- Delta: Q(baseline) - Q(agent) (relative to dynamic baseline)
- RV_jk: L(p_{k-1}) - L(p_k) (telescoping property verified)
- Fact layer: amendment compliance rate, invalid reference duration, KEEP_UNKNOWN correctness
- O: Conditional overreaction on lossless_duplicate/mirror/no_change_reissue only
- Timeliness: amendment available_at to first compliant commit, right-censored
- Calibration: by lead-time/process, reusing brier_report

Reuses:
- brier_report from monitoring_v1/scoring.py (single-point Brier scoring)
- generic_missing_gain_bounds from monitoring_v1/scoring.py (missing outcome bounds)
- effective state resolution concept from revision_v1/belief_commit.py (HOLD carry-forward)
- ledger kind classification from revision_v1/ledger.py (overreaction scoping)
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from ..monitoring_v1.scoring import brier_report, generic_missing_gain_bounds


# ---------------------------------------------------------------------------
# Probability validation (matching monitoring_v1/scoring.py)
# ---------------------------------------------------------------------------


def _validate_prob(value: float) -> float:
    """Validate probability is finite and in [0, 1]."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError(f"Invalid probability: {value}")
    return float(value)


def _validate_binary_outcome(y: int) -> int:
    """Validate outcome is int 0 or 1 (not bool)."""
    if type(y) is not int or y not in (0, 1):
        raise ValueError(f"Outcome must be int 0 or 1, got {type(y).__name__}: {y}")
    return y


def _brier_loss(p: float, y: int) -> float:
    """Compute Brier loss L(p, y) = (p - y)^2."""
    return (p - y) ** 2


# ---------------------------------------------------------------------------
# Effective probability at time t (HOLD carry-forward semantics)
# ---------------------------------------------------------------------------


def effective_at_from_commits(
    target_id: str,
    commits: list[dict],
    at: int | float,
    fallback: float,
) -> float:
    """Get the effective probability at time `at` for target `target_id`.

    Implements HOLD carry-forward: the last commit with effective_at <= at
    is the effective value. If no commit is effective yet, use fallback.

    This follows the same semantics as FutureSim's get_prediction_as_of
    and METRIC_REFERENCE.py's effective_at function.

    Args:
        target_id: The target identifier.
        commits: List of commit dicts with target_id, effective_at, probability.
        at: The time to evaluate at.
        fallback: The fallback probability before any commit.

    Returns:
        The effective probability at time `at`.
    """
    _validate_prob(fallback)

    # Filter commits for this target
    target_commits = [c for c in commits if c.get("target_id") == target_id]

    # Sort by effective_at
    target_commits = sorted(target_commits, key=lambda c: c["effective_at"])

    # Find the last commit with effective_at <= at
    value = fallback
    for commit in target_commits:
        prob = commit["probability"]
        _validate_prob(prob)
        if commit["effective_at"] <= at:
            value = prob
        else:
            break

    return value


# ---------------------------------------------------------------------------
# Q: Trajectory score
# ---------------------------------------------------------------------------


def trajectory_score_Q(
    commits: list[dict],
    grid: dict[str, list[tuple[int | float, float]]],
    outcomes: dict[str, int],
    fallback: dict[str, float],
) -> float:
    """Compute trajectory score Q = (1/N) * sum_j sum_k w_jk * L(p_eff(j, t_k), Y_j).

    Args:
        commits: List of commit dicts with {target_id, effective_at, probability}.
        grid: Dict mapping target_id -> [(time, weight), ...]. Weights must sum to 1.
        outcomes: Dict mapping target_id -> Y (binary outcome, int 0 or 1).
        fallback: Dict mapping target_id -> fallback probability before any commit.

    Returns:
        The trajectory score Q.

    Raises:
        ValueError: If weights don't sum to 1, negative weights, or invalid probs.
    """
    if not grid:
        raise ValueError("Grid cannot be empty")

    N = len(grid)  # Number of targets
    total_loss = 0.0

    for target_id, checkpoints in grid.items():
        if not checkpoints:
            raise ValueError(f"Target {target_id} has empty checkpoint list")

        # Extract weights and validate
        times = [t for t, _ in checkpoints]
        weights = [w for _, w in checkpoints]

        if any(w < 0 for w in weights):
            raise ValueError(f"Target {target_id} has negative weight")

        if not math.isclose(sum(weights), 1.0, rel_tol=1e-9):
            raise ValueError(
                f"Target {target_id} weights must sum to one, got {sum(weights)}"
            )

        # Get outcome
        if target_id not in outcomes:
            raise ValueError(f"Missing outcome for target {target_id}")

        y = _validate_binary_outcome(outcomes[target_id])

        # Get fallback
        if target_id not in fallback:
            raise ValueError(f"Missing fallback for target {target_id}")

        fb = fallback[target_id]

        # Compute weighted loss over checkpoints
        target_loss = 0.0
        for t, w in checkpoints:
            p_eff = effective_at_from_commits(target_id, commits, t, fb)
            loss = _brier_loss(p_eff, y)
            target_loss += w * loss

        total_loss += target_loss

    return total_loss / N


# ---------------------------------------------------------------------------
# Delta: relative to baseline
# ---------------------------------------------------------------------------


def compute_delta(q_baseline: float, q_agent: float) -> float:
    """Compute Delta = Q(baseline) - Q(agent).

    Positive delta means agent is better (lower Q) than baseline.

    Args:
        q_baseline: The baseline's trajectory score Q.
        q_agent: The agent's trajectory score Q.

    Returns:
        Delta value.
    """
    return q_baseline - q_agent


# ---------------------------------------------------------------------------
# RV_jk: Revision Value with telescoping property
# ---------------------------------------------------------------------------


def compute_rv_sequence(probs: list[float], y: int) -> list[float]:
    """Compute RV sequence: RV_k = L(p_{k-1}) - L(p_k) for k in 1..n-1.

    The telescoping property guarantees: sum(RV) = L(p_0) - L(p_{n-1}).

    Args:
        probs: Sequence of probabilities [p_0, p_1, ..., p_{n-1}].
        y: Binary outcome (int 0 or 1).

    Returns:
        List of RV values [RV_1, ..., RV_{n-1}]. Length is len(probs) - 1.
    """
    y = _validate_binary_outcome(y)

    if len(probs) < 2:
        return []

    rv_values = []
    for i in range(len(probs) - 1):
        p_prev = _validate_prob(probs[i])
        p_curr = _validate_prob(probs[i + 1])
        L_prev = _brier_loss(p_prev, y)
        L_curr = _brier_loss(p_curr, y)
        rv_values.append(L_prev - L_curr)

    return rv_values


def verify_rv_telescoping(probs: list[float], y: int, rv_values: list[float]) -> bool:
    """Verify the telescoping property: sum(RV) == L(p_0) - L(p_{n-1}).

    This is an explicit verification for the acceptance criteria.

    Args:
        probs: Sequence of probabilities.
        y: Binary outcome.
        rv_values: The computed RV sequence.

    Returns:
        True if telescoping property holds.
    """
    if len(probs) < 2:
        return True  # Empty RV sequence trivially satisfies

    L_first = _brier_loss(probs[0], y)
    L_last = _brier_loss(probs[-1], y)
    expected = L_first - L_last

    return math.isclose(sum(rv_values), expected, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Fact layer metrics
# ---------------------------------------------------------------------------


def compute_amendment_compliance_rate(amendments: list[dict]) -> float | None:
    """Compute amendment compliance rate.

    Rate = fraction of amendments that were properly adopted by the agent.

    Args:
        amendments: List of amendment dicts with {source_id, properly_adopted: bool}.

    Returns:
        Compliance rate in [0, 1], or None if no amendments.
    """
    if not amendments:
        return None

    adopted = sum(1 for a in amendments if a.get("properly_adopted", False))
    return adopted / len(amendments)


def compute_invalid_reference_duration(references: list[dict]) -> int:
    """Compute total invalid reference duration.

    Duration = sum of time each commit referenced superseded evidence.

    Args:
        references: List of dicts with {evidence_id, superseded_at, corrected_at}.

    Returns:
        Total duration (same units as input times).
    """
    total = 0
    for ref in references:
        superseded_at = ref.get("superseded_at")
        corrected_at = ref.get("corrected_at")
        if superseded_at is not None and corrected_at is not None:
            duration = corrected_at - superseded_at
            if duration > 0:
                total += duration
    return total


def compute_keep_unknown_correctness_rate(operations: list[dict]) -> float | None:
    """Compute KEEP_UNKNOWN correctness rate.

    Rate = fraction of KEEP_UNKNOWN operations that were correct
    (the value was truly unknown at the time).

    Args:
        operations: List of operation dicts with {operation, was_correct: bool}.

    Returns:
        Correctness rate in [0, 1], or None if no KEEP_UNKNOWN operations.
    """
    keep_unknown_ops = [op for op in operations if op.get("operation") == "KEEP_UNKNOWN"]

    if not keep_unknown_ops:
        return None

    correct = sum(1 for op in keep_unknown_ops if op.get("was_correct", False))
    return correct / len(keep_unknown_ops)


# ---------------------------------------------------------------------------
# Conditional Overreaction O
# ---------------------------------------------------------------------------


# The three kinds that qualify for overreaction measurement
INFORMATION_FREE_KINDS = frozenset({"lossless_duplicate", "mirror", "no_change_reissue"})


def compute_conditional_overreaction(packages: list[dict]) -> float | None:
    """Compute conditional overreaction O = E|p' - p| on information-free evidence.

    This is computed ONLY over ledger-labeled lossless_duplicate/mirror/no_change_reissue
    packages. These represent evidence that carries no new information.

    The ideal agent should have O = 0 (no belief change on info-free evidence).

    Args:
        packages: List of package dicts with {kind, p_before, p_after}.

    Returns:
        Mean absolute belief change, or None if no qualifying packages.
    """
    # Filter to information-free kinds only
    qualifying = [p for p in packages if p.get("kind") in INFORMATION_FREE_KINDS]

    if not qualifying:
        return None

    total_drift = 0.0
    for pkg in qualifying:
        p_before = _validate_prob(pkg["p_before"])
        p_after = _validate_prob(pkg["p_after"])
        total_drift += abs(p_after - p_before)

    return total_drift / len(qualifying)


def overreaction_vs_noise_floor(O_agent: float, noise_floor: float) -> dict:
    """Compare agent overreaction against resampling noise floor.

    Args:
        O_agent: The agent's overreaction value.
        noise_floor: The expected overreaction from repeated sampling noise.

    Returns:
        Comparison dict with O_agent, noise_floor, and whether agent exceeds noise.
    """
    return {
        "O_agent": O_agent,
        "noise_floor": noise_floor,
        "exceeds_noise": O_agent > noise_floor,
        "ratio": O_agent / noise_floor if noise_floor > 0 else None,
    }


# ---------------------------------------------------------------------------
# Timeliness with right-censoring
# ---------------------------------------------------------------------------


def compute_timeliness(amendments: list[dict]) -> dict:
    """Compute timeliness metrics with right-censoring.

    Timeliness = interval from amendment available_at to first compliant commit.
    Amendments not yet responded to are right-censored (not dropped).

    Args:
        amendments: List of dicts with {source_id, available_at, first_compliant_commit_at}.
                   first_compliant_commit_at is None for right-censored (not responded).

    Returns:
        Dict with mean_response_time, compliant_count, right_censored_count.
    """
    compliant_times = []
    censored_count = 0

    for amd in amendments:
        available_at = amd.get("available_at")
        responded_at = amd.get("first_compliant_commit_at")

        if responded_at is not None:
            response_time = responded_at - available_at
            compliant_times.append(response_time)
        else:
            censored_count += 1

    return {
        "mean_response_time": (
            sum(compliant_times) / len(compliant_times) if compliant_times else None
        ),
        "compliant_count": len(compliant_times),
        "right_censored_count": censored_count,
    }


# ---------------------------------------------------------------------------
# Calibration by strata (reusing brier_report)
# ---------------------------------------------------------------------------


def calibration_by_strata(
    rows: list[dict],
    stratum_key: str | None = None,
) -> dict:
    """Compute calibration metrics stratified by a key.

    Reuses brier_report from monitoring_v1/scoring.py for the core computation.

    Args:
        rows: List of row dicts for brier_report (opportunity_id, base, prediction, outcome).
        stratum_key: Optional key to stratify by (e.g., "lead_time", "process").
                    If None, computes overall calibration.

    Returns:
        Dict mapping stratum values -> brier_report results.
    """
    if stratum_key is None:
        # Overall calibration
        return {"all": brier_report(rows)}

    # Group by stratum
    groups: dict[Any, list[dict]] = defaultdict(list)
    for row in rows:
        key = row.get(stratum_key, "unspecified")
        groups[key].append(row)

    # Compute brier_report for each group
    result = {}
    for stratum_value, group_rows in groups.items():
        result[stratum_value] = brier_report(group_rows)

    return result


def compute_missing_outcome_bounds(
    settlement_fraction: float,
    settled_mean_gain: float,
) -> tuple[float, float]:
    """Compute missing outcome bounds, reusing generic_missing_gain_bounds.

    This is a thin wrapper to ensure we reuse the existing implementation.

    Args:
        settlement_fraction: Fraction of outcomes that have settled.
        settled_mean_gain: Mean gain on settled outcomes.

    Returns:
        (lower_bound, upper_bound) tuple.
    """
    return generic_missing_gain_bounds(settlement_fraction, settled_mean_gain)
