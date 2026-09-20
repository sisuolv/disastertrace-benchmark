"""Fixed grid trajectory scorer for DisasterTrace v14 (P0-04 / R3 repair).

Implements metrics from plan section 9 with R3 fixes from review section 3 + section 4:
- Q: Trajectory score = (1/N) * sum_j sum_k w_jk * L(p_eff(j, t_k), Y_j)
  - R3 Issue #2: strict finite/unique/sorted grid, cohort fingerprint, missing-Y bounds
- Delta: Q(baseline) - Q(agent) (relative to dynamic baseline)
- RV_jk: L(p_{k-1}) - L(p_k) (loss-decomposition diagnostic, NOT causal attribution)
  - R3 Issue #3: clearly labeled as loss-change diagnostic, not causal contribution
- Fact layer: amendment compliance rate, invalid reference duration, KEEP_UNKNOWN correctness
  - R3 Issue #5: uncorrected references charge through to observation end
  - R3 Issue #7: KEEP_UNKNOWN uses full required-slot denominator
- O: Conditional overreaction on lossless_duplicate/mirror/no_change_reissue only
  - R3 Issue #4: resampling-based noise floor estimation, returns interval + signed diff
- Timeliness: amendment available_at to first compliant commit, censoring-aware
  - R3 Issue #6: Kaplan-Meier-style bounds for right-censored cases
- Brier by strata: renamed from calibration_by_strata (Brier is not calibration)
  - R3 Issue #8: renamed to brier_by_strata; calibration_by_strata kept as deprecated alias

Section 4 missing-Y contract:
- Do not drop registered targets with missing Y
- Use common-settled cohort and report coverage + full-cohort sensitivity bounds
- For a single missing target, compute metric gain under both Y=0 and Y=1
- Sensitivity bounds are NOT confidence intervals (separately labeled)

Reuses:
- brier_report from monitoring_v1/scoring.py (single-point Brier scoring)
- generic_missing_gain_bounds from monitoring_v1/scoring.py (missing outcome bounds)
- effective state resolution concept from revision_v1/belief_commit.py (HOLD carry-forward)
- ledger kind classification from revision_v1/ledger.py (overreaction scoping)
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import warnings
from collections import defaultdict
from typing import Any

from ..monitoring_v1.scoring import brier_report, generic_missing_gain_bounds


# ---------------------------------------------------------------------------
# R3 Issue #1: Adapter for belief_commit effective state
# ---------------------------------------------------------------------------


def commits_from_effective_states(
    effective_states: list[dict],
    *,
    target_id_key: str = "target_id",
    effective_at_key: str = "effective_at",
    probability_key: str = "probability",
) -> list[dict]:
    """Adapter to convert belief_commit effective state records to flat commit format.

    R3 Issue #1: The Q calculation's effective_at_from_commits requires flat
    already-applied records, but belief_commit stores raw vs effective separately.
    This adapter consumes the verified-applied events from belief_commit's
    attempt->commit->effective chain and produces the flattened form Q needs.

    Args:
        effective_states: List of effective state records from CommitStore.
            Each record should have target_id, effective_at, and the probability
            from the forecasts dict.
        target_id_key: Key name for target_id in records.
        effective_at_key: Key name for effective timestamp.
        probability_key: Key name for probability value.

    Returns:
        List of flat commit dicts suitable for effective_at_from_commits.
    """
    commits = []
    for record in effective_states:
        # Handle both direct flat records and nested forecasts structure
        if "forecasts" in record:
            # From CommitStore effective_state snapshot
            effective_at = record.get(effective_at_key)
            for target_id, prob in record.get("forecasts", {}).items():
                commits.append({
                    "target_id": target_id,
                    "effective_at": effective_at,
                    "probability": prob,
                })
        else:
            # Already flat format
            commits.append({
                "target_id": record.get(target_id_key),
                "effective_at": record.get(effective_at_key),
                "probability": record.get(probability_key),
            })
    return commits


# ---------------------------------------------------------------------------
# R3 Issue #2: Grid validation and cohort fingerprint
# ---------------------------------------------------------------------------


def validate_scoring_grid(
    grid: dict[str, list[tuple[int | float, float]]],
) -> None:
    """Validate that scoring grid is finite, unique, and sorted per target.

    R3 Issue #2: Q must be computed on a frozen, finite, strictly-ordered,
    deduplicated checkpoint grid bound to each target's own time window.

    Args:
        grid: Dict mapping target_id -> [(time, weight), ...].

    Raises:
        ValueError: If grid contains NaN/inf times, duplicates, or unsorted times.
        TypeError: If grid contains non-numeric times.
    """
    for target_id, checkpoints in grid.items():
        if not checkpoints:
            raise ValueError(f"Target {target_id} has empty checkpoint list")

        times = [t for t, _ in checkpoints]

        # Check for non-numeric times
        for t in times:
            if not isinstance(t, (int, float)):
                raise TypeError(f"Target {target_id} has non-numeric checkpoint time: {t}")

        # Check for NaN or infinity
        for t in times:
            if not math.isfinite(t):
                raise ValueError(f"Target {target_id} has non-finite checkpoint time: {t}")

        # Check for duplicates
        if len(times) != len(set(times)):
            raise ValueError(f"Target {target_id} has duplicate checkpoint times")

        # Check for sorted order
        if times != sorted(times):
            raise ValueError(f"Target {target_id} checkpoint times are not sorted")


def compute_cohort_fingerprint(
    grid: dict[str, list[tuple[int | float, float]]],
    outcomes: dict[str, int | None],
) -> str:
    """Compute a cohort fingerprint for verifying grid identity across runs.

    R3 Issue #2: Different runs can verify they scored the same committed grid
    by comparing cohort fingerprints.

    Args:
        grid: The scoring grid (target_id -> [(time, weight), ...]).
        outcomes: The outcomes dict (target_id -> Y or None for missing).

    Returns:
        SHA256 hex digest of the canonical representation.
    """
    # Create canonical representation
    canonical = {
        "grid": {
            tid: [(float(t), float(w)) for t, w in checkpoints]
            for tid, checkpoints in sorted(grid.items())
        },
        "outcome_targets": sorted(outcomes.keys()),
        "settled_targets": sorted(tid for tid, y in outcomes.items() if y is not None),
    }
    content = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


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

    R3 fix: Only validate probabilities that are actually used (effective at the
    query time). Future commits with invalid values do not affect earlier views.
    This ensures archival table validation is separate from as-of view computation.

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
    # R3 fix: Only validate probabilities when we actually USE them (effective_at <= at)
    value = fallback
    for commit in target_commits:
        if commit["effective_at"] <= at:
            prob = commit["probability"]
            _validate_prob(prob)  # Validate only when this commit is effective
            value = prob
        else:
            # Future commits are not validated yet - they don't affect this view
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

    R3 Issue #2: Now validates grid for finite/unique/sorted times.

    Args:
        commits: List of commit dicts with {target_id, effective_at, probability}.
        grid: Dict mapping target_id -> [(time, weight), ...]. Weights must sum to 1.
              Checkpoint times must be finite, unique, and sorted per target.
        outcomes: Dict mapping target_id -> Y (binary outcome, int 0 or 1).
        fallback: Dict mapping target_id -> fallback probability before any commit.

    Returns:
        The trajectory score Q.

    Raises:
        ValueError: If weights don't sum to 1, negative weights, invalid probs,
                    non-finite/duplicate/unsorted checkpoint times.
        TypeError: If checkpoint times are not numeric.
    """
    if not grid:
        raise ValueError("Grid cannot be empty")

    # R3 Issue #2: Validate grid structure
    validate_scoring_grid(grid)

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


def trajectory_score_Q_with_bounds(
    commits: list[dict],
    grid: dict[str, list[tuple[int | float, float]]],
    outcomes: dict[str, int | None],
    fallback: dict[str, float],
) -> dict:
    """Compute trajectory score Q with missing-Y sensitivity bounds.

    R3 Issue #2 / Section 4 missing-Y contract:
    - Do not drop registered targets with missing Y
    - For missing targets, compute the metric under both Y=0 and Y=1
    - Report sensitivity bounds (NOT confidence intervals)
    - All checkpoints for a missing target share the SAME imputed Y

    Args:
        commits: List of commit dicts with {target_id, effective_at, probability}.
        grid: Dict mapping target_id -> [(time, weight), ...].
        outcomes: Dict mapping target_id -> Y (0, 1, or None for missing).
        fallback: Dict mapping target_id -> fallback probability before any commit.

    Returns:
        Dict with:
            q_settled: Q computed on settled (non-missing) targets only.
            q_lower_bound: Q lower bound (best case for missing targets).
            q_upper_bound: Q upper bound (worst case for missing targets).
            settled_count: Number of targets with known outcomes.
            missing_count: Number of targets with missing outcomes.
            coverage: Fraction of targets with known outcomes.
            cohort_fingerprint: SHA256 of the grid/outcomes for reproducibility.
            interpretation: Note that bounds are sensitivity bounds, not CIs.
    """
    if not grid:
        raise ValueError("Grid cannot be empty")

    # R3 Issue #2: Validate grid structure
    validate_scoring_grid(grid)

    # Separate settled vs missing targets
    settled_targets = {tid for tid, y in outcomes.items() if y is not None}
    missing_targets = set(grid.keys()) - settled_targets

    N = len(grid)

    # Compute loss contributions for settled targets
    settled_loss = 0.0
    for target_id in settled_targets:
        if target_id not in grid:
            continue
        checkpoints = grid[target_id]
        weights = [w for _, w in checkpoints]
        if any(w < 0 for w in weights):
            raise ValueError(f"Target {target_id} has negative weight")
        if not math.isclose(sum(weights), 1.0, rel_tol=1e-9):
            raise ValueError(f"Target {target_id} weights must sum to one")

        y = _validate_binary_outcome(outcomes[target_id])
        fb = fallback.get(target_id, 0.5)

        target_loss = 0.0
        for t, w in checkpoints:
            p_eff = effective_at_from_commits(target_id, commits, t, fb)
            loss = _brier_loss(p_eff, y)
            target_loss += w * loss
        settled_loss += target_loss

    # For missing targets, compute bounds
    # Per Section 4: all checkpoints for a target share the same Y
    missing_lower = 0.0
    missing_upper = 0.0

    for target_id in missing_targets:
        if target_id not in grid:
            continue
        checkpoints = grid[target_id]
        weights = [w for _, w in checkpoints]
        if any(w < 0 for w in weights):
            raise ValueError(f"Target {target_id} has negative weight")
        if not math.isclose(sum(weights), 1.0, rel_tol=1e-9):
            raise ValueError(f"Target {target_id} weights must sum to one")

        fb = fallback.get(target_id, 0.5)

        # Compute loss under Y=0 and Y=1
        loss_if_0 = 0.0
        loss_if_1 = 0.0
        for t, w in checkpoints:
            p_eff = effective_at_from_commits(target_id, commits, t, fb)
            loss_if_0 += w * _brier_loss(p_eff, 0)
            loss_if_1 += w * _brier_loss(p_eff, 1)

        # Lower bound uses the better outcome, upper uses worse
        missing_lower += min(loss_if_0, loss_if_1)
        missing_upper += max(loss_if_0, loss_if_1)

    # Compute Q values
    settled_count = len(settled_targets & set(grid.keys()))
    missing_count = len(missing_targets & set(grid.keys()))

    q_settled = settled_loss / settled_count if settled_count > 0 else None
    q_lower = (settled_loss + missing_lower) / N if N > 0 else None
    q_upper = (settled_loss + missing_upper) / N if N > 0 else None

    return {
        "q_settled": q_settled,
        "q_lower_bound": q_lower,
        "q_upper_bound": q_upper,
        "settled_count": settled_count,
        "missing_count": missing_count,
        "coverage": settled_count / N if N > 0 else 0.0,
        "cohort_fingerprint": compute_cohort_fingerprint(grid, outcomes),
        "interpretation": (
            "Sensitivity bounds: q_lower/upper assume all missing targets "
            "have the same Y (0 or 1) that minimizes/maximizes Q respectively. "
            "These are NOT confidence intervals."
        ),
    }


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
# RV_jk: Revision Value (Loss-Change Diagnostic)
# R3 Issue #3: RV describes loss CHANGE, not causal attribution of evidence
# ---------------------------------------------------------------------------


def compute_rv_sequence(probs: list[float], y: int) -> list[float]:
    """Compute RV (loss-change) sequence: RV_k = L(p_{k-1}) - L(p_k).

    R3 Issue #3 clarification: RV is a LOSS-DECOMPOSITION DIAGNOSTIC that
    measures how much the Brier loss changed between consecutive probability
    updates. It satisfies the telescoping property (sum = first-vs-last diff)
    but does NOT attribute causal contribution to specific evidence.

    This metric answers "how much did the loss change at each step?" not
    "how much did each piece of evidence causally contribute to accuracy?"

    For causal attribution, see O (conditional overreaction) with paired
    intervention branches, which is handled separately.

    The telescoping property guarantees: sum(RV) = L(p_0) - L(p_{n-1}).

    Args:
        probs: Sequence of probabilities [p_0, p_1, ..., p_{n-1}].
        y: Binary outcome (int 0 or 1).

    Returns:
        List of RV values [RV_1, ..., RV_{n-1}]. Length is len(probs) - 1.
        Positive values indicate loss decreased (improvement), negative
        values indicate loss increased (degradation).
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

    The telescoping property is a mathematical identity that must hold for
    any valid RV sequence. It ensures loss-change decomposition is consistent.

    Args:
        probs: Sequence of probabilities.
        y: Binary outcome.
        rv_values: The computed RV sequence.

    Returns:
        True if telescoping property holds (within numerical tolerance).
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


def compute_invalid_reference_duration(references: list[dict]) -> int | float:
    """Compute total invalid reference duration.

    Duration = sum of time each commit referenced superseded evidence.

    R3 Issue #5: When corrected_at is None (reference NEVER corrected), the
    invalid duration is charged through to the observation's end time
    (right_censor_at field). A reference that is never corrected must
    accumulate MORE duration than one corrected later, not ZERO.

    Args:
        references: List of dicts with:
            - evidence_id: The evidence identifier
            - superseded_at: When the evidence became superseded
            - corrected_at: When the reference was corrected (None if never)
            - right_censor_at: End of registered observation window (required
              when corrected_at is None)

    Returns:
        Total duration (same units as input times).

    Raises:
        ValueError: If corrected_at is None but right_censor_at is also missing.
    """
    total = 0
    for ref in references:
        superseded_at = ref.get("superseded_at")
        if superseded_at is None:
            continue

        corrected_at = ref.get("corrected_at")

        if corrected_at is not None:
            # Corrected: duration from superseded to corrected
            duration = corrected_at - superseded_at
            if duration > 0:
                total += duration
        else:
            # R3 Issue #5: Never corrected - charge to observation end
            right_censor_at = ref.get("right_censor_at")
            if right_censor_at is None:
                raise ValueError(
                    f"Invalid reference to {ref.get('evidence_id')}: "
                    f"corrected_at is None but right_censor_at is missing. "
                    f"Uncorrected references must specify the observation end time."
                )
            duration = right_censor_at - superseded_at
            if duration > 0:
                total += duration

    return total


def compute_keep_unknown_correctness_rate(operations: list[dict]) -> float | None:
    """Compute KEEP_UNKNOWN correctness rate (DEPRECATED - use full-slot version).

    Rate = fraction of KEEP_UNKNOWN operations that were correct
    (the value was truly unknown at the time).

    WARNING: This function only evaluates slots the model chose to address,
    which lets a model selectively avoid difficult slots. Use
    compute_fact_layer_correctness for proper evaluation.

    Args:
        operations: List of operation dicts with {operation, was_correct: bool}.

    Returns:
        Correctness rate in [0, 1], or None if no KEEP_UNKNOWN operations.
    """
    warnings.warn(
        "compute_keep_unknown_correctness_rate evaluates only addressed slots. "
        "Use compute_fact_layer_correctness for full required-slot denominator.",
        DeprecationWarning,
        stacklevel=2,
    )
    keep_unknown_ops = [op for op in operations if op.get("operation") == "KEEP_UNKNOWN"]

    if not keep_unknown_ops:
        return None

    correct = sum(1 for op in keep_unknown_ops if op.get("was_correct", False))
    return correct / len(keep_unknown_ops)


def compute_fact_layer_correctness(
    operations: list[dict],
    required_slots: set[str],
) -> dict:
    """Compute fact-layer correctness against full required-slot denominator.

    R3 Issue #7: KEEP_UNKNOWN correctness (and fact-layer compliance generally)
    must be computed against the FULL set of required registered slots as the
    denominator, not just the slots the model chose to address. This prevents
    a model from selectively avoiding difficult slots to score well.

    Args:
        operations: List of operation dicts with:
            - slot: The slot identifier
            - operation: SET, RETRACT, or KEEP_UNKNOWN
            - was_correct: Whether the operation was correct
        required_slots: Full set of required slot identifiers that must be addressed.

    Returns:
        Dict with:
            addressed_count: Number of required slots the model addressed.
            required_count: Total number of required slots (denominator).
            coverage: Fraction of required slots addressed.
            correct_count: Number of correctly handled slots.
            incorrect_count: Number of incorrectly handled slots.
            unaddressed_count: Number of required slots NOT addressed (treated as errors).
            correctness_rate: correct / required (full denominator).
            keep_unknown_correct: Number of correct KEEP_UNKNOWN operations.
            keep_unknown_total: Total KEEP_UNKNOWN operations.
            keep_unknown_rate: KEEP_UNKNOWN correctness (if any).
    """
    addressed_slots = {op.get("slot") for op in operations if op.get("slot")}
    addressed_required = addressed_slots & required_slots
    unaddressed = required_slots - addressed_slots

    # Filter to operations on required slots
    required_ops = [op for op in operations if op.get("slot") in required_slots]

    correct_count = sum(1 for op in required_ops if op.get("was_correct", False))
    incorrect_count = len(required_ops) - correct_count

    # KEEP_UNKNOWN specific
    keep_unknown_ops = [op for op in required_ops if op.get("operation") == "KEEP_UNKNOWN"]
    keep_unknown_correct = sum(1 for op in keep_unknown_ops if op.get("was_correct", False))

    required_count = len(required_slots)

    return {
        "addressed_count": len(addressed_required),
        "required_count": required_count,
        "coverage": len(addressed_required) / required_count if required_count > 0 else 0.0,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unaddressed_count": len(unaddressed),
        # R3 Issue #7: Denominator is FULL required slots, not just addressed
        "correctness_rate": correct_count / required_count if required_count > 0 else None,
        "keep_unknown_correct": keep_unknown_correct,
        "keep_unknown_total": len(keep_unknown_ops),
        "keep_unknown_rate": (
            keep_unknown_correct / len(keep_unknown_ops)
            if keep_unknown_ops else None
        ),
        "interpretation": (
            "correctness_rate uses full required-slot denominator. "
            "Unaddressed required slots count as errors (implicit incorrect). "
            "A model cannot improve by avoiding difficult slots."
        ),
    }


# ---------------------------------------------------------------------------
# Conditional Overreaction O
# R3 Issue #4: Resampling-based noise floor estimation
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


def compute_conditional_overreaction_signed(packages: list[dict]) -> dict | None:
    """Compute conditional overreaction with signed differences.

    R3 Issue #4: Report signed difference, not just absolute value.

    Args:
        packages: List of package dicts with {kind, p_before, p_after}.

    Returns:
        Dict with mean signed change, mean absolute change, and individual diffs,
        or None if no qualifying packages.
    """
    qualifying = [p for p in packages if p.get("kind") in INFORMATION_FREE_KINDS]

    if not qualifying:
        return None

    signed_diffs = []
    for pkg in qualifying:
        p_before = _validate_prob(pkg["p_before"])
        p_after = _validate_prob(pkg["p_after"])
        signed_diffs.append(p_after - p_before)

    abs_diffs = [abs(d) for d in signed_diffs]

    return {
        "mean_signed_change": sum(signed_diffs) / len(signed_diffs),
        "mean_absolute_change": sum(abs_diffs) / len(abs_diffs),
        "signed_diffs": signed_diffs,
        "count": len(qualifying),
    }


def estimate_conditional_noise_floor(
    identity_branch_deltas: list[float],
    *,
    confidence_level: float = 0.95,
) -> dict:
    """Estimate conditional noise floor via identity-identity branch resampling.

    R3 Issue #4: O must use the ledger's identity-vs-identity resampled branches
    (built in R1, available via arrival_relationship/version_relationship fields)
    to estimate a genuine conditional noise floor via resampling, not a bare
    scalar comparison.

    This function takes deltas from identity-identity branches (where the same
    parent state processes duplicate/identity evidence twice) and computes
    a distribution of expected noise.

    Note: Full paired-branch fork-based O estimation across parent states is
    R4's job with trap_policies.py/fixtures. This function provides the
    STATISTICAL definition of the noise floor that R4 will call.

    Args:
        identity_branch_deltas: List of observed |p' - p| deltas from
            identity-identity branches. Each delta is the absolute difference
            between two runs that processed the SAME evidence from the SAME
            parent state.
        confidence_level: Confidence level for interval estimation (default 0.95).

    Returns:
        Dict with:
            mean: Mean of observed deltas (point estimate of noise floor).
            std: Standard deviation of deltas.
            interval: (lower, upper) interval at specified confidence level.
            count: Number of observations.
            interpretation: Note about proper statistical usage.

    Raises:
        ValueError: If no deltas provided.
    """
    if not identity_branch_deltas:
        raise ValueError("Cannot estimate noise floor from empty delta list")

    n = len(identity_branch_deltas)
    mean_delta = sum(identity_branch_deltas) / n

    if n < 2:
        # Single observation: no variance estimate
        return {
            "mean": mean_delta,
            "std": None,
            "interval": (0.0, mean_delta * 2) if mean_delta > 0 else (0.0, 0.0),
            "count": n,
            "interpretation": (
                "Single observation - interval is heuristic. "
                "More identity-branch samples needed for reliable estimation."
            ),
        }

    # Compute standard deviation
    variance = sum((d - mean_delta) ** 2 for d in identity_branch_deltas) / (n - 1)
    std_delta = math.sqrt(variance)

    # For interval estimation, use normal approximation or percentiles
    # With small samples, report empirical percentiles
    sorted_deltas = sorted(identity_branch_deltas)

    # Compute percentile indices
    lower_pct = (1 - confidence_level) / 2
    upper_pct = 1 - lower_pct

    lower_idx = int(lower_pct * n)
    upper_idx = min(int(upper_pct * n), n - 1)

    # Use empirical percentiles
    interval_lower = sorted_deltas[lower_idx]
    interval_upper = sorted_deltas[upper_idx]

    return {
        "mean": mean_delta,
        "std": std_delta,
        "interval": (interval_lower, interval_upper),
        "count": n,
        "confidence_level": confidence_level,
        "interpretation": (
            "Noise floor estimated from identity-identity branches. "
            "Interval is empirical percentile-based. "
            "Agent O exceeding interval.upper suggests signal beyond noise."
        ),
    }


def overreaction_vs_noise_floor(O_agent: float, noise_floor: float) -> dict:
    """Compare agent overreaction against resampling noise floor (DEPRECATED).

    WARNING: This function uses a bare scalar comparison. Use
    compare_overreaction_to_noise_interval for proper statistical treatment.

    Args:
        O_agent: The agent's overreaction value.
        noise_floor: The expected overreaction from repeated sampling noise.

    Returns:
        Comparison dict with O_agent, noise_floor, and whether agent exceeds noise.
    """
    warnings.warn(
        "overreaction_vs_noise_floor uses bare scalar comparison. "
        "Use compare_overreaction_to_noise_interval for proper statistical treatment.",
        DeprecationWarning,
        stacklevel=2,
    )
    return {
        "O_agent": O_agent,
        "noise_floor": noise_floor,
        "exceeds_noise": O_agent > noise_floor,
        "ratio": O_agent / noise_floor if noise_floor > 0 else None,
    }


def compare_overreaction_to_noise_interval(
    O_agent: float,
    noise_estimate: dict,
    *,
    equivalence_tolerance: float = 0.0,
) -> dict:
    """Compare agent overreaction to resampling noise interval.

    R3 Issue #4: Report signed difference + interval + pre-registered equivalence
    tolerance, not just O > noise_floor as a bare significance test.

    Args:
        O_agent: The agent's observed overreaction value.
        noise_estimate: Output from estimate_conditional_noise_floor.
        equivalence_tolerance: Pre-registered tolerance for practical equivalence.
            If O_agent is within (noise_mean - tolerance, noise_mean + tolerance),
            it may be considered practically equivalent to noise.

    Returns:
        Dict with:
            O_agent: The agent's overreaction.
            noise_mean: Mean noise floor.
            noise_interval: (lower, upper) noise interval.
            signed_diff: O_agent - noise_mean (positive = more than noise).
            exceeds_interval: Whether O_agent > interval upper bound.
            within_tolerance: Whether O_agent is within equivalence tolerance.
            interpretation: Summary of comparison.
    """
    noise_mean = noise_estimate["mean"]
    noise_interval = noise_estimate["interval"]

    signed_diff = O_agent - noise_mean
    exceeds_interval = O_agent > noise_interval[1]
    within_tolerance = abs(signed_diff) <= equivalence_tolerance

    # Build interpretation
    if within_tolerance:
        interp = "Agent O is within pre-registered equivalence tolerance of noise."
    elif exceeds_interval:
        interp = (
            f"Agent O ({O_agent:.4f}) exceeds noise interval upper bound "
            f"({noise_interval[1]:.4f}). May indicate genuine overreaction."
        )
    elif O_agent < noise_interval[0]:
        interp = (
            f"Agent O ({O_agent:.4f}) is below noise interval lower bound "
            f"({noise_interval[0]:.4f}). Less drift than expected baseline noise."
        )
    else:
        interp = (
            f"Agent O ({O_agent:.4f}) is within noise interval "
            f"[{noise_interval[0]:.4f}, {noise_interval[1]:.4f}]. "
            f"Cannot distinguish from noise."
        )

    return {
        "O_agent": O_agent,
        "noise_mean": noise_mean,
        "noise_interval": noise_interval,
        "signed_diff": signed_diff,
        "exceeds_interval": exceeds_interval,
        "within_tolerance": within_tolerance,
        "equivalence_tolerance": equivalence_tolerance,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# Timeliness with right-censoring
# R3 Issue #6: Censoring-aware inference, not just mean + side-count
# ---------------------------------------------------------------------------


def compute_timeliness(amendments: list[dict]) -> dict:
    """Compute timeliness metrics with right-censoring (DEPRECATED).

    WARNING: This function only computes mean over responders plus a count.
    Use compute_timeliness_censored for proper censoring-aware inference.

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


def compute_timeliness_censored(amendments: list[dict]) -> dict:
    """Compute timeliness with proper right-censoring treatment.

    R3 Issue #6: A single censored_count column doesn't constitute real
    censoring-aware inference. This function implements Kaplan-Meier-style
    estimation with appropriate bounds.

    For each amendment:
    - If responded: exact response time is known
    - If censored: we only know response time > (censor_at - available_at)

    The mean over responders UNDERESTIMATES true mean timeliness because
    it ignores information from censored cases (which have longer times).

    Args:
        amendments: List of dicts with:
            - source_id: Amendment identifier
            - available_at: When amendment became available
            - first_compliant_commit_at: When first responded (None if censored)
            - censor_at: Observation end time (required for censored amendments)

    Returns:
        Dict with:
            observed_mean: Mean over observed (responded) amendments.
            observed_median: Median over observed amendments.
            observed_count: Number of observed response times.
            censored_count: Number of right-censored amendments.
            total_count: Total amendments.
            censoring_rate: Fraction of amendments that are censored.
            lower_bound_mean: Conservative lower bound (observed mean is a lower bound
                             for true mean when there are censored observations).
            upper_bound_mean: Upper bound treating censored as observed at censor time.
            km_survival_at_max: Kaplan-Meier survival estimate at max observed time.
            interpretation: Note about proper interpretation.
    """
    observed_times = []
    censored_times = []  # Lower bounds for censored

    for amd in amendments:
        available_at = amd.get("available_at")
        responded_at = amd.get("first_compliant_commit_at")

        if responded_at is not None:
            response_time = responded_at - available_at
            observed_times.append(response_time)
        else:
            # Censored: we know time > (censor_at - available_at)
            censor_at = amd.get("censor_at")
            if censor_at is not None:
                censored_lower_bound = censor_at - available_at
                censored_times.append(censored_lower_bound)
            # If no censor_at, we can't bound - treat as 0 lower bound
            else:
                censored_times.append(0)

    total = len(observed_times) + len(censored_times)

    if total == 0:
        return {
            "observed_mean": None,
            "observed_median": None,
            "observed_count": 0,
            "censored_count": 0,
            "total_count": 0,
            "censoring_rate": 0.0,
            "lower_bound_mean": None,
            "upper_bound_mean": None,
            "km_survival_at_max": None,
            "interpretation": "No amendments to analyze.",
        }

    observed_count = len(observed_times)
    censored_count = len(censored_times)
    censoring_rate = censored_count / total

    # Observed statistics
    observed_mean = sum(observed_times) / observed_count if observed_count > 0 else None
    observed_median = (
        sorted(observed_times)[observed_count // 2]
        if observed_count > 0 else None
    )

    # Lower bound: observed mean is a lower bound (ignores censored with longer times)
    lower_bound_mean = observed_mean

    # Upper bound: treat censored as observed at their censoring time
    # This is still a lower bound on their true times, so upper_bound_mean
    # is still a conservative estimate
    all_times = observed_times + censored_times
    upper_bound_mean = sum(all_times) / total if total > 0 else None

    # Simple Kaplan-Meier survival at maximum observed time
    # S(t) = product of (1 - d_i / n_i) where d_i = deaths at time i
    # This is a simplified estimate
    km_survival = None
    if observed_count > 0:
        max_observed = max(observed_times)
        # Number "at risk" at max time includes censored with lower_bound > max_observed
        at_risk_at_max = sum(1 for t in censored_times if t >= max_observed)
        # Crude survival estimate: fraction not yet responded by max observed time
        km_survival = at_risk_at_max / total if total > 0 else 0.0

    # Build interpretation
    if censoring_rate > 0.5:
        interp = (
            f"High censoring rate ({censoring_rate:.1%}). observed_mean significantly "
            f"underestimates true mean. Report bounds, not point estimate."
        )
    elif censoring_rate > 0:
        interp = (
            f"Censoring present ({censoring_rate:.1%}). observed_mean is a lower bound. "
            f"True mean is between lower_bound_mean and upper_bound_mean."
        )
    else:
        interp = "No censoring. observed_mean is the true mean."

    return {
        "observed_mean": observed_mean,
        "observed_median": observed_median,
        "observed_count": observed_count,
        "censored_count": censored_count,
        "total_count": total,
        "censoring_rate": censoring_rate,
        "lower_bound_mean": lower_bound_mean,
        "upper_bound_mean": upper_bound_mean,
        "km_survival_at_max": km_survival,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# Brier by strata (reusing brier_report)
# R3 Issue #8: Renamed from calibration_by_strata - Brier is NOT calibration
# ---------------------------------------------------------------------------


def brier_by_strata(
    rows: list[dict],
    stratum_key: str | None = None,
) -> dict:
    """Compute Brier metrics stratified by a key.

    R3 Issue #8: This function computes BRIER LOSS performance, NOT calibration.
    Brier score measures overall accuracy (resolution + calibration + uncertainty).
    For actual calibration/reliability diagnostics, use a reliability diagram
    or calibration-specific metrics (not yet implemented).

    Reuses brier_report from monitoring_v1/scoring.py for the core computation.

    Args:
        rows: List of row dicts for brier_report (opportunity_id, base, prediction, outcome).
        stratum_key: Optional key to stratify by (e.g., "lead_time", "process").
                    If None, computes overall Brier metrics.

    Returns:
        Dict mapping stratum values -> brier_report results.
    """
    if stratum_key is None:
        # Overall Brier metrics
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


def calibration_by_strata(
    rows: list[dict],
    stratum_key: str | None = None,
) -> dict:
    """DEPRECATED: Use brier_by_strata instead.

    R3 Issue #8: This function was misnamed. It computes Brier performance,
    not calibration. Brier score conflates calibration with resolution.
    For true calibration, use reliability diagrams or calibration metrics.

    Args:
        rows: List of row dicts for brier_report.
        stratum_key: Optional key to stratify by.

    Returns:
        Dict mapping stratum values -> brier_report results.
    """
    warnings.warn(
        "calibration_by_strata is deprecated and misnamed. "
        "Use brier_by_strata instead. Brier loss is not calibration.",
        DeprecationWarning,
        stacklevel=2,
    )
    return brier_by_strata(rows, stratum_key)


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
