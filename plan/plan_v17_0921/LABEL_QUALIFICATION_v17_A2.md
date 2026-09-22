# Label Qualification v17 — Batch A2 Corrected Report

Generated: 2026-09-21T21:00:06Z
Supersedes: `LABEL_QUALIFICATION_v17.md` (original V17-03 report) for the purpose of
TAF source-label / lineage qualification. That report's original 15-sample AI-re-read
(fixed seed 20260921) is preserved unchanged below its new pointer note; it is not deleted,
and its own honestly-stated `PENDING_HUMAN_VERIFICATION` status is not altered.

**Scope reminder (unchanged from the original report, restated because it was previously
mis-cited elsewhere in this repo — see OR1c in `EXECUTION_STATUS_v17.md`): this document
qualifies TAF AMD/COR/lineage source-record classification. It says nothing about ASOS/METAR
outcome (Y) labels, which are a separate, untouched concern under hard boundary #5.**

## What is new in A2 vs. the original report

The original report's qualification method was a 15-item AI self-re-read of already-classified
records, with no byte-level traceability back to the original archive text, no separation of
"what does the record objectively contain" from "does the program's classification agree,"
and no explicit representation of the structural change-type taxonomy (regular AMD/COR vs.
late-arriving vs. duplicate vs. adjacent-history vs. cross-window vs. conflict/unknown).

This A2 report instead points to a purpose-built **witness package**
(`artifacts_v17/ba2_20260921T202507Z/witness_v1/witnesses.jsonl`, 30 items) built by
`artifacts_v17/ba2_20260921T202507Z/a2_7_witness_select.py` directly from the A2-6 real
`census_full_run/` output (`all_changes.jsonl`, `slot_summary.jsonl`, `input_readset.jsonl`)
and the same 140 already-allowed real body files — no new file was read, `quarantine_holdout/`
was not touched, and no ASOS/METAR/outcome module was imported (verified by inspecting the
script's own import list; not re-verified via the stricter runtime `sys.modules` check that
A2-6 additionally applied to its own script — disclosed as a minor asymmetry, see
`TRANSITION_CENSUS_v17_A2.md`).

### Selection method (structural, not outcome-based)

Every witness was chosen by a fixed field-value bucketing of `all_changes.jsonl` records
(`change_type`, `relevance_tier`, `checkpoint_classification`, `relation_status`,
`dispute_status`), taking the first N distinct `(target, current_source_id)` records per bucket
**in file order** — file order follows the census script's fixed station/date iteration, never
any outcome, model-agreement, or model-error ranking. This satisfies hard boundary #5 ("不按
结果、模型输赢或模型错误选样") by construction: the script never imports or reads any
outcome/label module.

### Coverage — all 7 plan-named witness types present (none absent)

| witness_type | count | stations covered |
|---|---|---|
| regular_amd | 4 | KSFO |
| regular_cor | 2 | KORD, KSFO |
| late_arriving | 4 | KJFK, KORD, KSFO |
| duplicate | 4 | KSFO |
| adjacent_history | 4 | KSFO |
| cross_window | 4 | KDEN, KORD, KSFO |
| conflict_unknown | 4 | KJFK |

Plus **4 slot-level "no change" witnesses** (2 `INITIAL_ONLY_NO_CHANGE`, 2
`NO_APPLICABLE_EVIDENCE`) — **30 witnesses total**. Full counts machine-verifiable in
`artifacts_v17/ba2_20260921T202507Z/witness_v1/selection_report.json`.

**Disclosed limitation — station skew.** Because "first N in file order" is deterministic but
not station-balanced, four of the seven change-level buckets concentrate on a single station
(`regular_amd`/`adjacent_history`/`duplicate` → KSFO only; `conflict_unknown` → KJFK only).
This was a known and accepted tradeoff, not corrected by re-sampling: re-sampling for station
spread would itself be an undisclosed additional selection criterion beyond "first in file
order," and station diversity was not a stated A2-7 acceptance criterion in the approved plan.
A reviewer relying on this package for station-level generalization should treat the skewed
buckets as single-station case studies, not cross-station samples.

### Traceability — byte identity

Each change-level witness record carries a `byte_identity` field giving the exact source body
file, byte offset range, and a short text preview of the original AFOS/TAF frame it was
compiled from. This was computed by reimplementing the production `split_afos_stream` SOH/ETX
framing logic at the byte level (the production function only returns decoded strings, not
offsets) and matching each witness's `current_source_id` to its compiled package's
`receipt_seq`, then to a frame index, then to a byte range — using only the same already-allowed
body files already verified in `input_readset.jsonl`.

Result: **26/26 (100%) of change-level witnesses resolved to an exact byte range.** (The 4
slot-level "no change" witnesses have no single source record to resolve to a byte range by
construction — they represent the *absence* of a qualifying change, not a specific record —
and are not counted in this denominator; see `selection_report.json`'s
`byte_identity_resolved_count: 26` / `byte_identity_unresolved_count: 4`, where the 4 unresolved
are exactly those 4 no-change witnesses, not failures.)

Example (`witness_type=conflict_unknown`, station KJFK, `current_source_id=
KJFK-1688894520000000-277d4d5a3b90`): resolved to `KJFK_202307.body`, byte range
`[71031, 71467)`, frame preview beginning `FTUS41 KOKX 090922 AAB / TAFJFK / TAF AMD ...`.

### Record structure

Each of the 30 witness records in `witnesses.jsonl` separates the **objective record data**
(station, target support window, `current_source_id`, `candidate_predecessors`, issued/available
timestamps and basis, three-checkpoint visibility booleans, byte identity, and the program's
own rule-basis fields: `change_type`, `relevance_tier`, `checkpoint_classification`,
`relation_status`, `relation_reason`, `dispute_status`) from the **review apparatus**
(`review_question` — a plain-language question for a human reviewer; `program_answer` — what
the program concluded; `independent_judgment` and `disagreement_notes` — both `null` on every
record; `status` — `"PENDING_INDEPENDENT_REVIEW"` on every record). This separation exists
specifically so a future independent reviewer can answer `review_question` from the
`byte_identity` source text alone, without being anchored by `program_answer`, and then record
agreement or disagreement explicitly.

## Status

**`PENDING_INDEPENDENT_REVIEW` on all 30 witnesses.** No human has reviewed any of them this
batch (per the original A2 instruction, no reviewer was online / no additional agent was
launched to perform review — launching an additional review agent would itself violate hard
boundary #7). This report is **not** a claim of qualification passed; it is a claim that the
*instrument* for qualification is now byte-traceable, structurally diverse across all 7 planned
types, and Y-blind by construction — an improvement in verifiability over the original 15-sample
AI-re-read, not a substitute for actual independent review.

## Recommendations for independent human verification (carried forward, updated)

1. Review all 30 items in `witnesses.jsonl`, focusing first on the 4 `conflict_unknown` items
   (all KJFK — genuine `bbb_contradicts_receipt_order` disputes) and the `episode_illustration.json`
   real multi-checkpoint example, as these most directly bear on the batch's core question.
2. For each item, read the `byte_identity` source range independently before reading
   `program_answer`, and record agreement/disagreement in `independent_judgment`/
   `disagreement_notes`.
3. Treat the station skew (above) as a known gap — a follow-up batch should either explicitly
   accept single-station case studies for those 4 types or authorize a station-balanced
   re-selection as a *new*, explicitly-disclosed selection criterion.
4. The 60 skipped compilation frames (out of 41,386 packages) and the KDEN_202506/KORD_202306
   backfill-incompleteness caveat (see `TRANSITION_CENSUS_v17_A2.md`) are not represented in
   this witness package and remain open items for a future batch.
