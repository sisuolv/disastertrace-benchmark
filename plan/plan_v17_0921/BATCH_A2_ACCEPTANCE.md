# Batch A2 Acceptance Report

Generated: 2026-09-21T21:00:06Z
Batch: A2 (H15 data-qualification measurement-chain repair and traceable re-census)
Plan: `/mnt/afs/260010168/.claude/plans/wobbly-pondering-gizmo.md` (plan mode, Fable 5.1)
Reference commit: `daba7cf3f1b53b5b6d8c8d376773c2b9d43d9644` (unchanged all batch — no commits
made; all A2 code/doc changes exist only as an uncommitted working-tree diff, per hard
boundary #7). Branch: `v17-batch-a-v1`.
Session start (A2-0 baseline): 2026-09-21T17:08:26Z. This report's generation time:
2026-09-21T21:00:06Z. Elapsed: ~3h52m of the ~10h budget.

**Execution-method disclosure**: this entire batch was implemented by the parent session
directly (Sonnet 5, `claude-sonnet-5`), not delegated to `fableplan:complex-executor` or
`fableplan:simple-executor`, per hard boundary #7 ("不启动额外 agent"). Planning for this batch
was done in plan mode (resolves to Fable 5.1 under this repo's `opusplan` routing config), but
no implementation work was Opus-executed.

## §1 — Task-by-task status

| Task | Status | Evidence |
|---|---|---|
| A2-0 | DONE | `TASK_CONTRACT_v17.json` `meta.g1_gate_status=PENDING_REVERIFICATION`, `meta.correction_history[0]` verified present; `EXECUTION_STATUS_v17.md` BA1/BA3/BA4/G1 rows corrected (verified present) |
| A2-1 | DONE | `access_policy.py` fail-closed path/param consistency + `read_verified_allowed_file`; tests in `test_revision_access_policy.py` pass |
| A2-2 | DONE | `tie_resolution.py`/`ledger.py` permutation-invariant tie handling, `relation_status`/`relation_reason`/`candidate_predecessors` fields; `test_revision_receipt_order.py`/`test_revision_ledger.py` pass; monitoring trio regression clean |
| A2-3 | DONE | Checkpoint-aware `run_transition_census_v17.py` rewrite, full 17,420-slot continuous calendar; `test_transition_census_v17.py` passes |
| A2-4 | DONE | `H15_DEFAULT_PROFILE`/`validate_outcome_profile` in `manifest.py`; `test_revision_manifest.py` passes (custom-contract rejection test updated to expect explicit rejection) |
| A2-5 | DONE | `tests/test_v17_a2_integration.py` end-to-end synthetic counterexample suite added and passing |
| A2-6 | DONE | Real 140-file census run: exit 1 (expected — UNRESOLVED slots present), 16m20s, 140/140 file integrity, full `census_summary.json` produced in `artifacts_v17/ba2_20260921T202507Z/census_full_run/` |
| A2-7 | DONE | 30-item witness package, 26/26 (100%) byte-identity resolution among change-level witnesses, all 7 plan-named types present, one real 3-checkpoint episode illustration |
| A2-8 | DONE (this document + regression + reconciliation) | See §4 below |

No task is BLOCKED. No task was skipped.

## §2 — Regression and directed test results (A2-8)

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_access_policy.py tests/test_revision_receipt_order.py \
  tests/test_revision_ledger.py tests/test_transition_census_v17.py \
  tests/test_revision_manifest.py tests/test_validate_dl3r_semantics.py \
  tests/test_v17_a2_integration.py
```
Result: **274 passed**, 0 failed, 0 skipped (2.63s).

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -o addopts= -q -p no:cacheprovider \
  tests/test_revision_*.py tests/test_validate_dl3r_semantics.py \
  tests/test_monitoring_admission.py tests/test_monitoring_taf_tasks.py tests/test_monitoring_aviation.py \
  tests/test_v17_a2_integration.py tests/test_transition_census_v17.py
```
Result: **731 passed**, 0 failed, 0 skipped, 4 warnings (6.62s). The 4 warnings are
pre-existing deprecation warnings in `test_revision_metrics.py`, unrelated to any A2 change
(not newly introduced — `test_revision_metrics.py` was not touched by A2).

No regressions found. No test was skipped, and no test file in the A2 scope reported
collection errors.

## §3 — Counterexamples closed vs. remaining

Six root-cause defects (CE1-CE4 plus the two named in the plan's "other verified" list —
dead `tie_unresolved` field, `supersedes[0]` truncation) were confirmed present pre-fix by
direct code reading and reproduced synthetically, then fixed with regression tests:

| ID | Defect | Status |
|---|---|---|
| CE1 | `resolve_receipt_tie_strict` order-dependent on equal-BBB ties | CLOSED — permutation-invariance test in `test_revision_receipt_order.py` passes; real run confirms 46/46 genuine unresolved records all trace to this exact cause |
| CE2 | `compile_ledger` mutual A→B/B→A supersession under ambiguous same-instant AMDs | CLOSED — `test_revision_ledger.py` asserts no mutual supersession; real run shows 0 mutual-supersede pairs |
| CE3 | Checkpoint-blind classification (`issued_at < T` only) | CLOSED — `test_transition_census_v17.py` T-10 AMD case now correctly classified `AFTER_LAST_SCORE`, not counted as in-episode |
| CE4 | `AccessPolicy.assert_allowed` bypassable via explicit `as_of_us`/`year_month` override | CLOSED — `test_revision_access_policy.py` asserts fail-closed rejection on path/param mismatch |
| Dead `tie_unresolved` field | Census read a field the ledger never emitted | CLOSED — replaced by genuinely-emitted `relation_status` |
| `supersedes[0]` truncation | Multiple legitimate predecessors silently dropped to one | CLOSED — `supersedes` kept as full list end-to-end |

**Remaining, not addressed this batch (by design, out of scope):**
- OR1a (Y-distribution/positive-label statistical power) — inherently Y-dependent, explicitly
  out of scope for a Y-blind batch.
- OR1b (process-group independence) — descriptive grouping only, no independence claim made
  or attempted.
- `target_content_change=UNASSESSED` on every record — no new meteorological-content-diff
  logic was written.
- The 60 skipped compilation frames (41,386 total packages) were not individually
  investigated for root cause this batch.
- LAMP gzip-truncation (F06) and QL branch — untouched, explicitly out of scope (no
  model/API/GPU work this batch per hard boundary #6).

## §4 — Actual test commands and results

See §2 above (both commands and both exact result lines reproduced verbatim, not summarized).

## §5 — Actual read range and stats (units and denominators)

- Real TAF files read: 140/140 of the allowed `station-month` set (denominator: the fixed
  140-file allow-list; numerator: 140 verified by sha256). 0 files outside this set opened.
- Continuous calendar slots evaluated: 17,420 (denominator: 4 stations × 35 allowed months ×
  4 daily checkpoints-anchor-times; this is the full calendar, not a filtered subset).
- Change records produced: 226,930 (this is a record count, not a slot count — one slot can
  have 0 to many change records).
- IN_EPISODE_CHANGE slots: 292 / 17,420 = 1.68%.
- UNRESOLVED slots: 37 / 17,420 = 0.21%.
- Genuinely unresolved change-level records: 46 / 226,930 = 0.02%, all with
  `relation_reason=bbb_contradicts_receipt_order`.
- Witness package: 30 items / (24-32 planned range) — all 7 named types present (0 absent).
- Byte-identity resolution: 26/26 = 100% of the 26 change-level witnesses (the 4 slot-level
  no-change witnesses are not in this denominator by construction — see
  `LABEL_QUALIFICATION_v17_A2.md`).

Full detail with per-type and per-checkpoint breakdowns is in `TRANSITION_CENSUS_v17_A2.md`.

## §6 — Historical claims withdrawn or narrowed this batch

1. "G1 evidence-existence PASSED" (original V17-03 conclusion) — **withdrawn**, per A2-0,
   status now `PENDING_REVERIFICATION` → after A2-6/A2-7 completion, honestly assessable as
   **`PENDING_INDEPENDENT_REVIEW`** (instrument closed, one real run done, no human review yet
   — neither PASSED nor FAILED).
2. "0% dispute rate" / "Unresolved conflicts: 0" — **withdrawn**; real dispute rate is 46/226,930
   change-level records (37/17,420 slots), not structurally zero.
3. "121,885 total changes across 17,064 revision-enriched slots, ~98% coverage" — **narrowed/
   corrected**; correct full-calendar denominator is 17,420, and the corrected count of
   IN_EPISODE_CHANGE + UNRESOLVED slots (the actual "something happened" subset) is 329
   (292+37), not the entire changes-by-type total (226,930 records, which includes
   INITIAL_BASELINE records for every slot with any input at all).
4. **Boundary-compliance incident, disclosed not retracted**: during A2-6 script development,
   one `find` command briefly traversed into `quarantine_holdout/` and printed a single
   directory-name line (`.../quarantine_holdout/taf`) before being caught — a violation of hard
   boundary #2 in spirit, though no file content inside `quarantine_holdout/` was ever read,
   opened, or used in any output. Self-flagged and corrected within the same A2-6 work session;
   all subsequent directory scans use `-path .../quarantine_holdout -prune -o ...`. Logged here
   and in `BATCH_A2_PROGRESS.md`'s A2-6 entry per the requirement to disclose, not omit,
   boundary near-misses.
5. **Input-corpus incompleteness caveat, not previously stated**: `KDEN_202506` and
   `KORD_202306` are known (via `RECONCILIATION_DL3R.md`, cited in A2-6) to have incomplete
   backfill relative to sibling months. This was not disclosed in the original V17-03 report at
   all; it is now explicitly carried in `TRANSITION_CENSUS_v17_A2.md`.

## §7 — Instrument acceptance vs. G1 status (kept separate, per plan requirement)

**Instrument acceptance: PASSED.** All A2-1 through A2-5 acceptance criteria met:
- A2-1: real census entry point rejects out-of-boundary targets before any glob/open (0
  glob/open calls on rejected targets, verified by the directed test's counting harness); a
  body-content change with an unchanged receipt fails sha-verification as required.
- A2-2: CE1 fix is permutation-invariant across all tested orderings; CE2 fix produces
  `concurrent`/`unresolved` with no mutual supersession; synthetic conflict fixture makes the
  aggregate unresolved count > 0; monitoring three-file regression clean.
- A2-3: T-10 AMD correctly excluded from in-episode change count via `AFTER_LAST_SCORE`; every
  slot in the full calendar is output and reconciles between detail and summary files.
- A2-4: custom outcome contract explicitly rejected; default profile's generated checkpoints
  match the disclose-path target exactly.
- A2-5: end-to-end synthetic counterexample suite (`test_v17_a2_integration.py`) passes,
  covering rejection-before-read ordering, permutation stability, append-only-future
  non-mutation, and digest reproducibility.

**G1 (data qualification / evidence-existence) status: `PENDING_INDEPENDENT_REVIEW`.** Per the
plan's own exit rule (§8): "仪器过、真实运行未完 → census PENDING；清点可信、无独立核验 → G1
PENDING_INDEPENDENT_REVIEW". The instrument passed, and one full real run completed and is
internally consistent (file integrity 140/140, exit code semantics explained, summary matches
stdout trace) — so this is **not** "PENDING" in the weaker instrument-only sense. But no human
has independently reviewed the A2-7 witness package, so G1 is **not** claimed PASSED. This is
an explicit, deliberate non-commitment per the original instruction ("不要承诺 G1 必须通过").

## §8 — What still needs independent verification, real data, or later experiments

1. Human review of all 30 A2-7 witnesses (`witnesses.jsonl`) — the single most direct remaining
   gap before G1 can be assessed as PASSED or FAILED.
2. OR1a: Y-permissioned positive-label distribution analysis (requires ASOS/METAR access,
   explicitly forbidden this batch by hard boundary #5).
3. OR1b: an actual independence justification (or explicit acknowledgment of non-independence
   with a variance correction) for the 275 process groups.
4. Root-cause investigation of the 60 skipped compilation frames.
5. Resolution of the KDEN_202506/KORD_202306 backfill-incompleteness caveat (requires a new,
   currently-forbidden download).
6. `target_content_change` semantic assessment (currently `UNASSESSED` on all 226,930 records)
   — a genuinely new scope item, not started.
7. Station-balance re-selection decision for the 4 skewed witness-type buckets (§ in
   `LABEL_QUALIFICATION_v17_A2.md`).

## §9 — Explicitly OPEN / DEFERRED / NOT EXECUTED (not expanded this batch)

Per the A2 plan's explicit exclusion list, none of the following were touched, attempted, or
partially implemented this batch — listed here for completeness, not as new findings:

- METAR 语义去重 / COR 权威 (METAR semantic deduplication / COR authority resolution)
- exposure registry 耐故障 (exposure registry fault-tolerance)
- LAMP / QL (LAMP gzip-truncation fix, QL branch)
- 完整合同系统 (full outcome-contract system beyond the single `H15_DEFAULT_PROFILE`)
- 模型矩阵 (model evaluation matrix)
- Living (living/continuously-updating capability, G4)
- 多灾种 (multi-hazard scope expansion beyond TAF/aviation)
- related-work (literature/related-work section)
- BA4 (V17-04 partial: unified view / three-arm state, interface-only) — explicitly NOT IN
  THIS BATCH per `EXECUTION_STATUS_v17.md`
- Real freeze/disclose, LAMP registration, or outcome settlement — explicitly forbidden this
  batch by hard boundary #10; only synthetic verification of any touched code paths was done

## Document index

- `TRANSITION_CENSUS_v17_A2.md` — corrected census report (this batch)
- `LABEL_QUALIFICATION_v17_A2.md` — corrected label-qualification / witness-package report (this batch)
- `TRANSITION_CENSUS_v17.md` — original report, preserved verbatim below a new superseded-pointer note
- `LABEL_QUALIFICATION_v17.md` — original report, preserved verbatim below a new superseded-pointer note
- `BATCH_A2_PROGRESS.md` — full task-by-task command/exit-code/result log, A2-0 through A2-8
- `artifacts_v17/ba2_20260921T202507Z/census_full_run/` — real census machine output
- `artifacts_v17/ba2_20260921T202507Z/witness_v1/` — witness package machine output
