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
