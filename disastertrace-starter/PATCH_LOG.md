# DisasterTrace v14 Review Repair Patch Log

## R3: metrics.py semantic scoring repair (2026-09-20)

**Commit**: ee10b9a14
**Author**: Claude Opus 4.5
**Files changed**: 
- `src/disastertrace/revision_v1/metrics.py` (+790 lines)
- `tests/test_revision_metrics.py` (+406 lines, 23 new test cases)

### Issues Fixed (from review section 3)

| Issue | Description | Fix |
|-------|-------------|-----|
| #1 | effective_at_from_commits requires flattened records incompatible with raw belief schema | Added `commits_from_effective_states` adapter for belief_commit integration |
| #2 | Q lacks target-time binding, strict grid validation, cohort fingerprint; missing-Y crashes | Added `validate_scoring_grid` (rejects NaN/inf/duplicate/unsorted), `compute_cohort_fingerprint`, `trajectory_score_Q_with_bounds` for sensitivity bounds |
| #3 | RV described as causal attribution rather than loss-decomposition diagnostic | Clarified docstrings: RV is loss-change diagnostic, not causal contribution |
| #4 | O uses bare scalar noise comparison, no resampling or interval | Added `estimate_conditional_noise_floor` and `compare_overreaction_to_noise_interval` with interval reporting |
| #5 | invalid_reference_duration gives 0 for never-corrected references | Now charges uncorrected to `right_censor_at` (observation end) |
| #6 | timeliness mean ignores censoring; single count not proper inference | Added `compute_timeliness_censored` with Kaplan-Meier-style bounds |
| #7 | KEEP_UNKNOWN correctness uses only addressed slots, not full required denominator | Added `compute_fact_layer_correctness` with full required-slot denominator |
| #8 | calibration_by_strata misnamed (Brier is not calibration) | Renamed to `brier_by_strata`; deprecated alias kept |

### Missing-Y Contract (section 4)

- `trajectory_score_Q_with_bounds` computes sensitivity bounds for missing targets
- All checkpoints for a missing target share the same imputed Y (not independent per checkpoint)
- Bounds explicitly labeled as sensitivity bounds (NOT confidence intervals)
- Reports cohort fingerprint, coverage, settled/missing counts

### Review Regression Tests Fixed (FAIL -> PASS)

- `test_no_nan_checkpoint_time` (grid validation)
- `test_unresolved_stale_reference_counts_to_registered_horizon` (issue #5)
- `test_future_bad_probability_does_not_change_earlier_view` (lazy validation)

### Test Counts

- Before: 215 passed
- After: 238 passed (+23 new R3 tests)

### R4 Handoff Notes

The O noise-floor estimator function signature for R4:

```python
def estimate_conditional_noise_floor(
    identity_branch_deltas: list[float],
    *,
    confidence_level: float = 0.95,
) -> dict:
    """
    Args:
        identity_branch_deltas: Observed |p' - p| from identity-identity branches
        confidence_level: For interval estimation (default 0.95)
    
    Returns:
        {"mean": float, "std": float, "interval": (lower, upper), "count": int, ...}
    """
```

R4 should:
1. Generate identity-identity branch deltas from trap_policies fork orchestration
2. Call this function to get noise floor distribution
3. Use `compare_overreaction_to_noise_interval(O_agent, noise_estimate)` for comparison

---

## R2: belief_commit.py attempt/commit/effective chain repair (2026-09-20)

**Commit**: 23d52091a
**Issues**: 9/9 fixed per R2 self-report

---

## R1: ledger.py online prefix + source/relationship separation (2026-09-20)

**Commit**: 74d0505d9
**Issues**: 7/7 fixed per R1 self-report
