# Transition Census v17 — Batch A2 Corrected Report

Generated: 2026-09-21T21:00:06Z
Supersedes: `TRANSITION_CENSUS_v17.md` (original V17-03 report, 2026-09-21T13:35:49Z) — that
report's headline conclusions are **withdrawn**; see `TASK_CONTRACT_v17.json`
`meta.correction_history[0]` and `EXECUTION_STATUS_v17.md` Gate Status / G1.
Reference commit (working tree unmodified from this HEAD; A2 code changes exist only as an
uncommitted working-tree diff per hard boundary #7 — no commits/pushes made this batch):
`daba7cf3f1b53b5b6d8c8d376773c2b9d43d9644`.
Producing run: `artifacts_v17/ba2_20260921T202507Z/census_full_run/` (script:
`scripts/run_transition_census_v17.py` as modified through A2-1/A2-2/A2-3).

## What changed vs. the original report

The original `TRANSITION_CENSUS_v17.md` was produced by a measurement chain that three
independent reviews (R02/R03/R06, merged in `TASK_CONTRACT_v17.json` `correction_history`)
found defective in ways that directly affect the numbers below:

1. **Checkpoint-blind classification (CE3, fixed in A2-3).** The original census classified
   a change as "in scope" using only `issued_at < target_start`, never consuming the three
   scoring checkpoints (T-60/T-40/T-20) or `available_at`. A change issued at T-10 (after the
   last checkpoint) was counted identically to one issued at T-90. This run instead compiles
   each station's full ledger once and evaluates `visible_at(ledger, cutoff=checkpoint)` at
   each of the three checkpoints separately, classifying every change's `checkpoint_classification`
   as one of `INITIAL_PREFIX` / `INTERVAL_1` / `INTERVAL_2` / `AFTER_LAST_SCORE`.
2. **Dead dispute field (fixed in A2-2/A2-3).** The original "0% dispute rate" / "Unresolved
   conflicts: 0" claim read a `tie_unresolved` field that `compile_ledger()` never emitted —
   it was structurally incapable of being anything but 0. This run's ledger now emits
   `relation_status ∈ {resolved, unresolved, not_applicable}` genuinely, and the census reads
   that field. Real result: **37 targets with `UNRESOLVED` status**, all 37 genuinely
   `dispute_status=unresolved` at the individual-change level.
3. **Wrong denominator (fixed in A2-3).** The original report's "17,064 revision-enriched
   slots" figure undercounted the true continuous calendar (should have been closer to 17,078
   for the "not NO_INPUT" subset, and 17,420 for the full four-times-daily calendar including
   `NO_INPUT`/excluded slots) — its "~98% coverage" line divided by the wrong base. This run
   reports every slot in the full continuous calendar with an explicit denominator on every
   ratio.
4. **Unjustified process-group independence.** The original report's 4,264 "process groups"
   were station/issue-day groupings with no stated independence justification. This run keeps
   the same descriptive grouping (renamed `n_candidate_blocks`, now 4,275 under the corrected
   denominator) but does **not** claim these are independent weather processes — see OR1b in
   `EXECUTION_STATUS_v17.md`, still open.

None of the above claims that the original numbers were fabricated — they were the direct,
reproducible output of the described code defects, now fixed. Both the defect and the fix are
covered by regression tests (`tests/test_revision_receipt_order.py`,
`tests/test_revision_ledger.py`, `tests/test_transition_census_v17.py`,
`tests/test_v17_a2_integration.py`).

## Access boundary and read scope (exact)

- Input: the 140 already-allowed TAF `station-month` `.body`/`.json` pairs under
  `data_real_v16/taf/20260920T134949Z_1bbe63aedc00_dl3rbulk/` — the same fixed allow-list used
  in every prior batch. No file outside this set was read. 2025-02 (the entire month, not just
  the protected sub-window) remains fully excluded, per hard boundary #4.
- File integrity: **140/140 verified** (sha256-matched against `input_readset.jsonl`), 0
  missing, 0 mismatched.
- `quarantine_holdout/` and the protected window `[2025-02-17T00:00:00Z, 2025-02-24T00:00:00Z)`:
  not read. (One `find` command during A2-6 development briefly traversed into
  `quarantine_holdout/` and printed a single directory-name line before being caught and
  corrected — no file content was ever opened. Disclosed in full in `BATCH_A2_PROGRESS.md`
  A2-6 and in the final A2 report; all subsequent scans use `-path .../quarantine_holdout -prune`.)
- No ASOS/METAR file was read; no outcome/label module was imported by the census or witness
  scripts (verified by import-list inspection each time; a stricter runtime `sys.modules` check
  was additionally run for the A2-6 census script but not re-run for the A2-7 witness script —
  disclosed as a minor asymmetry, not corrected by re-running to keep this report's claims
  matched to what was actually executed).

## Run record

```
cd $CODE && PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/run_transition_census_v17.py \
  --out artifacts_v17/ba2_20260921T202507Z/census_full_run
```
Started: 2026-09-21T20:26:53Z, finished: 2026-09-21T20:43:14Z. Wall time: `16m20.544s`
(`real`), `15m53.243s` (`user`), `10.579s` (`sys`). **Exit code: 1.** This exit code is by the
script's own contract the expected non-error signal that `UNRESOLVED` slots exist (i.e. "ran to
completion and found real conflicts needing disclosure/review"), not a crash — the run's own
stdout (`census_full_run_stdout.txt`) shows all 6 steps completing and writing every declared
output file, and `census_summary.json` is fully populated and internally consistent with the
stdout trace. This is stated as a fact, not re-derived from a separate assertion — if a future
reader wants to confirm the exit-code contract, see the script's own exit-code branch in
`scripts/run_transition_census_v17.py`.

## Results (full continuous calendar, denominator = 17,420 four-times-daily slots)

Sampling: "四时次日历采样" — 4 stations (KDEN, KJFK, KORD, KSFO) × 35 allowed months ×
{00Z, 06Z, 12Z, 18Z} × 1-hour target support window.

| Slot status | Count | / 17,420 |
|---|---|---|
| NO_INPUT | 0 | 0.0% |
| NO_APPLICABLE_EVIDENCE | 348 | 2.0% |
| INITIAL_ONLY_NO_CHANGE | 16,743 | 96.1% |
| IN_EPISODE_CHANGE | 292 | 1.68% |
| UNRESOLVED | 37 | 0.21% |

Calendar-level exclusions (protected window / unallowed month, tracked separately, not folded
into the 17,420): **116**, all `protected_window` reason, all inside the excluded 2025-02
range — consistent with hard boundary #4 (no file for 2025-02 was in the 140-file input set to
begin with; these 116 are slots whose *calendar position* falls in the excluded window, logged
for completeness of the continuous calendar, not evidence of any 2025-02 file access).

Changes by type (all 226,930 change records across all slots, not just IN_EPISODE_CHANGE ones):

| change_type | Count |
|---|---|
| AMD | 121,859 |
| INITIAL_BASELINE | 102,369 |
| COR | 2,687 |
| mirror_duplicate | 15 |

Checkpoint classification (same 226,930 records):

| checkpoint_classification | Count |
|---|---|
| INITIAL_PREFIX | 206,579 |
| INTERVAL_2 | 14,899 |
| AFTER_LAST_SCORE | 5,283 |
| INTERVAL_1 | 169 |

Relation/dispute status:

| relation_status | Count |
|---|---|
| resolved | 124,500 |
| not_applicable | 102,384 |
| unresolved | 46 |

All 46 `unresolved`-relation change records have `relation_reason=bbb_contradicts_receipt_order`
— i.e. every genuine dispute found in the real 140-file corpus is attributable to the same root
cause the A2-2 fix targets (equal-BBB records whose receipt order and BBB-implied order
disagree), not to a variety of unrelated data problems. These 46 change-level records map to
the 37 `UNRESOLVED` slots above (a slot can have more than one contributing unresolved change).

Process groups (descriptive station/issue-day grouping, **not** claimed to be independent
weather processes — see OR1b): 275 total — KDEN 92, KJFK 49, KORD 45, KSFO 89.

Compilation: 41,386 TAF packages compiled from the 140 files, 60 frames skipped
(malformed/unparseable — not investigated further this batch; see "Not investigated" below).

## Answer to the batch's core scientific question

*"For a fixed future weather target, how much legitimately visible, relevant, verifiable new
evidence actually changes between the T-60/T-40/T-20 scoring checkpoints, in the real 140-file
corpus?"*

Out of 17,420 continuous-calendar target slots: **292 (1.68%) have at least one legitimate
evidence change that is genuinely new between checkpoints** (`IN_EPISODE_CHANGE`), and a further
**37 (0.21%) have a genuine unresolved-authority conflict** among candidate predecessor records
at some checkpoint (`UNRESOLVED`). The overwhelming majority, **16,743 (96.1%)**, have only their
initial baseline evidence and no further legitimate change across any checkpoint transition —
i.e. real checkpoint-to-checkpoint evidence churn is rare but non-zero and traceable to specific,
byte-identifiable source records (see `LABEL_QUALIFICATION_v17_A2.md` / the A2-7 witness package
for 26 such records resolved to exact byte offsets).

A concrete real illustration (not a synthetic example) is in
`artifacts_v17/ba2_20260921T202507Z/witness_v1/episode_illustration.json`: for station KORD,
target validity 2023-01-01T12:00–13:00Z, checkpoints T-60=11:00Z/T-40=11:20Z/T-20=11:40Z — at
T-60 and T-40 the scorer legitimately sees only the first 4 of 7 real candidate records; two
more (`INITIAL_BASELINE` issued 11:31Z/available 11:33Z, and `COR` issued 11:35Z/available
11:37Z) cross their `available_at` threshold strictly between T-40 and T-20 and become newly
visible exactly at T-20; a seventh record (`AMD` issued 12:18Z/available 12:20Z) never becomes
visible at any of the three checkpoints and is correctly excluded as `AFTER_LAST_SCORE`.

## Known incompleteness in the input corpus (disclosed, not fixed this batch)

Two of the 140 allowed station-months (`KDEN_202506`, `KORD_202306`) were previously identified
(A2-6, citing `RECONCILIATION_DL3R.md`) as having incomplete backfill relative to their sibling
months for the same station — i.e. these two files are genuinely part of the allowed 140-file
set and were fully read and verified (their sha256 matches the receipt), but the *content*
itself is known to under-represent the true issuance stream for those two months. This is not
corrected in this batch (would require a new download, forbidden by hard boundary #6) and is
carried forward as an open caveat: the 292/37 counts above may be a slight undercount
specifically for those two station-months.

## Not claimed

- G1 is **not** claimed PASSED or FAILED by this report. Per the A2 plan's exit rule, the
  instrument is closed (A2-1 through A2-5 tests pass, A2-6 real run completed cleanly with
  perfect file integrity) and one traceable real run has been produced — this places G1 at
  **PENDING_INDEPENDENT_REVIEW** (see `EXECUTION_STATUS_v17.md`), not PASSED. No human has yet
  reviewed the A2-7 witness package.
- `target_content_change` is `UNASSESSED` on every record — this census counts *evidence
  record* changes (new/superseding TAF issuances becoming visible), not whether the actual
  forecast content changed in a way that would move a downstream score. That is an explicitly
  separate, unaddressed question this batch (no new meteorological projection logic was
  written, per the plan's scope).
- The 292/37 figures are a full census of the 140-file allowed corpus, not a statistical sample
  — no claim is made about what a larger corpus (e.g. including 2025-02) would show.
- Process-group independence (OR1b) and positive-label statistical power (OR1a) remain open
  and are not addressed by this Y-blind census; see `EXECUTION_STATUS_v17.md` Open Risks.
