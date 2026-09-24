> **⚠️ PARTIALLY SUPERSEDED BY BATCH V4 (2026-09-23/24).** Under "Repairs made" below, the line
> "Legacy checkpoint-local outcome conflicts remain explicit in `inconsistent_target_groups` rather
> than being silently treated as a clean target-level roster" understates what V4 actually closed:
> conflicting rows are now excluded from every qualified/primary score field, not merely flagged
> while still contributing to them (see the superseded note atop `SCORER_CONTRACT_V2.md` in this
> same directory, and `plan/plan_v19_0923/v19_execution_20260923_v4/OPUS_REVIEW_OF_SONNET.md`).
> Test counts under "Validation" (148/34/25) are also a pre-V4, pre-V3-even snapshot; see
> `plan/plan_v19_0923/v19_execution_20260923_v4/TEST_RESULTS_V4.json` for current counts. Original
> text preserved unchanged below.

---

# DisasterTrace v18 review and repair status

Date: 2026-09-23
Worktree: `development/disastertrace-next`
Branch: `next-phase-v1`
Code base commit: `36082c42a93e11f67d274d8000c87cd1dc098d74`
Review identity: `v18-review-v2-20260923`

This is a repair review on an already dirty worktree. Existing source changes,
historical V1 artifacts and all closed API run identities were preserved. The
new files ending in `_V2` are the review outputs for the repaired contracts.

## Gate status

| Gate | Status | Evidence and boundary |
| --- | --- | --- |
| G0 baseline and access | BLOCKED_HEAD_DELTA_REVIEW | The declared v17 commit is unavailable locally; the current monitoring_v1 port remains the explicitly recorded implementation base. |
| G1 evidence qualification | COMPLETE_BOUNDED_SOURCE_ONLY | `G1_DEV_EPISODES_V2.json` and `G1_DEV_CENSUS_V2.json`: 24 episodes, 48 rows, January/March 2025, four stations. TAF statute-mile visibility is normalized to metre intervals and TEMPO/PROB windows retain their native semantics. |
| G2 complete-grid scoring | COMPLETE_SYNTHETIC_ADAPTER_ONLY | `G2_SYNTHETIC_SCORE_V2.json` and 32 v18 tests. Carry-forward is checkpoint ordered, checkpoint weights are normalized within each trajectory, and missing-Y completions are shared within a target when all checkpoints are unresolved. |
| G3 API contract | HARDENED_NO_NEW_RUN | The runner now requires HTTP 200, matching provider model identity, captures provider model/request ID and validates typed target state. No API request was issued during this review. |
| G3 intervention contract | COMPLETE_SYNTHETIC_ONLY | `G3_SYNTHETIC_INTERVENTIONS_V2.json` retains identity-repeat, duplicate, sham, withholding, delay and repair classifications. |
| G4 Natural Track | COMPLETE_SYNTHETIC_TYPED_KERNEL | `G4_NATURAL_SYNTHETIC_V2.json`: strict action fields, validated source roster and terminal expiry at the deadline. |

## Repairs made

- TAF `P6SM`/`SM` values are parsed through the canonical aviation interval
  parser and emitted as `visibility_m`; conditional windows, operators and
  native PROB30/40 values are retained.
- Grid materialization sorts by `(target_id, method, checkpoint_index)` and
  rejects duplicate or negative checkpoint indices in one trajectory. Pending
  outcomes default to `None`; non-binary and floating-point outcome values are
  rejected. Optional `checkpoint_weight` values are validated and normalized
  within each trajectory.
- Missing-Y bounds evaluate the two target-level completions jointly. Legacy
  checkpoint-local outcome conflicts remain explicit in
  `inconsistent_target_groups` rather than being silently treated as a clean
  target-level roster.
- API responses record requested/provider model identity and provider request
  ID, reject non-200 responses before parsing and reject malformed response
  envelopes safely.
- Natural actions reject unrelated fields; reaching or crossing the deadline
  creates a terminal expired state and cannot be followed by repeated WAITs.
- Evidence streams reject issued/available reordering, missing identities and
  same-time conflicting content; explicit duplicate/revision interventions
  carry their relation status.

## Scientific boundary

No mature outcome Y, quarantine holdout, protected February window or new
provider response was read. The G1 availability timestamp is a declared replay
lag, not prospective publication evidence. The synthetic score and Natural
Track artifacts validate accounting and state contracts only; they do not
support forecast gain, calibration, ranking or live-agent claims.

The closed G3 API runs remain unchanged and are not retried. A future provider
run requires a new manifest, run ID, model identity and complete denominator.

## Validation

The scoped monitoring regression passed 148 tests; the v18 suite passed 34
tests; the execution package passed 25 unit tests; and compileall passed. An
unscoped repository-wide pytest invocation is not a valid gate because the
repository intentionally contains many historical test copies and optional
dependency trees; details are recorded in `TEST_STATUS_V2.json`.
