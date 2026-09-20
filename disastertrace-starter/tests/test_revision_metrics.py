"""Tests for the fixed grid trajectory scorer (P0-04).

Acceptance criteria from plan v14 section 9:
- Hand-calculated examples must match implementation output exactly
- Multiple commits on the same episode must NOT change checkpoint weights w_jk
  (weight assignment is independent of commit count)
- The same outcome Y evaluated at multiple cutoff times must yield CONSISTENT
  values (same realized outcome shouldn't produce contradictory scores)
- RV_jk must satisfy telescoping-sum property: sum over k equals first-vs-last difference

Metrics implemented:
- Q: Trajectory score = (1/N) * sum_j sum_k w_jk * L(p_eff(j, t_k), Y_j)
- Delta: Q(baseline) - Q(agent) (relative to dynamic baseline)
- RV_jk: L(p_{k-1}) - L(p_k) (telescoping property required)
- Fact layer: amendment compliance rate, invalid reference duration, KEEP_UNKNOWN correctness
- O: Conditional overreaction on lossless_duplicate/mirror/no_change_reissue packages
- Timeliness: amendment available_at to first compliant commit, right-censored
- Calibration: reuses brier_report and generic_missing_gain_bounds

Reuses:
- brier_report from monitoring_v1/scoring.py
- generic_missing_gain_bounds from monitoring_v1/scoring.py
- effective_state from revision_v1/belief_commit.py (for p_eff)
- ledger kind classification from revision_v1/ledger.py (for overreaction scoping)
"""

import math
import pytest

from disastertrace.monitoring_v1.targets import canonical_hash, utc_us


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def us(iso_str):
    """Convert ISO string to microseconds since epoch."""
    return utc_us(iso_str)


# ---------------------------------------------------------------------------
# Hand-calculated examples for Q (trajectory score)
# ---------------------------------------------------------------------------


class TestTrajectoryScoreQ:
    """Test trajectory score Q = (1/N) * sum_j sum_k w_jk * L(p_eff(j, t_k), Y_j)."""

    def test_hand_calculated_single_target_single_checkpoint(self):
        """Hand-calculated example: one target, one checkpoint.

        Setup:
        - Target j=0, checkpoint at t=10, weight w=1.0 (sums to 1)
        - Commit at t=5 with p=0.8
        - Outcome Y=1

        Hand calculation:
        - p_eff(j=0, t=10) = 0.8 (commit at t=5 is effective at t=10)
        - L(0.8, 1) = (0.8 - 1)^2 = 0.04
        - Q = (1/1) * 1.0 * 0.04 = 0.04
        """
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": 0.8}]
        grid = {"t0": [(10, 1.0)]}  # (time, weight) pairs
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        result = trajectory_score_Q(commits, grid, outcomes, fallback)

        assert math.isclose(result, 0.04, rel_tol=1e-9)

    def test_hand_calculated_three_checkpoints_equal_weight(self):
        """Hand-calculated example: one target, three checkpoints with equal weight.

        Setup:
        - Target j=0, checkpoints at t=10, 20, 30, weights = 1/3 each
        - Commit at t=5 with p=0.2, commit at t=15 with p=0.6
        - Outcome Y=1

        Hand calculation:
        - p_eff(j=0, t=10) = 0.2 (commit at t=5)
        - p_eff(j=0, t=20) = 0.6 (commit at t=15)
        - p_eff(j=0, t=30) = 0.6 (HOLD from t=15)
        - L(0.2, 1) = 0.64
        - L(0.6, 1) = 0.16
        - Q = (1/1) * (1/3 * 0.64 + 1/3 * 0.16 + 1/3 * 0.16)
        - Q = (1/3) * (0.64 + 0.16 + 0.16) = 0.96 / 3 = 0.32
        """
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.2},
            {"target_id": "t0", "effective_at": 15, "probability": 0.6},
        ]
        grid = {"t0": [(10, 1/3), (20, 1/3), (30, 1/3)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        result = trajectory_score_Q(commits, grid, outcomes, fallback)

        assert math.isclose(result, 0.32, rel_tol=1e-9)

    def test_hand_calculated_two_targets(self):
        """Hand-calculated example: two targets, different outcomes.

        Setup:
        - Target t0: checkpoint at t=10, w=1.0, commit at t=5 with p=0.9, Y=1
        - Target t1: checkpoint at t=10, w=1.0, commit at t=5 with p=0.1, Y=0

        Hand calculation:
        - Q_t0 = 1.0 * (0.9 - 1)^2 = 0.01
        - Q_t1 = 1.0 * (0.1 - 0)^2 = 0.01
        - Q = (1/2) * (0.01 + 0.01) = 0.01
        """
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.9},
            {"target_id": "t1", "effective_at": 5, "probability": 0.1},
        ]
        grid = {
            "t0": [(10, 1.0)],
            "t1": [(10, 1.0)],
        }
        outcomes = {"t0": 1, "t1": 0}
        fallback = {"t0": 0.5, "t1": 0.5}

        result = trajectory_score_Q(commits, grid, outcomes, fallback)

        assert math.isclose(result, 0.01, rel_tol=1e-9)

    def test_hold_carries_forward(self):
        """HOLD semantics: p_eff carries forward when no new commit."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        # Only one commit at t=5, evaluated at t=10, 20, 30
        commits = [{"target_id": "t0", "effective_at": 5, "probability": 0.7}]
        grid = {"t0": [(10, 0.5), (20, 0.25), (30, 0.25)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        result = trajectory_score_Q(commits, grid, outcomes, fallback)

        # L(0.7, 1) = 0.09 at all checkpoints (HOLD carries forward)
        expected = 0.5 * 0.09 + 0.25 * 0.09 + 0.25 * 0.09  # = 0.09
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_fallback_before_first_commit(self):
        """Fallback is used before any commit is effective."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        # Commit at t=15, but checkpoint at t=10 (before commit)
        commits = [{"target_id": "t0", "effective_at": 15, "probability": 0.9}]
        grid = {"t0": [(10, 0.5), (20, 0.5)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.2}

        result = trajectory_score_Q(commits, grid, outcomes, fallback)

        # t=10: p_eff = 0.2 (fallback), L(0.2, 1) = 0.64
        # t=20: p_eff = 0.9 (commit), L(0.9, 1) = 0.01
        expected = 0.5 * 0.64 + 0.5 * 0.01  # = 0.325
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_weights_must_sum_to_one(self):
        """Grid weights for each target must sum to 1."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": 0.5}]
        grid = {"t0": [(10, 0.6), (20, 0.6)]}  # sums to 1.2, not 1
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        with pytest.raises(ValueError, match="sum to one"):
            trajectory_score_Q(commits, grid, outcomes, fallback)

    def test_negative_weight_rejected(self):
        """Negative weights are rejected."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": 0.5}]
        grid = {"t0": [(10, -0.5), (20, 1.5)]}  # negative weight
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        with pytest.raises(ValueError, match="negative"):
            trajectory_score_Q(commits, grid, outcomes, fallback)

    def test_multiple_commits_same_episode_does_not_change_weights(self):
        """Multiple commits on same episode must NOT change checkpoint weights.

        This acceptance criterion ensures that the weight assignment is
        independent of how many belief-commits were made.
        """
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        # Many commits, but grid weights stay fixed
        commits_few = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.8},
        ]
        commits_many = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.3},
            {"target_id": "t0", "effective_at": 8, "probability": 0.5},
            {"target_id": "t0", "effective_at": 12, "probability": 0.8},
        ]

        # Same grid (weights sum to 1) regardless of commit count
        grid = {"t0": [(10, 0.5), (20, 0.5)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        # Score with many commits (final p_eff at each checkpoint differs)
        # t=10: p_eff = 0.5 (commit at t=8), L(0.5, 1) = 0.25
        # t=20: p_eff = 0.8 (commit at t=12), L(0.8, 1) = 0.04
        result_many = trajectory_score_Q(commits_many, grid, outcomes, fallback)
        expected_many = 0.5 * 0.25 + 0.5 * 0.04  # = 0.145
        assert math.isclose(result_many, expected_many, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Delta: relative to baseline
# ---------------------------------------------------------------------------


class TestDelta:
    """Test Delta = Q(baseline) - Q(agent)."""

    def test_hand_calculated_delta(self):
        """Hand-calculated Delta: baseline worse than agent."""
        from disastertrace.revision_v1.metrics import compute_delta

        # Agent has lower Q (better), baseline has higher Q (worse)
        q_agent = 0.04
        q_baseline = 0.16

        delta = compute_delta(q_baseline, q_agent)
        assert math.isclose(delta, 0.12, rel_tol=1e-9)

    def test_delta_zero_when_equal(self):
        """Delta is zero when agent equals baseline."""
        from disastertrace.revision_v1.metrics import compute_delta

        delta = compute_delta(0.1, 0.1)
        assert delta == 0.0


# ---------------------------------------------------------------------------
# RV_jk: Revision Value with telescoping property
# ---------------------------------------------------------------------------


class TestRVjk:
    """Test RV_jk = L(p_{k-1}) - L(p_k) with telescoping sum."""

    def test_telescoping_sum_property(self):
        """RV sum across k must equal L(p_0) - L(p_n).

        This is an explicit assertion/test per the plan acceptance criteria.
        """
        from disastertrace.revision_v1.metrics import compute_rv_sequence

        # Sequence of probabilities: 0.2 -> 0.6 -> 0.4 -> 0.8
        # Y = 1
        probs = [0.2, 0.6, 0.4, 0.8]
        y = 1

        rv_values = compute_rv_sequence(probs, y)

        # Hand calculation of L(p, 1) = (p - 1)^2
        # L(0.2) = 0.64, L(0.6) = 0.16, L(0.4) = 0.36, L(0.8) = 0.04
        # RV[0] = L(0.2) - L(0.6) = 0.64 - 0.16 = 0.48
        # RV[1] = L(0.6) - L(0.4) = 0.16 - 0.36 = -0.20
        # RV[2] = L(0.4) - L(0.8) = 0.36 - 0.04 = 0.32
        # Sum = 0.48 - 0.20 + 0.32 = 0.60
        # L(first) - L(last) = 0.64 - 0.04 = 0.60

        assert len(rv_values) == 3  # n-1 values for n probabilities

        # Verify individual RV values
        assert math.isclose(rv_values[0], 0.48, rel_tol=1e-9)
        assert math.isclose(rv_values[1], -0.20, rel_tol=1e-9)
        assert math.isclose(rv_values[2], 0.32, rel_tol=1e-9)

        # CRITICAL: Verify telescoping sum property
        rv_sum = sum(rv_values)
        L_first = (probs[0] - y) ** 2
        L_last = (probs[-1] - y) ** 2
        expected_sum = L_first - L_last

        assert math.isclose(rv_sum, expected_sum, rel_tol=1e-9), (
            f"Telescoping sum failed: sum(RV)={rv_sum}, "
            f"L(first)-L(last)={expected_sum}"
        )

    def test_telescoping_y_equals_zero(self):
        """Telescoping property also holds for Y=0."""
        from disastertrace.revision_v1.metrics import compute_rv_sequence

        probs = [0.1, 0.5, 0.3]
        y = 0

        rv_values = compute_rv_sequence(probs, y)

        rv_sum = sum(rv_values)
        L_first = (probs[0] - y) ** 2
        L_last = (probs[-1] - y) ** 2

        assert math.isclose(rv_sum, L_first - L_last, rel_tol=1e-9)

    def test_single_probability_no_rv(self):
        """Single probability yields empty RV sequence."""
        from disastertrace.revision_v1.metrics import compute_rv_sequence

        rv_values = compute_rv_sequence([0.5], 1)
        assert rv_values == []


# ---------------------------------------------------------------------------
# Fact layer metrics
# ---------------------------------------------------------------------------


class TestFactLayerMetrics:
    """Test fact layer compliance rate, invalid reference duration, KEEP_UNKNOWN."""

    def test_amendment_compliance_rate(self):
        """Amendment compliance = fraction of amendments properly adopted."""
        from disastertrace.revision_v1.metrics import compute_amendment_compliance_rate

        # 3 amendments, 2 properly adopted
        amendments = [
            {"source_id": "amd-1", "properly_adopted": True},
            {"source_id": "amd-2", "properly_adopted": False},
            {"source_id": "amd-3", "properly_adopted": True},
        ]

        rate = compute_amendment_compliance_rate(amendments)
        assert math.isclose(rate, 2/3, rel_tol=1e-9)

    def test_amendment_compliance_empty(self):
        """Empty amendments list returns None (undefined)."""
        from disastertrace.revision_v1.metrics import compute_amendment_compliance_rate

        rate = compute_amendment_compliance_rate([])
        assert rate is None

    def test_invalid_reference_duration(self):
        """Invalid reference duration = total time referencing superseded evidence."""
        from disastertrace.revision_v1.metrics import compute_invalid_reference_duration

        # Commit references evidence that was superseded at time 100
        # Commit stays referencing it until correction at time 150
        # Duration = 50
        references = [
            {"evidence_id": "ev-1", "superseded_at": 100, "corrected_at": 150},
            {"evidence_id": "ev-2", "superseded_at": 200, "corrected_at": 220},
        ]

        total_duration = compute_invalid_reference_duration(references)
        assert total_duration == 70  # 50 + 20

    def test_keep_unknown_correctness_rate(self):
        """KEEP_UNKNOWN correctness = fraction of KEEP_UNKNOWN operations that were correct."""
        from disastertrace.revision_v1.metrics import compute_keep_unknown_correctness_rate

        # 4 KEEP_UNKNOWN operations, 3 were actually correct (value was truly unknown)
        operations = [
            {"operation": "KEEP_UNKNOWN", "was_correct": True},
            {"operation": "KEEP_UNKNOWN", "was_correct": True},
            {"operation": "KEEP_UNKNOWN", "was_correct": False},
            {"operation": "KEEP_UNKNOWN", "was_correct": True},
        ]

        rate = compute_keep_unknown_correctness_rate(operations)
        assert math.isclose(rate, 0.75, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Conditional Overreaction O
# ---------------------------------------------------------------------------


class TestConditionalOverreaction:
    """Test O = E|p' - p| on lossless_duplicate/mirror/no_change_reissue only."""

    def test_overreaction_on_information_free_evidence(self):
        """Overreaction measures belief change on information-free evidence.

        Acceptance criteria: computed ONLY over lossless_duplicate/mirror/no_change_reissue.
        """
        from disastertrace.revision_v1.metrics import compute_conditional_overreaction

        # Evidence packages with kinds
        packages = [
            {"kind": "new_observation", "p_before": 0.3, "p_after": 0.7},  # excluded
            {"kind": "lossless_duplicate", "p_before": 0.5, "p_after": 0.52},
            {"kind": "mirror", "p_before": 0.6, "p_after": 0.58},
            {"kind": "no_change_reissue", "p_before": 0.4, "p_after": 0.45},
            {"kind": "amendment_supersedes", "p_before": 0.2, "p_after": 0.8},  # excluded
        ]

        O = compute_conditional_overreaction(packages)

        # Only 3 packages qualify: |0.52-0.5| + |0.58-0.6| + |0.45-0.4| = 0.02 + 0.02 + 0.05 = 0.09
        # O = 0.09 / 3 = 0.03
        assert math.isclose(O, 0.03, rel_tol=1e-9)

    def test_overreaction_empty_when_no_qualifying_packages(self):
        """Returns None when no lossless_duplicate/mirror/no_change_reissue."""
        from disastertrace.revision_v1.metrics import compute_conditional_overreaction

        packages = [
            {"kind": "new_observation", "p_before": 0.3, "p_after": 0.7},
            {"kind": "amendment_supersedes", "p_before": 0.2, "p_after": 0.8},
        ]

        O = compute_conditional_overreaction(packages)
        assert O is None

    def test_overreaction_ideal_zero(self):
        """Ideal agent has zero overreaction on information-free evidence."""
        from disastertrace.revision_v1.metrics import compute_conditional_overreaction

        packages = [
            {"kind": "lossless_duplicate", "p_before": 0.5, "p_after": 0.5},
            {"kind": "mirror", "p_before": 0.6, "p_after": 0.6},
        ]

        O = compute_conditional_overreaction(packages)
        assert O == 0.0

    def test_compare_to_resampling_noise_floor(self):
        """Overreaction should be compared against resampling noise floor."""
        from disastertrace.revision_v1.metrics import overreaction_vs_noise_floor

        # Agent overreaction
        O_agent = 0.03

        # Resampling noise floor (simulated from repeated sampling)
        noise_samples = [0.02, 0.025, 0.018, 0.022, 0.019]
        noise_floor = sum(noise_samples) / len(noise_samples)

        comparison = overreaction_vs_noise_floor(O_agent, noise_floor)

        assert "O_agent" in comparison
        assert "noise_floor" in comparison
        assert "exceeds_noise" in comparison


# ---------------------------------------------------------------------------
# Timeliness with right-censoring
# ---------------------------------------------------------------------------


class TestTimeliness:
    """Test timeliness: amendment available_at to first compliant commit."""

    def test_timeliness_compliant_response(self):
        """Timeliness = interval from amendment available_at to first compliant commit."""
        from disastertrace.revision_v1.metrics import compute_timeliness

        amendments = [
            {"source_id": "amd-1", "available_at": 100, "first_compliant_commit_at": 150},
            {"source_id": "amd-2", "available_at": 200, "first_compliant_commit_at": 210},
        ]

        result = compute_timeliness(amendments)

        assert result["mean_response_time"] == 30.0  # (50 + 10) / 2
        assert result["compliant_count"] == 2
        assert result["right_censored_count"] == 0

    def test_timeliness_right_censored(self):
        """Right-censored: amendments not yet responded to."""
        from disastertrace.revision_v1.metrics import compute_timeliness

        amendments = [
            {"source_id": "amd-1", "available_at": 100, "first_compliant_commit_at": 150},
            {"source_id": "amd-2", "available_at": 200, "first_compliant_commit_at": None},  # censored
        ]

        result = compute_timeliness(amendments)

        assert result["mean_response_time"] == 50.0  # only the compliant one
        assert result["compliant_count"] == 1
        assert result["right_censored_count"] == 1

    def test_timeliness_all_censored(self):
        """All right-censored returns None for mean."""
        from disastertrace.revision_v1.metrics import compute_timeliness

        amendments = [
            {"source_id": "amd-1", "available_at": 100, "first_compliant_commit_at": None},
            {"source_id": "amd-2", "available_at": 200, "first_compliant_commit_at": None},
        ]

        result = compute_timeliness(amendments)

        assert result["mean_response_time"] is None
        assert result["compliant_count"] == 0
        assert result["right_censored_count"] == 2


# ---------------------------------------------------------------------------
# Calibration by lead-time/process
# ---------------------------------------------------------------------------


class TestCalibration:
    """Test calibration metrics reusing brier_report and generic_missing_gain_bounds."""

    def test_calibration_by_lead_time(self):
        """Calibration stratified by lead time."""
        from disastertrace.revision_v1.metrics import calibration_by_strata

        rows = [
            {"opportunity_id": "op1", "base": 0.5, "prediction": 0.8, "outcome": 1, "lead_time": "1h"},
            {"opportunity_id": "op2", "base": 0.5, "prediction": 0.3, "outcome": 0, "lead_time": "1h"},
            {"opportunity_id": "op3", "base": 0.5, "prediction": 0.6, "outcome": 1, "lead_time": "3h"},
        ]

        result = calibration_by_strata(rows, stratum_key="lead_time")

        assert "1h" in result
        assert "3h" in result
        assert "opportunities" in result["1h"]
        assert "system_brier" in result["1h"]

    def test_reuses_brier_report(self):
        """Calibration must reuse brier_report from monitoring_v1/scoring.py."""
        from disastertrace.revision_v1.metrics import calibration_by_strata
        from disastertrace.monitoring_v1.scoring import brier_report

        rows = [
            {"opportunity_id": "op1", "base": 0.5, "prediction": 0.7, "outcome": 1},
        ]

        # Direct brier_report call for reference
        direct_result = brier_report(rows)

        # Our calibration should give same result for single-stratum case
        calib_result = calibration_by_strata(rows, stratum_key=None)

        assert calib_result["all"]["system_brier"] == direct_result["system_brier"]

    def test_missing_outcome_bounds_reused(self):
        """Missing outcome bounds reuse generic_missing_gain_bounds."""
        from disastertrace.revision_v1.metrics import compute_missing_outcome_bounds
        from disastertrace.monitoring_v1.scoring import generic_missing_gain_bounds

        # Same parameters should give same result
        settlement_fraction = 0.8
        settled_mean_gain = 0.05

        # Direct call
        direct_bounds = generic_missing_gain_bounds(settlement_fraction, settled_mean_gain)

        # Our wrapper
        our_bounds = compute_missing_outcome_bounds(settlement_fraction, settled_mean_gain)

        assert our_bounds == direct_bounds


# ---------------------------------------------------------------------------
# Consistency: same Y at multiple cutoffs
# ---------------------------------------------------------------------------


class TestConsistency:
    """Test that same outcome Y at multiple cutoffs yields consistent values."""

    def test_same_outcome_different_cutoffs_consistent(self):
        """Same Y evaluated at different cutoff times must be consistent.

        'Consistent' means: the same realized outcome shouldn't produce
        contradictory scores just because you evaluated at a different time.
        """
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        # Same commits, same outcome Y=1
        commits = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.7},
        ]
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        # Different grids (different cutoff times), but weights sum to 1
        grid_early = {"t0": [(10, 1.0)]}
        grid_late = {"t0": [(20, 1.0)]}
        grid_both = {"t0": [(10, 0.5), (20, 0.5)]}

        Q_early = trajectory_score_Q(commits, grid_early, outcomes, fallback)
        Q_late = trajectory_score_Q(commits, grid_late, outcomes, fallback)
        Q_both = trajectory_score_Q(commits, grid_both, outcomes, fallback)

        # All use same p_eff (0.7 from HOLD carry-forward) and same Y=1
        # So all should yield the same loss L(0.7, 1) = 0.09
        assert math.isclose(Q_early, 0.09, rel_tol=1e-9)
        assert math.isclose(Q_late, 0.09, rel_tol=1e-9)
        assert math.isclose(Q_both, 0.09, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Probability validation
# ---------------------------------------------------------------------------


class TestProbabilityValidation:
    """Test probability input validation."""

    def test_probability_outside_zero_one_rejected(self):
        """Probability outside [0, 1] is rejected."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": 1.5}]
        grid = {"t0": [(10, 1.0)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        with pytest.raises(ValueError):
            trajectory_score_Q(commits, grid, outcomes, fallback)

    def test_nan_probability_rejected(self):
        """NaN probability is rejected."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": float("nan")}]
        grid = {"t0": [(10, 1.0)]}
        outcomes = {"t0": 1}
        fallback = {"t0": 0.5}

        with pytest.raises(ValueError):
            trajectory_score_Q(commits, grid, outcomes, fallback)

    def test_boolean_outcome_rejected(self):
        """Boolean outcome (True/False) is rejected; must be int 0/1."""
        from disastertrace.revision_v1.metrics import trajectory_score_Q

        commits = [{"target_id": "t0", "effective_at": 5, "probability": 0.5}]
        grid = {"t0": [(10, 1.0)]}
        outcomes = {"t0": True}  # Should be int 1, not bool True
        fallback = {"t0": 0.5}

        with pytest.raises(ValueError):
            trajectory_score_Q(commits, grid, outcomes, fallback)


# ---------------------------------------------------------------------------
# Integration with belief_commit effective state
# ---------------------------------------------------------------------------


class TestEffectiveStateIntegration:
    """Test that metrics use belief_commit's effective state resolution."""

    def test_effective_at_uses_belief_commit_semantics(self):
        """effective_at_from_commits uses belief_commit's HOLD carry-forward."""
        from disastertrace.revision_v1.metrics import effective_at_from_commits

        commits = [
            {"target_id": "t0", "effective_at": 5, "probability": 0.3},
            {"target_id": "t0", "effective_at": 15, "probability": 0.7},
        ]
        fallback = 0.5

        # Before first commit: fallback
        assert effective_at_from_commits("t0", commits, 3, fallback) == 0.5
        # At t=10: commit at t=5 is effective
        assert effective_at_from_commits("t0", commits, 10, fallback) == 0.3
        # At t=20: commit at t=15 is effective
        assert effective_at_from_commits("t0", commits, 20, fallback) == 0.7
        # At t=30: HOLD from t=15
        assert effective_at_from_commits("t0", commits, 30, fallback) == 0.7
