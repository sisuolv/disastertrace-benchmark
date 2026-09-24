> **⚠️ PARTIALLY SUPERSEDED BY BATCH V4 (2026-09-23/24).** The line below stating "A legacy target
> containing conflicting settled outcomes is retained and reported as `inconsistent_target_groups`"
> is no longer accurate: as of V4's C2 fix, a conflicting target's rows are **excluded** from every
> qualified/primary score field (`system_brier`, `net_realized_gain`, `g_plus`, `g_minus`,
> `base_brier`, `full_population_gain_bounds`, `settled`, `missing`), not merely flagged while still
> contributing to them. The old all-rows numbers remain available only under a new
> `legacy_all_rows_including_conflicts` sub-dict, explicitly marked `audit_only: True, qualified:
> False`. See `plan/plan_v19_0923/v19_execution_20260923_v4/OPUS_REVIEW_OF_SONNET.md` for the full
> account (independently adversarially reviewed against 4,000 random rosters). The rest of this
> document (registration-is-denominator, carry-forward, missing-outcome joint completion) remains
> accurate. Original text preserved unchanged below.

---

# v18 complete-grid scorer contract, repaired

The registration roster is the denominator. Every registered
`target_id/method/checkpoint_id` cell remains in the output, including invalid,
late, not-dispatched, stop and missing submissions.

Each registration may provide a nonnegative integer `checkpoint_index` and a
finite nonnegative `checkpoint_weight`. An omitted registration `outcome`
means that the outcome is pending (`None`); only integer 0 or 1 is accepted
when it is supplied. The
adapter normalizes weights within each target/method trajectory and emits the
normalized value as `score_weight`. A trajectory must have a positive total
weight. The score is therefore target- and trajectory-normalized instead of
silently weighting targets with more checkpoints more heavily.

For a cell with no valid current submission, the adapter carries forward the
last valid probability when enabled; otherwise it uses the registered
fallback. Submission status and prediction source remain separate.

Missing outcomes remain `None`. If all unresolved cells in a target share one
hidden binary outcome, the two possible target completions are evaluated
jointly before taking the bound. A legacy target containing conflicting
settled outcomes is retained and reported as `inconsistent_target_groups`;
that roster must be migrated before an empirical target-level claim.

The contract is implemented by `grid_scoring_v18.py` and `scoring.py`. The
synthetic fixture is `G2_SYNTHETIC_SCORE_V2.json`; it is not a weather result.
