# DisasterTrace v17 Execution Status

Version: v17-20260921

## Batch A: Problem and Data Qualification

Target: Reach G1 (data qualification gate)

| Task ID | Task Name | Status | Description | Dependencies |
|---------|-----------|--------|-------------|--------------|
| BA0 (V17-00) | Candidate Contract and Claim Preparation | **DONE** | Candidate contract, claim-evidence matrix, decision table, execution status skeleton | None |
| BA1 (V17-01) | Access Boundary and Input Identity | **DONE (A2-1 fix applied and tested)** | Allow-list paths, date guards, exposure registry code exists; entry-point enforcement and explicit-parameter-override gaps found in independent review (R08/A04) were fixed in A2-1 (fail-closed path/param consistency, shared `read_verified_allowed_file` entry point); `tests/test_revision_access_policy.py` passes | V17-00 |
| BA2 (V17-02) | Target, Lineage, and Outcome Policy | **DONE, with caveats (see A2-2)** | Source lineage, outcome resolution, validity/target separation (F01, F02, F10, F11 fixed); tie-resolution permutation-dependence (R05/A10) and ledger mutual-supersession (A11) found in independent review, addressed in A2-2 | V17-00, V17-01 |
| BA3 (V17-03) | Real Change Census and G1 | **DONE (implementation + A2-6 real re-census + A2-7 witness package), G1 status PENDING_INDEPENDENT_REVIEW — see A2-0/A2-3/A2-6/A2-7** | Transition census, label qualification produced; original G1 evidence-existence PASSED claim withdrawn per Batch A2 correction; corrected checkpoint-aware census (17,420 slots, 292 IN_EPISODE_CHANGE, 37 UNRESOLVED) and 30-item byte-traceable witness package completed 2026-09-21, awaiting independent human review (see Gate Status below) | V17-02 |
| BA4 (V17-04 partial) | Unified View and State Arms (interface only) | **NOT IN THIS BATCH** | View isolation, three-arm definition, synthetic tests only — planning template allowed optional parallel scheduling, but it was not authorized or executed in Batch A/A2; any future scheduling is a separate decision | V17-00, V17-01 |
| BA-V | Batch A Verification | PENDING | Standing test suite, integration check | BA1-BA3 (BA4 not in scope) |

## Task Details

### BA0 (V17-00) - DONE

**Deliverables created:**
- `PLAN/TASK_CONTRACT_v17.json` - 12-dimension candidate scientific contract
- `PLAN/CLAIM_EVIDENCE_MATRIX_v17.md` - C1-C5 claims with X0-X5 experiments
- `PLAN/DECISIONS_v17.yaml` - D01-D12 inheritance/refinement analysis
- `PLAN/EXECUTION_STATUS_v17.md` - This file

**Acceptance criteria verified:**
- AC1: Every claim maps to at least one experiment (verified in matrix)
- AC2: AMD/COR existence not conflated with probability-must-change (explicit in contract)
- AC3: Downloader/archival distinguished from living system (explicit in contract)
- AC4: Output contract has no internally conflicting fields (verified orthogonal operations)

### BA1 (V17-01) - DONE (A2-1 fix applied and tested)

**Scope:** Access boundary enforcement before real file discovery
**Files:** `scripts/build_episode_manifest_v16.py`, `scripts/build_lamp_categorical_registry_v16.py`, `src/disastertrace/revision_v1/outcome_wiring.py`, `src/disastertrace/revision_v1/access_policy.py`, `scripts/run_transition_census_v17.py`
**Tests:** Synthetic temporary directories, symlink/alias handling, date boundary guards, path/param consistency (`tests/test_revision_access_policy.py`)
**Addresses:** Codex F04, F07
**Status correction (Batch A2, 2026-09-21):** `AccessPolicy` class exists and its unit-level checks are real, but independent review found (a) explicit `as_of_us`/`year_month` parameters can override path-implied month restrictions (R08/A04/CE4, reproduced), and (b) the LAMP builder and some real entry points do not call the shared policy before glob/open. A2-1 fixed fail-closed parameter/path consistency and added the shared verified-read entry point `read_verified_allowed_file`; the real census entry point (`scripts/run_transition_census_v17.py`) now goes through it exclusively. Census-path enforcement (the A2-1 acceptance bar) is verified: 0 glob/open calls on rejected targets. Freeze/disclose/LAMP entry points were **not** brought into scope this batch — real freeze/disclose/LAMP registration remain explicitly forbidden this batch (hard boundary #10) and untouched beyond any incidental code paths exercised only synthetically.

### BA2 (V17-02) - DONE

**Scope:** Target and lineage semantics repair
**Files:** `src/disastertrace/revision_v1/contracts.py`, `manifest.py`, `ledger.py`, `episode_compiler.py`, `outcome_wiring.py`
**Tests:** Cross-window AMD, same-window different-source, mirror vs original publisher, late old version, CNL, same-minute conflict
**Addresses:** Codex F01, F02, F10, F11
**Commits:** 69c730e0c (V17-02: Fix four semantic bugs), 6889e2aa7 (V17-02 Gap remediation)

### BA3 (V17-03) - DONE (implementation + A2-6/A2-7); G1 decision WITHDRAWN, now PENDING_INDEPENDENT_REVIEW

**Scope:** Real change census using V17-01 allow-list (Y-blind by design)
**Deliverables:** `PLAN/TRANSITION_CENSUS_v17.md`, `PLAN/LABEL_QUALIFICATION_v17.md` (superseded by `TRANSITION_CENSUS_v17_A2.md`, `LABEL_QUALIFICATION_v17_A2.md`, both completed 2026-09-21 as part of A2-8), plus `BATCH_A2_ACCEPTANCE.md`
**Decision (WITHDRAWN 2026-09-21, Batch A2):** ~~Retain H15 - G1 evidence-existence gate PASSED~~ — withdrawn. Three independent reviews found the census classifies changes using `issued_at < target_start` only, never consuming the three checkpoint fields or `available_at`; the reported "0% dispute rate" reads a `tie_unresolved` field that `compile_ledger()` never emits; and the 4,264 "process groups" are station/issue-day groupings without an independence justification. See `TASK_CONTRACT_v17.json` `correction_history` and `open_risks.OR1a/OR1b/OR1c`.
**Commit:** f72373d40 (V17-03: Transition census for G1 data qualification) — implementation retained; conclusions drawn from it are what is withdrawn, not the code.
**Note:** A2-1 (entry-point fixes), A2-2 (tie/ledger/conflict propagation), and A2-3 (checkpoint-aware re-census) are complete. A2-6 ran one real 140-file re-census (140/140 file integrity, 17,420 slots, 292 IN_EPISODE_CHANGE, 37 UNRESOLVED — all 46 underlying change-level unresolved records trace to `bbb_contradicts_receipt_order`, confirming the A2-2 fix behaves correctly on real, not just synthetic, data). A2-7 built a 30-item byte-traceable witness package (26/26 change-level witnesses resolved to exact byte offsets) for independent review. G1 status is now `PENDING_INDEPENDENT_REVIEW`, not `PENDING_REVERIFICATION` — the instrument and one real run are both complete; what remains is a human reviewing the A2-7 witness package, not further code fixes. The Codex positive-label statistical-power concern is now OR1a and remains OPEN, requiring future Y-permissioned analysis; it is explicitly separate from, and must not block, the Y-free X3 drift diagnostics (see OR1_note_y_free_diagnostics_exception).

### BA4 (V17-04 partial) - NOT IN THIS BATCH

**Scope:** Interface and synthetic test portion of V17-04
**Files:** `src/disastertrace/revision_v1/p1_harness.py`, `belief_commit.py`
**Tests:** View isolation, three-arm verification, commit validation
**Addresses:** Codex F03, F08, F09
**Batch A2 clarification:** The original execution plan allowed BA4's pure-interface/synthetic-test portion to be scheduled optionally alongside Batch A, but it was never authorized or executed in Batch A or A2. This row previously appeared in the batch task table in a way that conflated "plannable in the future" with "in this batch's scope" — corrected here; BA4 is out of scope until explicitly scheduled in a future batch.

### BA-V - PENDING

**Scope:** Batch A integration verification
**Tests:** Standing test suite run, combined regression check

## Gate Status

| Gate | Description | Status | Evidence |
|------|-------------|--------|----------|
| G0 | Problem and scope | **CANDIDATE** | V17-00 through V17-03 provide a candidate contract; evidence-existence measurement itself is under reverification (A2), so "frozen" is downgraded to "candidate" pending A2-3 |
| G1 | Data qualification (evidence-existence) | **PENDING_INDEPENDENT_REVIEW** (was: PASSED — withdrawn 2026-09-21; was: PENDING_REVERIFICATION during A2-1..A2-5) | V17-03's original census reported 121,885 changes, ~98% coverage, 4,264 process groups, 0% TAF-side dispute rate, but three independent reviews found the underlying measurement did not consume checkpoint/`available_at` fields, the dispute-rate field was never emitted by the ledger, and process-group independence was unjustified. A2-1/A2-2/A2-3 fixed the measurement chain (tests pass). A2-6 completed one real, traceable 140-file re-census (140/140 file integrity; 17,420-slot full calendar; 292 IN_EPISODE_CHANGE, 37 UNRESOLVED — a genuine, non-zero dispute rate this time, all 46 underlying unresolved change-records tracing to `bbb_contradicts_receipt_order`). A2-7 built a 30-item byte-identity-traceable witness package (26/26 resolved) covering all 7 planned witness types. No independent human has reviewed the witness package yet, so G1 remains `PENDING_INDEPENDENT_REVIEW`, not PASSED — see `TRANSITION_CENSUS_v17_A2.md`, `LABEL_QUALIFICATION_v17_A2.md`, `BATCH_A2_ACCEPTANCE.md`, and `TASK_CONTRACT_v17.json` `correction_history`. |
| G2 | Measurement qualification | NOT STARTED | Requires Batch B |
| G3 | Development evidence | NOT STARTED | Requires V17-07 |
| G4 | Living capability | NOT STARTED | Requires V17-09 |
| G5 | Confirmation readiness | NOT STARTED | Requires V17-10 |

## Open Risks

1. **OR1a — Statistical power (REMAINS OPEN, Y-dependent)**: The Codex audit's concern about 8.33% positive-label rate (all 3 positives from a single KDEN event) is NOT addressed by the V17-03 census and cannot be addressed by any Y-blind census. A future outcome-side (Y-permissioned) analysis is required before H15 paired-diagnostic results depending on Y (C1/C4) can be trusted. See TASK_CONTRACT_v17.json `open_risks.OR1a_positive_label_distribution`.
2. **OR1b — Independent process count and pairing precision (REMAINS OPEN, Y-independent)**: Station/issue-day groupings are not established as independent weather processes; deferred to G3 (variance estimation) / G5 (confirmation precision). See `open_risks.OR1b_independent_process_and_pairing_precision`.
3. **OR1c — TAF source-label qualification (REMAINS OPEN, Y-independent)**: `LABEL_QUALIFICATION_v17.md`'s `PENDING_HUMAN_VERIFICATION` concerns TAF AMD/COR/lineage classification, not ASOS Y labels; a prior version of this document mis-cited it as outcome-label reliability. Independent human review pending (A2-7 witness package); no reviewer currently online, registered as `PENDING_INDEPENDENT_REVIEW`. See `open_risks.OR1c_taf_source_label_qualification`.
4. **Measurement-chain defects (Batch A2 in progress)**: tie-resolution permutation-dependence for equal-BBB records (R05/A10), ledger mutual-supersession under ambiguous same-instant AMDs (A11), dead `tie_unresolved` field read by census, checkpoint-unaware change classification (`issued_at < T` only), and access-policy explicit-parameter override of path-implied month restrictions (R08/A04). Being fixed in A2-1/A2-2/A2-3; see `BATCH_A2_PROGRESS.md`.
5. **LAMP completeness**: F06 shows truncated gzip streams; QL branch needed. QL blocks only LAMP-consuming paths (LAMP_categorical, LAMP_probabilistic), not non-LAMP baselines — see `TASK_CONTRACT_v17.json` C10 `blocked_by_note`.
6. **Ledger semantics (PARTIALLY RESOLVED by V17-02, residual gaps found in A2 review)**: F01 cross-window AMD handling fixed; equal-BBB ordering and same-instant mutual-supersession gaps remain (see item 4).
7. **Outcome ordering (RESOLVED by V17-02, scope-limited)**: F11 same-instant differing-observation input-order dependence fixed for the explicit-conflict case reviewed; semantic-duplicate folding (raw-text hash instead of parsed-semantics hash) remains a separate, unresolved gap (R11/R16).

## Next Steps

**Batch A (BA0-BA3 core implementation) is DONE. Batch A2 (A2-0 through A2-8) is DONE.** G1's
original PASSED conclusion remains WITHDRAWN; the corrected status after A2 completion is
`PENDING_INDEPENDENT_REVIEW` (instrument closed, one real traceable run done, no human review
yet — see Gate Status above). Do not restart BA0-BA3 or A2-0..A2-8 implementation. Current
next steps:

1. A2-0 through A2-8: all complete — see `BATCH_A2_PROGRESS.md` and `BATCH_A2_ACCEPTANCE.md`
   for the full task-by-task record.
2. Immediate next step: independent human review of the 30-item A2-7 witness package
   (`artifacts_v17/ba2_20260921T202507Z/witness_v1/witnesses.jsonl`) — this is what would move
   G1 from PENDING_INDEPENDENT_REVIEW to a genuine PASSED/FAILED determination.
3. BA4 (V17-04 partial) remains NOT IN THIS BATCH; do not schedule until a future batch
   explicitly authorizes it.
4. BA-V (Batch A verification) is satisfied by A2-8's regression pass (274 passed directed /
   731 passed full regression, 0 failed, 0 skipped); no separate restart needed.
5. See `BATCH_A2_ACCEPTANCE.md` §8/§9 for the full list of items still requiring independent
   verification, real data, or later experiments, and explicitly out-of-scope items.

---

*Last updated: 2026-09-21T21:00:06Z (Batch A2 completion — A2-8 reconciliation pass)*
*This file will be updated by subsequent batch tasks*
