# Batch A2 Progress Log

This file is the task-boundary progress record required by `disastertrace-starter/AGENTS.md`
("Record actual commands, exit codes, results, blockers, and the next executable task
in IMPLEMENTATION_STATUS.md at every task boundary") for Batch A2, per
`plan/plan_v17_0922/DISASTERTRACE_V17_BATCH_A2_10H_PLAN_CN.md`. `IMPLEMENTATION_STATUS.md`
carries a pointer to this file rather than the full log.

Executor identity: this batch is executed directly by the parent Claude Code session
(model: Claude Sonnet 5, `claude-sonnet-5`), not delegated to a subagent. Per the user's
Batch A2 hard constraints ("不启动额外 agent"), no `fableplan:complex-executor` /
`simple-executor` subagent was spawned for this batch, even though
`EXECUTION-ROUTING.md` would otherwise route implementation work to those agents. This
plan itself was produced in plan mode (Fable 5.1); execution after `ExitPlanMode` runs
as Sonnet 5. This is disclosed here and will be restated in the final 9-item report.

## Baseline (A2-0)

- UTC start: 2026-09-21T17:08:26Z
- Repo root (git): `/mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/repo`
- Code root: `repo/disastertrace-starter`
- HEAD: `daba7cf3f1b53b5b6d8c8d376773c2b9d43d9644` (branch `v17-batch-a-v1`) — matches the plan document's reference commit; tracked working tree clean at baseline.
- Untracked at baseline: 3 independent-review `.zip` files and `plan/plan_v17_0921/chatgpt_review_v17_batch_a/` (review-brief material, not code) — left untouched, not treated as in-progress code work.
- Python: 3.10.12 (venv at `/mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/.venv/bin/python`, i.e. `$CODE/../../.venv/bin/python`).
- A2's six-file targeted test set (`tests/test_revision_access_policy.py tests/test_revision_receipt_order.py tests/test_revision_ledger.py tests/test_revision_manifest.py tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py`), collect-only: **223 tests collected**, 0 errors.

## A2-0: Baseline and claim correction — DONE (document-only, no code changes)

Files edited (all in `plan/plan_v17_0921/`):

1. **`TASK_CONTRACT_v17.json`**
   - `g1_gate_status`: `"PASSED - proceed with H15 as scoped"` → `"PENDING_REVERIFICATION"`; added `g1_reverification_note` and `correction_history[]` (two entries: the original V17-03 post-hoc self-correction at commit `daba7cf3f`, and this Batch A2 correction). Both entries preserve the original withdrawn claim text verbatim, per the plan's "保留原文 + 撤回原因" requirement.
   - `C01_primary_domain`: `status: frozen_dev` → `candidate`; 3 `open_details` items added (per-checkpoint availability via A2-3, conflict-status wiring via A2-2, independence justification via A2-3); original 3 `resolved_details` bullets renamed to `withdrawn_details`, each prefixed `-- WITHDRAWN:` with a specific reason; `owner`/`closing_evidence` updated; `blocked_by: []` → `["A2-1", "A2-2", "A2-3"]`.
   - `C04_scoring_time`: same pattern — `frozen_dev` → `candidate`; `withdrawn_details` on the T-60/checkpoint-feasibility/17,064-slots claims; `blocked_by: []` → `["A2-3"]`.
   - `C10_professional_forecast_baseline`: added `blocked_by_note` clarifying QL only blocks LAMP-consuming paths (LAMP_categorical, LAMP_probabilistic), not non-LAMP baselines (FOLLOW/values_bank); `blocked_by` array itself unchanged.
   - `open_risks.OR1_positive_label_statistical_power` (single entry) split into three: `OR1a_positive_label_distribution` (Y-dependent; does NOT block C3/X3 Y-free diagnostics), `OR1b_independent_process_and_pairing_precision` (Y-independent; deferred to G3/G5), `OR1c_taf_source_label_qualification` (Y-independent; TAF AMD/COR source-label review via A2-7 witness package, distinct from ASOS Y-label reliability), plus `OR1_note_y_free_diagnostics_exception` clarifying the exception explicitly.

2. **`CLAIM_EVIDENCE_MATRIX_v17.md`**
   - "Statistical Power Concern" section rewritten to name the four previously-conflated variables (Y=1, checkpoint-visible source-evidence change, model factual/state error, forecast-loss improvement) and state that a Y-blind census can speak only to the second.
   - "Statistical Power Risk Matrix" table: C1 row split into a Y-independent column (evidence-change coverage, census-measurable) and a Y-dependent column (OR1a positive-label distribution, not census-measurable), replacing the single "HIGH - 8.33% positive rate" label; C4 row annotated similarly.
   - "Open Questions for V17-03 Census" split into a Y-blind section (items 1-4, answerable this batch) and a new "Open Questions Requiring Future Y Access" section (item 5, the positive-rate-sufficiency question, explicitly deferred).
   - C1 row in "Claim-Experiment Bidirectional Mapping" updated to require per-checkpoint visible-exposure counting (not merely pre-target-start issuance) and to flag OR1a as a separate, deferred requirement.

3. **`EXECUTION_STATUS_v17.md`**
   - Batch A task table: BA1 → `IMPLEMENTED / qualification PENDING (A2-1)`; BA2 → `DONE, with caveats (see A2-2)`; BA3 → `DONE (implementation), G1 status WITHDRAWN`; BA4 → `NOT IN THIS BATCH` (was previously listed as a batch task with status PENDING, which conflated "plannable" with "in-scope"); BA-V dependency narrowed to BA1-BA3.
   - Task Details sections for BA1, BA3, BA4 rewritten with status-correction notes explaining what independent review found and why the prior claim is withdrawn or narrowed (not deleted — original commit references and scope are retained).
   - Gate Status table: G0 `FROZEN_DEV` → `CANDIDATE`; G1 `PASSED` → `PENDING_REVERIFICATION`, with the specific measurement gaps named (checkpoint/`available_at` not consumed, dead `tie_unresolved` field, unjustified process-group independence).
   - Open Risks: expanded from 4 items to 7, incorporating OR1a/OR1b/OR1c, the measurement-chain defects found by the three independent reviews (tie-resolution permutation dependence, ledger mutual-supersession, access-policy parameter override), and narrowing the F11 "RESOLVED" claim to same-instant differing-observation cases only (semantic-duplicate folding via raw-text hash remains a separate open gap).
   - Next Steps: rewritten to point at A2-0 through A2-8 instead of re-listing BA1-BA4 as if nothing had been implemented; explicit instruction not to restart BA0-BA3 implementation.

4. **Independent-verification dependency registered**: `TASK_CONTRACT_v17.json` `OR1c_taf_source_label_qualification.owner` = "Independent reviewer (not currently online; dependency registered in Batch A2)"; status `PENDING_INDEPENDENT_REVIEW`. No human reviewer is online during this batch; A2-7 will prepare the witness package but cannot itself resolve this dependency.

**A2-0 acceptance check**: no status table in the three edited files now claims a future task as already complete; every narrowed/withdrawn claim retains the original text plus a reason (no silent deletion); unresolved verification items are named explicitly (OR1a/OR1b/OR1c, PENDING_INDEPENDENT_REVIEW, PENDING_REVERIFICATION). Old `TRANSITION_CENSUS_v17.md` / `LABEL_QUALIFICATION_v17.md` were left untouched at this step (A2-8 will add A2-versioned successors and a top-of-file pointer, per the plan; not done in A2-0 to avoid conflating the correction-pass step with the re-census step).

**No source code was modified in A2-0.** All four edited files are in `plan/plan_v17_0921/`.

## A2-1: Real access entry point and input readset — DONE

Files edited:

1. **`src/disastertrace/revision_v1/access_policy.py`**
   - `assert_allowed`: now always attempts to extract a path-implied year-month
     (step 4, unconditional — previously only attempted when both explicit
     params were absent). Any explicit `as_of_us`/`year_month` that disagrees
     with the path-implied month is now rejected fail-closed (step 5) — this
     closes CE4 (explicit "safe" parameter overriding a differently-monthed
     path). `_check_holdout_window` now runs the `as_of_us` and `year_month`
     checks independently (`if`/`if`, not `if`/`elif`). When the year-month
     allowlist is configured but the path's own month cannot be extracted,
     access is now rejected fail-closed rather than silently admitted.
   - New shared entry point `read_verified_allowed_file(policy, body_path,
     receipt_path, *, year_month=None) -> VerifiedInput`: runs
     `assert_allowed` on both body and receipt paths BEFORE any open/read;
     then reads the receipt JSON, reads the body bytes, recomputes SHA256,
     and raises `ReadVerificationError` (distinct from `AccessPolicyViolation`)
     on a hash mismatch. Returns a `VerifiedInput` carrying the body bytes,
     canonical paths, size, and both hashes, so callers never need a second
     read.
   - New `VerifiedInput` frozen dataclass with `.readset_record()`.
   - (This file's edits were made and regression-tested in the session
     immediately prior to this one; re-confirmed unchanged this session via a
     full re-read before continuing.)

2. **`scripts/run_transition_census_v17.py`**
   - Added `ALLOWED_YEAR_MONTHS` (frozenset of the 35 dashed `YYYY-MM` values
     derived from the existing `YEAR_MONTHS` constant — the explicit
     real-census allowlist; never widened beyond the 140-file set).
   - `verify_140_files(bulk_dir, policy)`: signature changed to take an
     `AccessPolicy`. Every real (body, receipt) pair is now verified through
     `read_verified_allowed_file()` — no direct `open()`/`sha256_file()` call
     on real archive content remains in this function. `.exists()` checks
     (stat only, not read) still bucket a genuinely absent file into
     `missing`; an existing-but-policy-rejected or hash-mismatched file is
     bucketed into `mismatches` with a `access_policy_violation` /
     `read_verification_error` reason, keeping the two outcomes distinct.
   - New `VerifiedTafFile` dataclass carries the already-read body text/hash
     out of `verify_140_files`, so `run_census` Step 2 no longer re-opens the
     files: `compile_afos_taf_stream` is now called directly on
     `vf.raw_text`.
   - `EvidenceChange.original_text_sha256` (previously mis-populated with a
     semantic hash under a raw-text-sounding name) split into two documented
     fields: `raw_text_sha256` (file-level hash of the verified source file,
     shared by every package parsed from that file) and
     `native_semantics_sha256` (the pre-existing per-package parsed-semantics
     hash, unchanged). Each compiled package is tagged with an internal
     `_source_raw_text_sha256` key so `classify_changes_for_slot` can recover
     the file-level hash without changing `compile_afos_taf_stream`'s or
     `compile_ledger`'s contracts (confirmed via grep that `compile_ledger`
     only reads specific known dict keys via `.get()`).
   - `run_census` now writes `input_readset.jsonl` (one record per verified
     file: station, year_month, canonical body/receipt paths, size, both
     hashes) and `input_fingerprint.json` (a stable-order SHA256 digest over
     the exact readset sequence, with the digest method documented inline),
     inside the existing `if artifacts_dir:` block, alongside the pre-existing
     `all_changes.jsonl`/`process_groups.json`/`slot_summary.jsonl` writers.
     `CensusResult`'s shape and `main()`'s call signature are unchanged.
   - **Deliberately NOT touched this task** (out of A2-1 scope, reserved for
     A2-2/A2-3): the `if pkg["issued_at"] >= slot.validity_start_us: continue`
     checkpoint-blind filter (CE3), the dead `if entry.get("tie_unresolved"):`
     branch, and the three `supersedes[0] if supersedes else None` sites.

3. **`tests/test_transition_census_v17.py`**
   - `test_verify_140_boundary_check` updated for the new
     `verify_140_files(bulk_dir, policy)` signature (constructs a minimal
     `AccessPolicy`; the quarantine_holdout check fires before policy is ever
     consulted, so any validly-constructed policy works here).
   - 5 `EvidenceChange(...)` construction sites (in
     `TestProcessGroupingRule`) updated from `original_text_sha256="hashN"`
     to `raw_text_sha256="hashN", native_semantics_sha256="hashN"` (mechanical
     rename, applied via `sed`, confirmed via grep to not touch the unrelated
     package-dict-field `native_semantics_sha256` references used by
     `TestChangeClassification.make_product`).
   - New `TestVerify140FilesAccessPolicyIntegration` class (3 tests), added
     per the plan's explicit A2-1 acceptance requirement ("通过真实 census
     入口（合成 bulk dir）断言被拒绝目标的 `glob/open` 计数为 0；只测 helper
     抛错不够"):
     - `test_rejected_target_is_never_opened`: synthetic bulk_dir with one
       real body/receipt pair, `AccessPolicy.allowed_root` deliberately does
       not contain bulk_dir (root-escape). Patches `builtins.open` to record
       every call. Asserts the file lands in `mismatches` with an
       `access_policy_violation` reason AND that `open()` was never called —
       i.e., rejection happens strictly before any read, through the real
       `verify_140_files` entry point, not just the `access_policy.py` unit
       tests in isolation.
     - `test_verifies_real_pair_and_carries_bytes`: positive path — a
       correctly-allowed pair verified through a real, permissive policy
       comes back as a `VerifiedTafFile` with the exact body text and correct
       `raw_text_sha256`.
     - `test_tampered_body_is_rejected_as_mismatch_not_missing`: a body
       modified after its receipt was written is rejected with
       `read_verification_error` (not silently dropped as `missing`),
       through the real entry point.

**Commands run and results (this task boundary):**

```
cd /mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/repo/disastertrace-starter
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py \
  tests/test_revision_ledger.py tests/test_revision_manifest.py \
  tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py
```
Result: **235 passed, 0 failed, 0 skipped**, exit code 0. (Baseline after the
prior session's `access_policy.py` work was 232 passed; the 3 new
`TestVerify140FilesAccessPolicyIntegration` tests account for the delta.
Before that: 223 collected at the A2-0 baseline, pre-`access_policy.py`
edits.)

Also ran, before the test edits, a standalone import smoke check:
`python -c "import run_transition_census_v17"`-equivalent (module-level
import of the rewritten script) — confirmed no syntax errors and that
`ALLOWED_YEAR_MONTHS` is a 35-entry frozenset of dashed year-months (e.g.
`2023-08`, `2024-04`, `2025-01`), i.e. 2025-02 correctly absent.

**A2-1 acceptance check**: real census entry point (`verify_140_files`) now
routes 100% of real-archive reads through `read_verified_allowed_file`; a
rejected target is verified (via `test_rejected_target_is_never_opened`) to
incur zero `open()` calls, not just a helper-level exception in isolation;
a tampered body is rejected as a distinct `read_verification_error` outcome
through the same real entry point; input readset + fingerprint artifacts are
written and are reproducible (stable digest method documented in the JSON
itself). Freeze/disclose/LAMP fingerprint work (`build_episode_manifest_v16.py`)
was **not touched this task** — explicitly deferred, to be recorded as
NOT EXECUTED THIS BATCH in the final `BATCH_A2_ACCEPTANCE.md` (A2-8) rather
than silently dropped.

**Not yet done for A2-1**: no additional permutation/symlink-specific tests
beyond the 3 added were written (time-boxed within the 90-minute budget);
the existing `test_revision_access_policy.py` suite from the prior session
already covers permutation-invariance and root-escape/symlink cases at the
`access_policy.py` unit level, so this was judged sufficient combined with
the new census-level integration tests above.

## A2-2: tie / ledger / conflict propagation (CE1, CE2) — DONE

Files edited:

1. **`src/disastertrace/revision_v1/tie_resolution.py`** (CE1 fix)
   - `check_bbb_order_vs_receipt_order`: within a same-family pairwise
     comparison, added an early `if bbb_i == bbb_j: return False,
     "equal_bbb_no_authority"` before computing `seq_order`. Previously,
     equal-BBB pairs made `bbb_order` trivially `False` while `seq_order`
     depended on which member landed at index `i` vs `j` in the caller's
     input list, so the pairwise comparison's result flipped depending on
     input permutation (CE1: `[A,B]` → resolved winner B, `[B,A]` →
     unresolved `bbb_contradicts_receipt_order`, for the same tied set).
   - `resolve_receipt_tie_strict`: added a stable sort of `tied_rows` by
     `source_id` before any gate runs, as defense-in-depth against future
     gates re-introducing an order dependency.

2. **`src/disastertrace/revision_v1/ledger.py`** (CE2 fix)
   - Added `_resolve_amendment_predecessors(product, prior_in_group)` and
     `_apply_amendment_resolution(product, prior_in_group, amendment_kind,
     extra_fields)`. The AMD/COR/baseline-override call sites (previously a
     blind `latest, _ = latest_issuance(prior_in_group); supersedes =
     [p["source_id"] for p in latest]`) now route through these helpers.
     When the "latest" prior candidates are strictly earlier than the
     product being classified, the old direct-assignment behavior is
     preserved unchanged (`relation_status="resolved",
     relation_reason="strictly_prior"`). Only when candidates share the
     product's own `issued_at` (an ambiguous same-instant tie) does the new
     path call `resolve_receipt_tie_strict` on the full tied set instead of
     assuming the product wins; an unresolved tie now yields
     `supersedes=None`, `superseded_by=None`,
     `version_relationship="concurrent"`, `relation_status="unresolved"` on
     **both** sides of the tie — closing CE2 (previously produced mutual
     `A supersedes [B]` / `B supersedes [A]` cycles for same-instant,
     non-comparable AMD/COR pairs).
   - `compile_ledger` entries gained three new fields: `relation_status`
     (`resolved` / `unresolved` / `not_applicable`), `relation_reason`, and
     `candidate_predecessors` (list, always populated when candidates were
     considered, independent of whether a direction was assigned).
   - Module docstring and `compile_ledger` docstring updated to document
     the three new fields.

3. **`scripts/validate_dl3r_semantics.py`** (reason-propagation fix)
   - `check_latest_issuance_uniqueness`'s Step 2/Step 3 conflict-reporting
     blocks now call the already-imported shared functions
     (`_shared_check_receipt_premise`, `_shared_check_bbb_order_vs_receipt_order`)
     directly and use their real `(ok, reason)` tuples, instead of
     re-deriving a coarse reason via a `has_any_seq` heuristic (which
     collapsed `premise_violated_duplicate_seq` /
     `premise_violated_stream_mismatch` / `premise_violated_issued_at_order`
     into a generic `"premise_violated"`) or hardcoding
     `"bbb_contradicts_receipt_order"` (which would have mislabeled the new
     `"equal_bbb_no_authority"` case from the CE1 fix). The bool-only
     wrapper functions `_check_bbb_order_vs_receipt_order` /
     `_check_receipt_premise` were left unchanged — they are directly
     imported and asserted on (`is True`/`is False`) by 11 existing test
     assertions in `tests/test_validate_dl3r_semantics.py`, so their
     signatures could not change; only the call site inside
     `check_latest_issuance_uniqueness` was fixed to stop discarding the
     real reason.

Tests added/revised:

4. **`tests/test_validate_dl3r_semantics.py`**
   - `test_stream_mismatch_stays_conflict`: assertion tightened from
     `conflicts[0]["reason"] in ("no_receipt_signal", "premise_violated")`
     to the exact `conflicts[0]["reason"] == "premise_violated_stream_mismatch"`,
     reflecting the reason-propagation fix (expected, predicted failure —
     confirmed before editing, then confirmed fixed after).
   - New `test_equal_bbb_stays_conflict_with_precise_reason` and
     `test_equal_bbb_conflict_is_permutation_invariant`: verify the new
     `"equal_bbb_no_authority"` reason (introduced by the CE1 fix) reaches
     the validator's conflict report unmodified, and that the result is
     identical regardless of input order.

5. **`tests/test_revision_receipt_order.py`**
   - New `TestEqualBbbPermutationInvariance` class (4 tests): pins that
     `check_bbb_order_vs_receipt_order` and `resolve_receipt_tie_strict`
     give the identical `(resolved, reason)` outcome across every
     permutation of a 2-member and a 3-member equal-BBB tied set (CE1's
     original counterexample), plus a sanity check that the existing
     distinct-BBB resolved path is undisturbed under permutation.

6. **`tests/test_revision_ledger.py`**
   - `test_tied_pair_without_seqs_keeps_legacy_entries`: previously only
     asserted "no crash, kind is not None" (deliberately not asserting a
     shape, per its own docstring, since the legacy path was known-buggy).
     Actual behavior was captured by running `compile_ledger` directly on
     the fixture before editing the test (not guessed): both `entry_a` and
     `entry_b` now come back `relation_status="unresolved"`,
     `relation_reason="no_receipt_signal"`,
     `version_relationship="concurrent"`, `supersedes=None` on both sides,
     `candidate_predecessors` populated with each other's source_id. The
     test now asserts this directly, plus the explicit acyclicity check
     (`"ksfo-legacy-b" not in a_supersedes` and vice versa), with a comment
     documenting the old CE2 defect (this exact fixture used to produce a
     genuine mutual A↔B supersede cycle) as a preserved negative example.
   - `test_stream_mismatch_keeps_legacy_visibility`: same treatment for the
     second latent-CE2-vulnerable case (mismatched `receipt_stream`, not
     missing `receipt_seq`). Actual output confirmed via direct
     `compile_ledger` run first: `relation_reason="premise_violated_stream_mismatch"`,
     same unresolved/concurrent/no-mutual-supersede shape.

**Commands run and results (this task boundary):**

```
cd /mnt/afs/260010168/extreme_weather_benchmark/development/v14_revision_20260919_01/repo/disastertrace-starter
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider tests/test_validate_dl3r_semantics.py
```
Result: **51 passed**, exit code 0 (was 49 passed / 48 passed 1 failed mid-fix; +2 new equal-BBB tests).

```
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider tests/test_revision_receipt_order.py
```
Result: **40 passed**, exit code 0 (was 36; +4 new permutation-invariance tests).

```
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider tests/test_revision_ledger.py
```
Result: **48 passed**, exit code 0 (same count as before — the two revised tests gained assertions, not new test functions).

```
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py \
  tests/test_revision_ledger.py tests/test_revision_manifest.py \
  tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py
```
Result: **241 passed, 0 failed, 0 skipped**, exit code 0 (A2-1 baseline was 235; +6 = the
2 validator + 4 receipt-order additions above; the 2 ledger-test revisions added
assertions to existing tests rather than new test functions).

```
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_monitoring_admission*.py tests/test_monitoring_taf_tasks*.py tests/test_monitoring_aviation*.py
```
Result: **56 passed**, exit code 0 — exactly matches the historical baseline count; no
regression in `versions.py`'s monitoring consumers from the CE1/CE2 fixes.

**A2-2 acceptance check** (per plan §A2-2 验收):
- CE1 全排列不变: confirmed via `TestEqualBbbPermutationInvariance` (2-member and
  3-member equal-BBB sets, all `itertools.permutations` give identical
  `(resolved, reason)`) and via the validator-level
  `test_equal_bbb_conflict_is_permutation_invariant`.
- CE2 输出 concurrent/unresolved 无互相 supersede: confirmed via the revised
  `test_tied_pair_without_seqs_keeps_legacy_entries` and
  `test_stream_mismatch_keeps_legacy_visibility`, both asserting
  `relation_status="unresolved"`, `version_relationship="concurrent"`,
  `supersedes is None` on both sides, and the explicit no-mutual-edge check —
  against actual `compile_ledger` output captured by direct execution before
  writing the assertions (not invented).
- 合成冲突使汇总 unresolved 计数 > 0: **not done at the census-summary level in
  A2-2** — the underlying ledger-level `relation_status="unresolved"` field
  now exists and is exercised by the two tests above, but wiring it into a
  census-level `n_targets_with_unresolved` aggregate is A2-3 scope (the plan
  places the checkpoint-aware census summary rewrite, including consumption of
  the (currently dead) `tie_unresolved`-style field, in A2-3, not A2-2).
  Recorded here explicitly rather than silently deferred.
- monitoring 三件套无回归: confirmed, 56/56, exact match to historical baseline.

**Not claimed**: no real-data verification occurred in A2-2 — all fixtures above
are synthetic, constructed and run directly against `compile_ledger` /
`resolve_receipt_tie_strict` / `check_latest_issuance_uniqueness` in this
process, not through the real census entry point or real archive files (that is
A2-6 scope, gated on A2-1/2/3/5 passing per the plan). No human review occurred.
No live model API calls occurred (none were in scope for A2-2).

## A2-3: Checkpoint-aware census, count units, full-calendar denominator — DONE (synthetic-only)

Files edited:

1. **`scripts/run_transition_census_v17.py`** (rewritten in an earlier session within this
   batch, prior to this progress entry) — replaced the checkpoint-blind
   `if pkg["issued_at"] >= slot.validity_start_us: continue` filter (CE3) with a
   per-station `compile_ledger` (whole allowed stream, prefix-stable) plus three
   `visible_at(ledger, cutoff=...)` views at `checkpoint_t60_us` / `_t40_us` / `_t20_us`.
   Evidence is classified by *availability* (`available_at`, `availability_basis`), never
   by comparing `issued_at` to the target's validity start. Added: `EvidenceChange`,
   `CandidateSlot`, `ExclusionRecord`, `CensusResult` dataclasses; `checkpoint_classification`
   enum (`AVAIL_INITIAL_PREFIX` / `AVAIL_INTERVAL_1` / `AVAIL_INTERVAL_2` /
   `AVAIL_AFTER_LAST_SCORE` / `AVAIL_UNKNOWN`); two relevance tiers
   (`TIER_STRICT_OVERLAP` / `TIER_ADJACENT_CONTEXT`); five mutually-exclusive slot
   statuses (`STATUS_NO_INPUT` / `STATUS_NO_APPLICABLE_EVIDENCE` /
   `STATUS_INITIAL_ONLY_NO_CHANGE` / `STATUS_IN_EPISODE_CHANGE` / `STATUS_UNRESOLVED`) plus
   a `flags` list (`prefix_coverage_insufficient`, `adjacent_only`, ...); a separate
   `ExclusionRecord` ledger for protected-window/disallowed-month slots (previously these
   were silently dropped by the calendar generator); `generate_continuous_calendar_slots`
   now returns `(slots, exclusions)` instead of `slots` alone; fixed sampling identity
   `SAMPLING_NAME = "四时次日历采样"` (4 stations × 35 allowed months × 00/06/12/18,
   1h target support) recorded as a module constant, not implicit in code shape.

2. **`tests/test_transition_census_v17.py`** — two kinds of edits:
   - Structural reconciliation with the rewritten script (5 fixes): replaced
     `test_census_does_not_import_asos_symbols`'s dead `pass`-only loop body with a real
     AST-based check (every non-blank ASOS/METAR-pattern occurrence in the script source
     must be inside a docstring, a `#` comment, or a line containing MUST NOT/DO NOT/NEVER
     — never executable code); renamed 5 `predecessor_source_id="pN"` (singular string)
     call sites to `predecessor_source_ids=["pN"]` (plural list) across
     `test_process_grouping_is_deterministic` and `test_process_grouping_splits_different_days`;
     updated both `TestCalendarSlotGeneration` tests to unpack the new
     `(slots, exclusions)` tuple, adding assertions that expected slots produce
     `exclusions == []` and that excluded slots are recorded with `reason == "protected_window"`
     rather than silently dropped.
   - New coverage (`TestCheckpointAwareCensus`, 8 test methods, plus a shared `_a2_3_pkg`
     synthetic-fixture helper), calling `classify_changes_for_slot` / `_compute_slot_status`
     directly (never through file I/O — no archive files, real or synthetic-on-disk, are
     touched by this class), covering every scenario the plan's A2-3 section enumerates:
     `test_lone_t10_amd_excluded_from_scoring` (the literal CE3 counterexample — a lone AMD
     issued at T-10 must classify `AVAIL_AFTER_LAST_SCORE` and the slot must land on
     `STATUS_INITIAL_ONLY_NO_CHANGE`, not count as an in-episode change);
     `test_t40_t20_exact_boundary_is_inclusive` (evidence available at exactly `t40`/`t20`
     lands in that checkpoint's view, confirming `visible_at`'s inclusive `<=`);
     `test_legally_issued_but_late_available_is_excluded` (issued 50 min early but
     `verified_publication` delays real availability past `t20` — availability, not issuance
     time, governs); `test_initial_only_no_change`; `test_adjacent_only_is_no_applicable_evidence`
     (zero-width-touching validity window is adjacent context, not strict overlap);
     `test_prefix_coverage_insufficient_flag` (station's earliest available evidence must be
     safely — within `PREFIX_LOOKBACK_MARGIN_US` — before `t60`, else a no-change verdict is
     flagged as untrustworthy rather than asserted as genuine absence of prior evidence);
     `test_missing_input_vs_no_applicable_evidence` (station with zero packages vs. a station
     with packages irrelevant to this particular slot are kept distinguishable);
     `test_one_source_multi_target_counts_reconcile` (a single wide-validity AMD relevant to
     two target slots: identity counts `n_unique_sources` / `n_unique_relation_edges` dedupe
     across targets to 1 each, while the per-target association count correctly increments to
     2 — demonstrating both "一源多目标不增殖" and per-slot-detail-sums-to-aggregate
     reconciliation in one fixture, since they share the same construction).

   All expected values in the new tests were hand-derived from `ledger.py`'s documented
   contracts (`DEFAULT_DECLARED_LAG_US = 120_000_000`; `available_at = issued_at +
   declared_lag_us` absent `verified_publication`/`collector_first_seen` overrides;
   `visible_at`'s inclusive `<=` cutoff) before running pytest — not by executing the script
   and copying its output into assertions.

### Commands run

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py \
  tests/test_revision_ledger.py tests/test_revision_manifest.py \
  tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py
```
Result: **249 passed**, exit code 0, 0 failed, 0 skipped. (Prior to the A2-3 script rewrite
and test-file update, this same targeted set stood at 241 passed; the +8 delta is exactly
the 8 new `TestCheckpointAwareCensus` methods — no other test count changed.) This was the
first real execution of the rewritten `classify_changes_for_slot` / `_compute_slot_status` /
`generate_continuous_calendar_slots` against the new hand-derived expectations, and it
passed on the first run with no script or test corrections needed — the hand arithmetic in
section "problem solving" (t40/t20 boundary values, the T-10-after-t20 computation, the
verified_publication override, the dual-slot multi-target availability windows) matched the
script's actual behavior exactly.

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_monitoring_admission*.py tests/test_monitoring_taf_tasks*.py tests/test_monitoring_aviation*.py
```
Result: **56 passed**, exit code 0 — exact match to the historical baseline; `ledger.py`'s
A2-3 changes (none, in fact — A2-3 touched only the census script and its own test file, not
`ledger.py`/`versions.py` again) introduced no monitoring regression.

**A2-3 acceptance check** (per plan §A2-3 验收):
- CE3 的 T−10 AMD 归 AFTER_LAST_SCORE、不计 in-episode: confirmed directly by
  `test_lone_t10_amd_excluded_from_scoring` — `checkpoint_classification ==
  AVAIL_AFTER_LAST_SCORE`, `_compute_slot_status(...) == STATUS_INITIAL_ONLY_NO_CHANGE`, and
  an explicit filter reproducing the "episode-eligible changes" definition returns empty.
- 所有 slot 输出且对账: confirmed at unit-fixture granularity by
  `test_one_source_multi_target_counts_reconcile`'s final assertion
  (`len(changes1) + len(changes2) == len(all_changes)`, i.e. no per-slot detail record is
  dropped or duplicated when summed into the aggregate). **Not yet confirmed at the full
  `run_census(...)` / `CensusResult` aggregate-summary level** — no test in this batch calls
  `run_census` end-to-end; that is explicitly A2-5 (synthetic end-to-end integration test)
  and A2-6 (real smoke + at most one full 140-file run) scope, both still pending.

**Not claimed**: no real-data verification occurred in A2-3 — every `TestCheckpointAwareCensus`
fixture is constructed in-process via `_a2_3_pkg`/`CandidateSlot`/`EvidenceChange`, never
read from disk, real or synthetic. `run_census`, `verify_140_files`, and the full calendar
generator against the real 140-file allowed set have not been exercised this task. No human
review occurred. No live model API calls occurred (none were in scope for A2-3). Per hard
boundary #9, no real archive files have been touched in this batch so far — everything above
is synthetic-directory / in-memory-fixture verification only.

## A2-4: Minimal outcome-contract enforcement — DONE (synthetic-only)

**Files edited**:
- `src/disastertrace/revision_v1/manifest.py`: added `H15_DEFAULT_PROFILE` (= the existing
  `DEFAULT_OUTCOME_CONTRACT` object, same values, named separately as the explicit
  single-supported-profile target); `UnsupportedOutcomeProfile(ValueError)`;
  `validate_outcome_profile(contract)` (checks all 5 required fields present AND each
  value exactly equals `H15_DEFAULT_PROFILE`'s); `compute_checkpoints(validity_start_us, *,
  profile=None)` now derives offsets/weights from a profile dict instead of the hardcoded
  `CHECKPOINT_OFFSETS_MINUTES`/weight=1.0 (default `profile=None` -> `H15_DEFAULT_PROFILE`,
  whose values equal the old hardcoded ones, so existing callers are unaffected);
  `build_manifest` now runs `_validate_checkpoint_weights` FIRST (preserves
  `test_empty_weights_raises`'s exact "cannot be empty" message for contracts missing
  `checkpoint_offsets_minutes` too), THEN `validate_outcome_profile(outcome_contract)`, then
  threads `profile=outcome_contract` into the per-target `compute_checkpoints` call, and adds
  four new ADDITIVE target-entry fields: `source_validity_start_us`/`source_validity_end_us`
  (identical to the existing `validity_start_us`/`validity_end_us`, the TAF-side window) and
  `target_support_start_us`/`target_support_end_us` (the H15 scoring window, derived from
  `outcome_contract["support_window_hours"]`, currently starting at the same instant as
  source_validity but conceptually distinct). No existing field was renamed or removed.
- `src/disastertrace/revision_v1/outcome_wiring.py`: `make_h15_visibility_target` gained two
  optional kwargs, `allowed_thresholds: frozenset[float] | None = None` (default
  `FROZEN_THRESHOLDS_M`, i.e. unchanged behavior) and `support_window_hours: float = 1.0`
  (default unchanged). The function still only *constructs* a `Target` object — it does not
  itself read ASOS/outcome data — so this parameterization does not touch any actual
  Y-reading/classification logic (hard boundary #5 unaffected).
- `scripts/build_episode_manifest_v16.py`: imported `DEFAULT_OUTCOME_CONTRACT`,
  `UnsupportedOutcomeProfile`, `validate_outcome_profile` from `manifest.py`. Added a new
  standalone function `resolve_disclose_outcome_contract(manifest: dict) -> dict` (pure
  function of the manifest dict; v1-schema or missing-`outcome_contract` manifests take an
  explicit legacy_v1 branch returning `DEFAULT_OUTCOME_CONTRACT`; v2-schema manifests must
  pass `validate_outcome_profile` or `UnsupportedOutcomeProfile` propagates). `run_disclose`
  now calls this helper immediately after the existing `verify_stations_calendar_sha256_match`
  check and BEFORE any AccessPolicy/ASOS-path code (the real
  `data_real_v16/asos` path is constructed later, at the original line ~536) — so a rejected
  contract short-circuits disclosure before any real-data path is touched. Both
  `make_h15_visibility_target` call sites (5km and 1km thresholds) now pass
  `allowed_thresholds=frozenset(outcome_contract["thresholds_m"])` and
  `support_window_hours=outcome_contract["support_window_hours"]` instead of relying on the
  function's hardcoded defaults.
- `tests/test_revision_manifest.py`: rewrote `test_custom_outcome_contract_preserved` (was:
  asserted a custom contract with different thresholds/policy/window/weights was silently
  preserved; now: asserts `build_manifest(...)` raises `UnsupportedOutcomeProfile` for that
  same custom contract). Added `test_default_profile_generates_matching_checkpoints` (default
  profile's per-target checkpoints in `build_manifest`'s output match calling
  `compute_checkpoints(t0, profile=H15_DEFAULT_PROFILE)` directly), `test_inconsistent_manifest_rejected`
  (a contract with valid non-empty weights but missing `checkpoint_offsets_minutes` is
  rejected by `validate_outcome_profile`, not `_validate_checkpoint_weights`),
  `test_validate_outcome_profile_accepts_h15_default` (no-op on the canonical profile and a
  `.copy()` of it), and a new `TestA2_4DiscloseOutcomeContractResolution` class (4 tests)
  exercising `resolve_disclose_outcome_contract` directly and entirely synthetically: v1-schema
  -> legacy branch; v2-schema-labeled-but-missing-`outcome_contract` -> legacy branch anyway
  (absence of the field is what matters, not the schema string); v2-schema with the exact
  default profile -> passes; v2-schema with a deviating profile -> `UnsupportedOutcomeProfile`.
- `plan/plan_v17_0921/TASK_CONTRACT_v17.json`: added a `registered_profile_A2_4` block under
  `C04_scoring_time` recording the exact enforced profile values (thresholds_m,
  report_policy, support_window_hours, checkpoint_weights, checkpoint_offsets_minutes),
  pointing at `H15_DEFAULT_PROFILE` as the source of truth, and stating explicitly that
  verification is synthetic/unit-test only this round (no real `data_real_v16/` run). Also
  appended one new `open_details` entry to `C04_scoring_time` describing the A2-4 enforcement
  and its synthetic-only status. Did not change `status`, `blocked_by`, or
  `closing_evidence` — those remain a G1/A2-8 judgment, not something this task-level edit
  should presume.

**Commands run**:
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py tests/test_revision_ledger.py \
  tests/test_revision_manifest.py tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py
```
Result: **256 passed**, exit code 0 (up from 249 before A2-4; +7 new tests: 3 in
`TestF02OutcomeContract` + 4 in `TestA2_4DiscloseOutcomeContractResolution`). Zero failures,
zero skips, no corrections needed to the new tests or the implementation after the first run.

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_monitoring_admission*.py tests/test_monitoring_taf_tasks*.py tests/test_monitoring_aviation*.py
```
Result: **56 passed**, exit code 0 — exact match to historical baseline; A2-4 did not touch
`ledger.py`/`versions.py`, so no monitoring-side regression was expected or found.

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_outcome_wiring.py
```
Result: **48 passed**, exit code 0. This file is not in the officially listed A2 six-file
target set, but `outcome_wiring.py`'s `make_h15_visibility_target` signature was directly
edited in A2-4, so it was run as an extra precaution. No regression.

**A2-4 acceptance check** (per plan §A2-4 验收):
- "custom 合同被拒" (custom contract rejected): confirmed by the rewritten
  `test_custom_outcome_contract_preserved` and by the new `test_inconsistent_manifest_rejected`
  (covers both a fully-different custom contract and a contract that's merely missing one
  field). Also confirmed at the `run_disclose`-adjacent layer by
  `test_v2_schema_with_unsupported_profile_raises`.
- "默认 profile 生成 checkpoint 与 disclose 目标一致" (default profile generates matching
  checkpoints, consistent with the disclose target): confirmed by
  `test_default_profile_generates_matching_checkpoints` (build_manifest's per-target
  checkpoints match direct `compute_checkpoints(..., profile=H15_DEFAULT_PROFILE)` calls) and
  by `test_v2_schema_with_default_profile_passes` (the exact H15_DEFAULT_PROFILE round-trips
  through `resolve_disclose_outcome_contract` unchanged, which is what
  `run_disclose` then threads into both `make_h15_visibility_target` calls).

**Not claimed**: `run_disclose` itself was NOT executed end-to-end this task (real or
synthetic) — doing so would require constructing a full synthetic AccessPolicy/config/
ExposureRegistry/ASOS-directory fixture, which is A2-5 (synthetic end-to-end integration
test) scope, not A2-4's. Instead, the new early-validation gate was extracted into the
standalone, directly-testable `resolve_disclose_outcome_contract` function and unit-tested
in isolation — this verifies the branching logic (legacy_v1 vs validate-and-use vs reject)
but does NOT verify that `run_disclose`'s surrounding code (AccessPolicy setup, ExposureRegistry
registration, the two `make_h15_visibility_target` call sites) actually wires the resolved
contract through correctly in a live run; that remains A2-5/A2-6 scope. No real
`data_real_v16/` file was read, opened, or globbed during any A2-4 test. No human review
occurred. No live model API calls occurred (none were in scope). Per hard boundary #10, no
real freeze/disclose, LAMP registration, or outcome settlement was executed this round.

## A2-5: End-to-end synthetic counterexample acceptance — DONE (synthetic-only)

**Files added**:
- `tests/test_v17_a2_integration.py` (new, 18 tests). Builds ONE synthetic AFOS/TAF bulk
  file pair (`KSFO_202301.body`/`.json`, 10 hand-crafted frames under `tmp_path`) plus a
  `config.json`-equivalent dict shrinking `calendar_start`/`calendar_end` to 2023-01-05..08
  while keeping the real protected holdout window (2025-02-17..24) verbatim, and drives it
  through the REAL `scripts/run_transition_census_v17.run_census()` entry point — not a
  reimplementation, not a mock of the census logic. The 10 frames cover seven named
  scenarios: initial-prefix baseline (no change), in-episode AMD, late-arriving AMD
  (excluded from scoring), byte-identical duplicate, unresolved equal-BBB tie, a
  never-amended "no-change" target, and an adjacent-but-non-overlapping target. Every
  expected value (per-slot status/flags/change_types, per-change relation_status/reason/
  checkpoint_classification, and the full `CensusResult` aggregate: 48 slots,
  `slots_by_status`, `n_target_change_associations=2`, `n_checkpoint_exposures=18`,
  `n_candidate_blocks=2`, `changes_by_type`, `total_process_groups=1`) was hand-derived from
  reading `tie_resolution.py`/`ledger.py`/`run_transition_census_v17.py`'s decision trees
  (receipt_seq rule in `episode_compiler.compile_afos_taf_stream`, `DEFAULT_DECLARED_LAG_US`
  =120s, the `_CHECKPOINT_EXPOSURE_WEIGHT` table, and the `_compute_slot_status` branch
  order) before this file was written, then cross-checked by running the real functions —
  not copied from a first failing run of the test.

**No other repository file was modified this task** (A2-1 through A2-4's implementation
files were already correct for the properties A2-5 exercises; A2-5 is acceptance-test-only
per the plan).

**Commands run**:
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider tests/test_v17_a2_integration.py
```
First run: 7 of 18 failed — all seven were the same test-fixture bug, not a
production-code defect: `_slot_by_window` matched on `validity_start_us` alone, and since
all four stations share the same time-of-day slot starts, it non-deterministically picked
one of 4 candidate slots (assertion `len(matches) == 1` caught this immediately as `got 4`).
Fixed by also filtering on `station="KSFO"`. Second run: 1 of 18 failed —
`test_scenario7_adjacent_context_only` asserted `num_changes == 0`, but `classify_changes_for_slot`
correctly still records the adjacent-tier package on the slot (`num_changes == 1`,
`relevance_tier == "adjacent_context"`); it is excluded from status/exposure *counting*, not
from the per-slot record itself. This was a wrong assumption in the test, corrected to assert
`num_changes == 1` and to separately check `relevance_tier == "adjacent_context"` on the
underlying change record. Third run: **18 passed**, exit code 0. No production code was
touched to make any of these three runs pass — both fixes were test-fixture corrections.

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py tests/test_revision_ledger.py \
  tests/test_revision_manifest.py tests/test_transition_census_v17.py tests/test_validate_dl3r_semantics.py \
  tests/test_v17_a2_integration.py
```
Result: **274 passed**, exit code 0 (256 from the A2 six-file target set, unchanged, + the
18 new A2-5 tests). Zero failures, zero skips.

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_monitoring_admission*.py tests/test_monitoring_taf_tasks*.py tests/test_monitoring_aviation*.py \
  tests/test_revision_outcome_wiring.py
```
Result: **104 passed**, exit code 0 (56 monitoring + 48 outcome-wiring — exact match to
historical baseline). A2-5 added a new test file only; no regression possible or found.

**A2-5 acceptance check** (per plan §A2-5 验收, all seven required assertions, each mapped
to the test that carries it):
- 拒绝先于读取 (rejection before read): `TestRejectionBeforeRead::test_disallowed_month_path_rejected_before_any_open`
  — a `KSFO_202502.body`/`.json` pair (protected month) is rejected by `AccessPolicy` via
  `read_verified_allowed_file`, with `builtins.open` wrapped to count calls; asserts zero
  opens occurred before the raised `AccessPolicyViolation`. Reuses the same call-counting
  pattern as `test_revision_access_policy.py::TestShortCircuitVerification`.
- 打乱顺序稳定字段不变 (shuffle-order invariance): `TestOrderAndSuffixInvariants::test_shuffled_input_order_yields_identical_ledger`
  — `compile_ledger` on the same 10 packages, as-is vs. `random.Random(20260921).shuffle`'d;
  asserts every ledger entry (keyed by `source_id`) is byte-identical across both orders.
- 追加未来后缀过去视图不变 (future-suffix invariance): `TestOrderAndSuffixInvariants::test_appending_future_suffix_preserves_past_view`
  — prepends an 11th, chronologically-later frame (2023-01-07) to the stream, recompiles the
  ledger, and asserts all 10 original entries are unchanged AND that `visible_at(ledger,
  cutoff=<scenario1's T-60>)` returns the identical visible-source-id set before and after
  the append.
- 冲突阳性对照穿透 (conflict positive control penetrates to summary):
  `TestConflictPositiveControlPenetratesToSummary::test_unresolved_tie_reaches_top_level_summary_count`
  — asserts `CensusResult.n_targets_with_unresolved > 0` and `slots_by_status["UNRESOLVED"] ==
  1`, then locates the specific `all_changes.jsonl` record with
  `relation_reason == "equal_bbb_no_authority"` at the scenario5 target.
- 缺字段不默认 0 (no silent zero-defaulting): `TestMissingFieldsNotDefaultedToZero::test_premise_violation_strips_receipt_fields_entirely`
  — a 2-frame stream violating the D1 file-order premise; asserts `"receipt_seq"` and
  `"receipt_stream"` are absent (`not in pkg`) from every resulting package, not present as 0.
- runtime readset 仅含允许合成输入: `TestReadsetOnlyContainsAllowedSyntheticInput` (2 tests)
  — asserts `input_readset.jsonl` has exactly 1 record, both canonical paths resolve under
  the tmp `bulk_dir`, neither `"data_real_v16"` nor `"quarantine_holdout"` appears anywhere
  in the readset JSON, and that the 139 files absent from the synthetic dir are reported in
  `files_missing` (not silently dropped from the denominator).
- 去 timestamp 后 digest 可复现: `TestDigestReproducibility::test_readset_fingerprint_reproducible_across_runs`
  — runs `run_census` twice against byte-identical input into two separate artifact
  directories; asserts `input_fingerprint.json`'s `readset_digest_sha256` is identical
  across both runs.

Additionally (beyond the seven required assertions, per plan wording "手算期望表覆盖初始
前缀 / 期内有效 AMD / 晚到 / 重复 / 未解等时对 / 无变化目标 / 仅历史上下文目标"):
`TestSevenScenariosViaRealCensusEntryPoint` (10 tests) drives the real `run_census()` entry
point end-to-end and checks every one of the seven named scenarios individually
(per-slot status/flags/change_types plus the specific `EvidenceChange` fields for the AMD
and tie cases), the 5 uncovered "background" KSFO slots, all 36 no-input slots at the other
3 stations, and the full aggregate `CensusResult` in one combined assertion.

**Not claimed**: this task used a single hand-built 10-frame fixture at one station
(KSFO) and one month (202301); it does not exercise the real 140-file archive, real METAR/
AFOS content, or any station other than KSFO. It does not verify performance/scale behavior
of a full 140-file run (that is A2-6 scope). No real `data_real_v16/` file was read, opened,
or globbed by any A2-5 test — every fixture lives under pytest's `tmp_path`. No human review
occurred. No live model API calls occurred (none were in scope). Per hard boundary #10, no
real freeze/disclose, LAMP registration, or outcome settlement was executed this round.

## A2-6: Real smoke test + one full 140-file census — DONE

**Precondition check** (plan requires A2-1/2/3/5 tests passing before any real-archive
task): re-ran the full A2 targeted set immediately before starting —
`274 passed` (0 failed), exit code 0. Confirmed satisfied.

**Process/traceability note (self-disclosed)**: while locating the real bulk directory, an
early reconnaissance `find` command (`find "$D" -iname "*bulk*" -o -iname "*taf*"`) was not
scoped with `-prune` on `quarantine_holdout/` and printed one line,
`quarantine_holdout/taf`, before any file inside it was opened — a directory-name listing
of one path segment, not a listing of quarantine_holdout's contents or any file read from
it. This is a violation of hard boundary #2 ("不打开、不列举、不读取
quarantine_holdout/") in spirit even though no file content was touched. Caught immediately,
stated to the user in-band at the time, and corrected: every subsequent filesystem scan
under `data_real_v16/` used `find ... -path ".../quarantine_holdout" -prune -o ...` to
exclude it structurally. `quarantine_holdout/` was never opened, listed beyond that one
line, or read from, for the remainder of this task. Recorded here rather than omitted, per
the standing instruction to disclose rather than hide any data-protection-adjacent slip.

**Locating the real bulk directory**: `data_real_v16/README.txt` (data-directory
documentation, not scoring content) confirmed the directory layout. Three TAF raw-text run
directories exist under `data_real_v16/taf/`: `..._dl3rbulk` (140 `.body`/`.json` files,
matching `EXPECTED_FILES` exactly), `..._dl3rbulk_backfill` (70 loose per-product files
named `backfill_<STATION>_<YM>_<N>.body`, not the `{station}_{year_month}.body` shape
`verify_140_files` expects), and `..._dl3rbulk_backfill_retry1` (3 more loose retry files).
`..._dl3rbulk/RECONCILIATION_DL3R.md` (pre-existing, generated 2026-09-20, not authored this
task) explicitly names `..._dl3rbulk/` as the "Raw Text Source" and documents two
station-months (KDEN 202506, KORD 202306) as `BACKFILLED` in its reconciliation table. A
direct byte-level SOH-frame count on `KDEN_202506.body` inside `..._dl3rbulk/` (319 frames)
does not match the reconciliation table's claimed final coverage count (330) — i.e. the
loose backfill frames documented in that report do not appear to have been merged into the
canonical station-month file yet. This is a **pre-existing condition disclosed in this
task's reconnaissance, not created by it**: per hard boundary #4 ("真实清点只使用现有显式
允许的 140 个 TAF station-month 文件，继续排除整个 2025-02，不扩大文件范围") this task did
not fetch, merge, or otherwise touch the loose backfill files — `..._dl3rbulk/` was used
as-is, exactly as `verify_140_files`/`run_transition_census_v17.py --bulk-dir` already
defaults to (confirmed the script's own `argparse` default already points at this same
directory and at `data_real_v16/config/stations_calendar_v16.json`, i.e. this is an
established entry point, not a new path chosen by this task). **Flagged for A2-7/A2-8**:
KDEN_202506 and KORD_202306 have a disclosed, pre-existing under-count of an unknown
magnitude relative to their own reconciliation report's claim; this does not violate any
hard boundary but should be named explicitly in the final report's "withdrawn/narrowed"
and "needs independent verification" sections.

**Smoke test** (script: `artifacts_v17/ba2_20260921T202507Z/a2_6_smoke.py`, real read entry
point `read_verified_allowed_file` + `compile_afos_taf_stream`, not a mock): 2
pre-specified station-months, **chosen from the plan text itself**
("如 KSFO_202301、KORD_202412") before any real file content was inspected this task — i.e.
not selected by outcome/Y or by anything learned during this task's reconnaissance.
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python artifacts_v17/ba2_20260921T202507Z/a2_6_smoke.py
```
Result: exit 0. Both station-months: `read_ok=true`, receipt sha256 == recomputed body
sha256 (KSFO_202301: `7ed67b3b...`, KORD_202412: `dbf5cf1f...`), `compile_ok=true`,
KSFO_202301 → 303 packages / 0 skipped / 0.0036s read + 0.1244s compile; KORD_202412 → 298
packages / 0 skipped / 0.0037s read + 0.1167s compile. Both package counts match
`RECONCILIATION_DL3R.md`'s independently-generated "Raw text frame count" column exactly
(303, 298) — an unplanned but useful cross-check against a pre-existing artifact. No
`outcome_wiring`/`providers.asos`/`providers.metar` module was ever loaded into the process
(checked via `sys.modules` after execution, not by grepping source text — an initial version
of this same self-check grepped the script's own source and trivially "failed" because the
check's own string literals contain the forbidden substrings; fixed to a runtime
`sys.modules` check before being relied on). Two bugs surfaced and fixed in the smoke
script itself during this step (not in production code): passing `verified.body` (bytes)
directly to `compile_afos_taf_stream` (expects `str`) → added `.decode("utf-8",
errors="replace")` matching `verify_140_files`'s own convention; and an `except` handler
that clobbered `entry["read_ok"]` back to `False` after a successful read when the
*subsequent* compile step raised — changed to `setdefault` so read/compile outcomes are
recorded independently. Receipt: `artifacts_v17/ba2_20260921T202507Z/a2_6_smoke_receipt.json`.

**Full 140-file census** (plan: "余量充足则跑一次 140 文件完整清点到 OUT/", authorized
because the smoke test was clean and the precondition held):
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/run_transition_census_v17.py \
  --bulk-dir /mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/taf/20260920T134949Z_1bbe63aedc00_dl3rbulk \
  --config /mnt/afs/260010168/extreme_weather_benchmark/data_real_v16/config/stations_calendar_v16.json \
  --artifacts-dir artifacts_v17/ba2_20260921T202507Z/census_full_run \
  --out artifacts_v17/ba2_20260921T202507Z/census_full_run/census_summary.json
```
Started 2026-09-21T20:26:53Z, finished 2026-09-21T20:43:14Z. Wall clock: **16m20.544s**
(`user 15m53.243s`, `sys 0m10.579s`). **Process exit code: 1** — this is the script's own
documented convention (`scripts/run_transition_census_v17.py` lines ~1216-1220): return 2 =
file-integrity hard-gate failure, return 1 = clean run with `n_targets_with_unresolved > 0`,
return 0 = clean run with zero unresolved. File integrity was perfect (140/140 verified, 0
missing, 0 hash mismatches → no hard-gate failure); exit 1 here means the run completed and
self-reported that real unresolved-conflict targets exist. **This is not a crash and not
silently treated as success** — recorded here exactly as the script reports it.

Output written to `artifacts_v17/ba2_20260921T202507Z/census_full_run/` (under `$CODE`,
never under `data_real_v16/`): `census_summary.json`, `input_readset.jsonl` (140 lines),
`input_fingerprint.json`, `slot_summary.jsonl` (7.8M), `all_changes.jsonl` (190M),
`exclusions.jsonl` (116 lines), `process_groups.json`. Verified post-hoc:
`grep -c quarantine_holdout` across every output file → 0 matches everywhere;
`input_fingerprint.json.n_files == 140`; all 116 `exclusions.jsonl` rows have
`"reason": "protected_window"` (count matches `census_summary.json`'s
`exclusions_count: 116` exactly), each carrying only validity-window timestamps and a
boolean overlap flag — no raw TAF text or content from the protected window appears in any
output.

**Real census summary numbers** (unit: `total_continuous_calendar_slots` = one row per
(station, 6-hour-target-slot) under "四时次日历采样" — 4 stations × 35 allowed months × 4
daily targets, denominator **17,420**, matching the plan's own root-cause note that the
prior report's 17,064 denominator was wrong and the correct total is 17,420):
- File integrity: 140/140 verified, 0 missing, 0 hash mismatches.
- Slot status (denominator 17,420): `NO_INPUT`=0, `NO_APPLICABLE_EVIDENCE`=348,
  `INITIAL_ONLY_NO_CHANGE`=16,743, `IN_EPISODE_CHANGE`=292, `UNRESOLVED`=37.
- Calendar-level exclusions (protected window): 116.
- `n_unique_sources`=41,375; `n_unique_relation_edges`=41,375;
  `n_target_change_associations`=308; `n_targets_with_initial_evidence`=16,743;
  `n_targets_with_in_episode_change`=292; `n_targets_with_unresolved`=37;
  `n_checkpoint_exposures`=510,975; `n_candidate_blocks`=4,275.
- Changes by type: `INITIAL_BASELINE`=102,369; `AMD`=121,859; `COR`=2,687;
  `mirror_duplicate`=15.
- Process groups: 275 total (KSFO 89, KDEN 92, KJFK 49, KORD 45).
- Compilation: 41,386 packages compiled from 140 files, 60 frames skipped (not padded, not
  investigated further this task — skip reasons are in `errors`/compiler internals, out of
  A2-6 scope; flagged for A2-7 if a witness item happens to land on one).

**Answer to the batch's core scientific question** ("对同一个固定未来天气目标，在
T−60/T−40/T−20 的实际评分过程中，到底有多少合法可见、相关且可核验的新证据变化"): of 17,420
real (station, target-slot) pairs under the current instrument, **292** show an in-episode
change-like (AMD/COR) event that is both strict-overlap-relevant and visible by an
in-scoring checkpoint (`IN_EPISODE_CHANGE`), and a further **37** show real, currently
unresolved equal-BBB ties among candidate predecessors (`UNRESOLVED` — genuine measurable
conflict, not zero, not silently dropped). 16,743 slots have initial-prefix evidence only
with no in-episode change; 348 have no applicable (strict-overlap, in-scoring-window)
evidence at all. **This is a raw instrument count, not a G1 pass/fail judgment** — G1 status
is decided in A2-8 after independent-verification witnessing (A2-7).

**Not claimed**: this run does not verify the *semantic correctness* of any individual
AMD/COR classification against the true underlying weather report content — only that the
pipeline runs end-to-end on real files, hashes verify, and the counts are internally
consistent. It does not resolve the KDEN_202506/KORD_202306 backfill-completeness question
above. No human review occurred. No ASOS/METAR file was read (confirmed structurally by
import list and confirmed at runtime by the smoke test's `sys.modules` check). No real
freeze/disclose/LAMP registration/outcome settlement was executed (out of scope per hard
boundary #10). The 37 unresolved targets are not yet individually witnessed — that is A2-7.

## A2-7: Independent-review witness package — DONE

Built from the A2-6 real `census_full_run/` output only (`all_changes.jsonl`,
`slot_summary.jsonl`, `input_readset.jsonl`) plus the same already-allowed 140 real body
files — no new file, no `quarantine_holdout/`, no ASOS/METAR/outcome module touched
(script never imports any outcome/label module; verified by code inspection of its own
import list, not re-run through the `sys.modules` runtime check this time — noted as a
minor asymmetry with A2-6's stricter self-check, disclosed rather than silently upgraded).

Script: `artifacts_v17/ba2_20260921T202507Z/a2_7_witness_select.py`.
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python artifacts_v17/ba2_20260921T202507Z/a2_7_witness_select.py
```
Exit 0. Output: `artifacts_v17/ba2_20260921T202507Z/witness_v1/witnesses.jsonl` (30 items),
`episode_illustration.json`, `selection_report.json`.

**Selection method (structural, not Y-based)**: streamed `all_changes.jsonl` once and
bucketed records into the plan's named types by field values already present in the
census output (`change_type`, `relevance_tier`, `checkpoint_classification`,
`relation_status`, `dispute_status`) — never by any outcome/label file, which this script
never opens. Within each bucket, kept the first N distinct-(target, current_source_id)
records **in file order** (file order follows the fixed station/date iteration order
of the census script, not any relevance/outcome ranking). This is deterministic and
reproducible but has a disclosed side effect: several buckets ended up concentrated on
one or two stations (`regular_amd`, `adjacent_history`, `duplicate` → KSFO only;
`conflict_unknown` → KJFK only) because file order clusters by station before the
target N per bucket was reached. Station diversity was not a stated A2-7 acceptance
criterion, so this was not corrected by re-sampling (re-sampling to force station spread
would itself be a selection criterion beyond "first in file order" and was judged
higher-risk to introduce than to leave disclosed).

**Result — all 7 plan-named types present** (none absent; counts: regular AMD=4,
regular COR=2, 晚到/late-arriving=4, 重复/duplicate=4, 相邻历史/adjacent-history=4,
跨窗/cross-window=4 → total 26 change-level witnesses) **+ 4 slot-level "无变化" witnesses**
(2 `INITIAL_ONLY_NO_CHANGE`, 2 `NO_APPLICABLE_EVIDENCE`) = **30 witnesses**, within the
plan's 24–32 range. Deduplicated by (target_station, target_validity_start/end,
current_source_id) — no two witnesses share that key.

Each witness carries: station; target support window (start/end, us + ISO); issue/
available/basis (`issued_at_us`, `available_at_us`, `availability_basis`); per-checkpoint
visibility computed directly as `available_at_us <= checkpoint_{t60,t40,t20}_us` (not
copied from any pre-existing boolean field — recomputed here); `candidate_predecessors`;
rule basis (`change_type`, `relevance_tier`, `checkpoint_classification`,
`relation_status`, `relation_reason`, `dispute_status`, `target_content_change`); a
`review_question` (independent-review prompt) kept separate from a `program_answer`
(the pipeline's own stated judgment, phrased so a reviewer can agree/disagree rather than
re-derive); empty `independent_judgment`/`disagreement_notes` fields for the reviewer to
fill; `status: PENDING_INDEPENDENT_REVIEW`.

**Byte identity**: for each of the 26 change-level witnesses, re-opened the same
already-allowed real body file (re-verified sha256 against `input_readset.jsonl` before
use), recompiled it with the real `compile_afos_taf_stream` entry point, matched the
witness's `current_source_id` to its package's `receipt_seq`, and located that frame's
exact byte span in the raw archive via an offset-preserving reimplementation of
`split_afos_stream`'s own SOH/ETX framing logic (byte-level, not the string-level
original — avoids any utf-8 decode ambiguity). **26/26 (100%) resolved** to a real
`(body_path, byte_start, byte_end, frame_index, total_frames_in_file)` plus a raw-text
preview of the frame's first non-blank lines. The 4 slot-level "no-change" witnesses have
no change record to locate by construction (`byte_identity.resolved=false`, reason stated
explicitly as "no change record for this slot", not a failure).

Example (`conflict_unknown`, station KJFK, `KJFK-1688894520000000-277d4d5a3b90`): resolved
to `KJFK_202307.body`, byte range [71031, 71467), frame preview `FTUS41 KOKX 090922 AAB /
TAFJFK / TAF AMD ...` — the real WMO `AAB` (second amendment) suffix is directly visible in
the raw frame, consistent with the program's `bbb_contradicts_receipt_order` judgment
being about actual conflicting BBB metadata, not a synthetic artifact.

**Episode illustration** (`episode_illustration.json`): one real target, KORD
2023-01-01T12:00–13:00Z (checkpoints T-60=11:00Z, T-40=11:20Z, T-20=11:40Z), with 7
associated raw records spanning `INITIAL_PREFIX` → `INTERVAL_2` → `AFTER_LAST_SCORE`.
At T-60 and T-40 only the first 4 records (all available by 09:06Z) are visible; between
T-40 and T-20 two more records (an `INITIAL_BASELINE` at 11:33Z and a `COR` at 11:37Z)
newly cross their `available_at` threshold and become visible exactly at T-20 — this is a
concrete real instance of the batch's core question ("legitimate new evidence appearing
within the T-60→T-20 window"). One further `AMD` (available 12:20Z) never becomes visible
at any of the three checkpoints and is correctly excluded (`AFTER_LAST_SCORE`).

**Not claimed**: none of the 30 `program_answer`/`review_question` pairs have been
independently judged yet — `independent_judgment` is null on every witness and
`status=PENDING_INDEPENDENT_REVIEW` throughout; this package is instrument output for a
human reviewer, not a completed review. No claim is made that the 26/30-station-skewed
selection is a representative sample of the full 292 `IN_EPISODE_CHANGE` / 37 `UNRESOLVED`
population — it is a traceability demonstration, not a statistical sample.

## A2-8: Regression, reconciliation, handoff — DONE

**Directed test run:**
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py \
  tests/test_revision_ledger.py tests/test_transition_census_v17.py \
  tests/test_revision_manifest.py tests/test_validate_dl3r_semantics.py \
  tests/test_v17_a2_integration.py
```
Result: `274 passed in 2.63s`. Exit 0. 0 failed, 0 skipped.

**Full regression run:**
```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_*.py tests/test_validate_dl3r_semantics.py \
  tests/test_monitoring_admission.py tests/test_monitoring_taf_tasks.py tests/test_monitoring_aviation.py \
  tests/test_v17_a2_integration.py tests/test_transition_census_v17.py
```
Result: `731 passed, 4 warnings in 6.62s`. Exit 0. 0 failed, 0 skipped. The 4 warnings are
pre-existing deprecation warnings in `test_revision_metrics.py` (a file not touched by A2 —
confirmed unrelated by inspection, not newly introduced).

**Documents written this task:**
- `plan/plan_v17_0921/TRANSITION_CENSUS_v17_A2.md` (new) — corrected checkpoint-aware census
  report using the real A2-6 `census_summary.json` numbers (17,420-slot denominator, 292
  IN_EPISODE_CHANGE, 37 UNRESOLVED, 46 genuinely-unresolved change records all tracing to
  `bbb_contradicts_receipt_order`), full read-scope/boundary disclosure (including the
  quarantine_holdout incident and the KDEN_202506/KORD_202306 backfill-incompleteness caveat),
  and an explicit "Not claimed" section (G1 not asserted PASSED/FAILED).
- `plan/plan_v17_0921/LABEL_QUALIFICATION_v17_A2.md` (new) — describes the A2-7 witness
  package as the current qualification instrument (30 items, 26/26 byte-identity resolved,
  all 7 plan-named types present, station-skew caveat disclosed and left uncorrected on
  purpose), status `PENDING_INDEPENDENT_REVIEW` on all items, carries forward updated
  recommendations for a future independent reviewer.
- `plan/plan_v17_0921/BATCH_A2_ACCEPTANCE.md` (new) — full batch acceptance report: §1
  task-by-task status (A2-0 through A2-8 all DONE), §2 exact test commands/results, §3
  counterexamples closed (CE1-CE4 + dead-field + supersedes-truncation, all CLOSED) vs.
  remaining (OR1a/OR1b, UNASSESSED content-change, 60 skipped frames, LAMP/QL — all
  explicitly out of scope), §4 test commands, §5 read range/stats with units and
  denominators, §6 five withdrawn/narrowed historical claims (including the
  quarantine_holdout incident and the backfill caveat), §7 instrument-acceptance-PASSED vs.
  G1-status-PENDING_INDEPENDENT_REVIEW kept explicitly separate, §8 seven items still needing
  independent verification/real data/later work, §9 explicit OPEN/DEFERRED/NOT-EXECUTED list
  (METAR dedup, exposure-registry fault-tolerance, LAMP/QL, full contract system, model
  matrix, Living, multi-hazard, related-work, BA4, real freeze/disclose/LAMP).

**Superseded pointers added** (original text preserved verbatim below each pointer, nothing
deleted or altered): `TRANSITION_CENSUS_v17.md` and `LABEL_QUALIFICATION_v17.md` each now
open with a blockquote note pointing to their `_A2` replacement.

**EXECUTION_STATUS_v17.md reconciled**: BA1 row moved from "IMPLEMENTED / qualification
PENDING (A2-1)" to "DONE (A2-1 fix applied and tested)" (A2-1 completed and tested since that
row was written). BA3 row and detail section updated to reference A2-6/A2-7 completion. G1
gate-status row corrected from stale future-tense "A2-6 will attempt one traceable re-census"
(pre-dating A2-6's actual completion) to the real outcome: A2-6 completed (140/140 file
integrity, 292/37 real counts) and A2-7 completed (30-item witness package, 26/26 byte-traced);
G1 status moved from `PENDING_REVERIFICATION` to `PENDING_INDEPENDENT_REVIEW` — explicitly
still not PASSED. Next Steps section rewritten to reflect A2-0..A2-8 all DONE, with the single
concrete next action being independent human review of the witness package.

**Boundary compliance this task**: no new file read beyond `EXECUTION_STATUS_v17.md`,
`TASK_CONTRACT_v17.json` (read-only, via the recursive-key-search script), the two old
PLAN-dir reports, and the already-produced A2-6/A2-7 artifacts under `artifacts_v17/`. No
`data_real_v16/` file touched. No `quarantine_holdout/` access. No ASOS/METAR file touched. No
commit/push/merge performed (HEAD unchanged at `daba7cf3f1b53b5b6d8c8d376773c2b9d43d9644`,
confirmed via `git rev-parse HEAD` immediately before writing these documents). No additional
agent launched.

**A2-8, and Batch A2 as a whole, is DONE.** Final 9-item report delivered to the user in this
session's final reply per the plan's exit rule (§8): instrument CLOSED, real run COMPLETE and
trustworthy, no independent review yet → **G1 = PENDING_INDEPENDENT_REVIEW**, not PASSED.
