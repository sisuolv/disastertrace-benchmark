# DisasterTrace v20: next-steps plan (merged from three independent reviews)

Drafted after three independent ChatGPT Pro review passes of commit `7bb03fbf7` (branch
`codex/v18-repaired-release-20260923`), each producing its own findings, revised plan, and
Codex-handoff task list. All three converged on the same top-priority finding — the published
commit was broken (see Horizon 0) — plus a long list of specific, executed, reproducible findings
about the v18 checkpoint pipeline, the repair mechanism, and the A2 census script. This document
merges those three reviews with the parent Claude session's own direct verification and an
independent Opus 5.5 critique of the merge itself (not of the code — of the plan). Nothing in this
document authorizes real data, real API, or holdout access.

## Confirmed working (do not re-do)

The T-60/T-40/T-20 checkpoint structure, real `relation_status` computation, repair no longer
copying future content directly, same-policy-object rejection, within-call RNG restoration, TAF
interval-clipping fixes, and the A2 month/signal/ledger-error fixes were each independently
reproduced by at least two of the three reviews. These are real, verified progress.

## Horizon 0 — release integrity (done)

Fixed as commit `f30c3d247`: 16 files (3 source modules, 4 scripts, 9 test files) had never been
committed at any point in this project's history, breaking imports in already-published code
(`run_v18_controlled_api.py` imported `agent_view_v18`, which did not exist in the published tree).
Verified via a fresh, isolated worktree checkout — 177 tests pass. Remaining: one independent review
call (not the same session that made the fix) should confirm this, and record the actual collected/
passed/failed/skipped counts and node IDs rather than treating "177" as a number to carry forward
unexamined.

## Horizon 1 — offline work, no new authorization needed

### Track B-0 — shared field-classification contract (must land before Track A item 1)

**New finding an independent Opus 5.5 review caught that all three ChatGPT Pro reviews missed**: the
bug where content hashing mixes in non-weather metadata fields is not confined to this round's own
`build_v18_dev_episodes.py::_periods_content_hash` — it also affects
`evidence_qualification_v18.py`'s `_NON_TARGET_KEYS` set (currently `{non_target, formatting,
transport, debug, length_sham, raw}`, missing `is_amendment`/`ftype`/`source_row_is_tempo`), so
`target_content_projection` and `qualify_evidence`'s `TARGET_CONTENT_CHANGE` /
`SOURCE_CHANGE_NO_TARGET_CHANGE` / `DUPLICATE` classification is contaminated by the same root cause.
Suggestive (not proof) evidence: the already-committed `review/v18_execution_20260923/
G1_DEV_EPISODES_V2.json` shows exactly 24 `NEW_TARGET_CONTENT` + 24 `TARGET_CONTENT_CHANGE`, zero
`SOURCE_CHANGE_NO_TARGET_CHANGE`/`DUPLICATE` — consistent with `is_amendment` flipping between
consecutive products and being misread as content change every time. Cheap test: strip these three
fields from G1's `qualify_stream` input and recount.

Deliverable: one shared field-classification constant (weather-semantic vs. administrative metadata),
imported by both `build_v18_dev_episodes.py` and `evidence_qualification_v18.py` — not two
independently-written whitelists, which is exactly how the next self-attribution error happens. Until
this lands, every `target_content_change_rows` figure already in G1 is `PENDING_REVALIDATION` and
should not be cited.

Track B-1 (frozen temporal measurement contract) follows: T-60 baseline state definition, the two
T-60→T-40 / T-40→T-20 diffs, changed-then-reverted events tracked separately from net-zero change,
CNL/NIL lifecycle handling, ~12 required synthetic test cases (per one review's list). Writable and
testable now with synthetic data, no D1 needed. Also formally retract the "292 to 14,803" range as a
bound on target-content change; replace with four counted categories — `A` (arrived), `V(R)` (version
revision), `C` (genuine content change), `U` (unknown) — each with an explicit denominator.

### Track A — small deterministic fixes, batched with checkpoints (not one bulk change)

**Batch 1** (changes G1 numbers; depends on Track B-0):
1. Duplicate-detection content hash — rewrite using Track B-0's shared constant.
2. CNL rows filtered out before cancellation-text classification even sees them
   (`_load_products`'s `if row.get("product_id") and row.get("fx_valid")` runs before
   `_has_cancellation_text`). Independent review added a required step 0: characterize whether the
   IEM pyIEM TAF CSV export can represent a CNL product at all (it's emitted per forecast period; a
   true CNL bulletin may have no periods and simply be absent from the export, not
   present-but-filtered). No test currently exercises `_has_cancellation_text`/
   `_classify_relation_status` at all — confirmed by search (`tests/test_monitoring_aviation.py:224`
   and `tests/test_v17_transition_census.py:120,190` cover CNL detection elsewhere, via `parse_taf` on
   raw text — a *different* pipeline reading a *different* input shape — but nothing covers the v18
   builder's own CSV-based path). **Before retracting or reaffirming "0 CNL observed," identify which
   pipeline that claim actually came from**: if it came from the v17 census (which reads raw TAF text
   via `parse_taf` and could plausibly see a CNL bulletin), the claim may still hold for that source;
   if it came from the v18 builder (which reads per-period CSV rows and structurally may never see
   one), the claim means nothing and should be restated as "this data source cannot represent CNL,"
   which is a different, more honest statement than "zero CNL observed." Add a synthetic acceptance
   test: a CSV body with a product row that has no `fx_valid` and has `CNL` in `raw` — assert the
   result is either `relation_status == "cancellation"` or an explicit `ExclusionRecord`, never a
   silent drop (same pattern as item 4's fix). **Scope stays within the existing authorized dev
   readset** (`STATIONS=(KDEN,KJFK,KORD,KSFO)`, `ALLOWED_MONTHS=(202501,202503)`, same `build_roster`
   entry point, same holdout exclusion) — this is not a license to scan the full 17,088-target
   archive; that is Horizon 2 / D1.
3. `[:8]` cap truncates *before* chronological sorting, so which record gets dropped depends on
   `source_id` string insertion order, not time. Sort first, then decide whether/how to truncate; if
   truncating, emit an `ExclusionRecord` with a reason instead of silently dropping.
4. `_group_operator` collapses `"PROB30 TEMPO"` into `"PROB30"`, losing the TEMPO qualifier.

Checkpoint: regenerate G1 and diff `status_counts` before/after — the diff itself is the evidence of
what the bug was doing, not a self-report.

**Batch 2** (changes G3 semantics; depends on Track C's ADR settling policy-visibility scope):
5. `identity_repeat`'s inconsistent result (`records` unchanged but `qualification` reports a phantom
   `DUPLICATE` row not present in `records`) — pick true-no-op or keep-and-disclose, decided by
   Track C's ADR on policy visibility.
6. `delay` intervention's `None`-handling: real timestamps trigger `available_at cannot precede
   issued_at` and crash (not a silently fabricated 24h-later time, as earlier described — only tiny
   synthetic test timestamps make it look like it "works"). The 24h constant itself is fine; only the
   `None` coalescing needs fixing — name the constant, raise or return `NOT_APPLICABLE` on `None`.
7. Chronology check only compares adjacent pairs, so `[20, None, 10]` passes; check the whole
   sequence.
8. `_repair` accepts an `as_of` inconsistent with the snapshot's own `clock`, with no target binding —
   add a consistency check at the entry point.

Checkpoint: the three review packages' own executed synthetic-reproduction scripts
(`/tmp/v20_review/run*/`, ephemeral — regenerate locally as needed) already exist and are free,
independent tests — re-run them after Batch 2 rather than writing new ones from scratch.

**Batch 3** (census script hygiene — independent review found these mostly already done, smaller
scope than originally assessed):
9. Exit-code ambiguity is narrower than described: `LedgerCompilationError` and hash/file-integrity
   failures already return exit code 2; UNRESOLVED already returns 1. The only real gap is an
   uncaught exception defaulting to Python's exit 1, colliding with the UNRESOLVED case. Fix: one
   `try/except Exception` wrapper returning a distinct code (e.g. 3) plus a `status` field in the
   summary JSON — not a five-state enum.
10. Historical-vs-in-window unresolved is already split: `FLAG_UNRESOLVED_IN_INITIAL_PREFIX` /
    `FLAG_UNRESOLVED_IN_SCORING_WINDOW` already exist, with a docstring explaining why the single
    `UNRESOLVED` status is kept with these as sub-flags. Verify these flags actually reach the
    summary JSON and downstream consumers; close as done if so.

### Track C — repair-mechanism architecture decision record (concrete template, not open-ended)

Independent review clarified: the mechanical fix for "policy never observes retrieved content" is
small — `NaturalKernel.step()` already returns `content`; `replay_suffix` just doesn't forward it into
`public_state()`, and the kernel's own `self.read` already holds it. The real work is a design
decision, not a big build.

File: `docs/adr/ADR-001-repair-isolation-and-visibility.md`. Must answer these five questions, each
with a one-line rationale:
1. Does `public_state()` expose read-cache content, `last_result`, or both?
2. Is the policy signature `policy(state)` or `policy(state, last_result)`?
3. Should `_repair` require `as_of == snapshot["clock"]` and bind `target_start`/`target_end` into
   the snapshot schema (a `SNAPSHOT_SCHEMA` version bump)?
4. Is process-fork isolation deferred permanently, or gated on a named trigger?
5. Is `deepcopy` of built policies rejected permanently? (Record the three reviews' reasoning
   verbatim: functions/closures/client objects aren't truly copied, and in-process forking doesn't
   clear state a parent process already polluted.)

Include a "what this ADR does not certify" section, mirroring the existing `policy_isolation` witness
fields in `interventions_v18.py`. Explicitly not doing: `deepcopy` as a quick patch for B-1's
remaining leak patterns.

### Track D — Y1 settlement adapter (synthetic-only; real Y stays blocked)

A thin adapter mapping the frozen v18 target contract onto the merged
`revision_v1/outcome_wiring.py`'s Target/OutcomeRegistry structures, reusing its pure resolution
logic (`resolve_h15_outcomes`) rather than treating it as an opaque black box or rewriting from
scratch. Independent review found sub-hour adaptation is smaller than assumed — `
make_h15_visibility_target` is already microsecond-precise; callers just need to pass an explicit
`target_id`. Real gap that must be addressed: `resolve_h15_outcomes` currently classifies everything
as `mature`, with no real `provisional` state — needs an outer state machine or a "final-archive
freeze" policy.

Mechanical synthetic-only guards (so this adapter can't later be mistaken for real-data-validated):
module name itself contains `synthetic` (e.g. `revision_v1/y1_adapter_synthetic.py`); every emitted
outcome record carries `availability_basis="synthetic_fixture"` and
`provenance.source_revision="SYNTHETIC"`; a test asserts `resolve_h15_outcomes` is never called with
an `AsosProvenance` whose sha256 matches a tracked receipt; the module docstring states plainly that
no real-data adapter exists yet; the adapter may import only pure functions from
`revision_v1.outcome_wiring`, nothing ASOS-fetch-related.

### Track E — offline end-to-end acceptance gate (builds on existing infrastructure, not greenfield)

`scripts/build_v19_offline_gate.py` (qualify → public_checkpoint → grid) and
`scripts/offline_guard/sitecustomize.py` (`DISASTERTRACE_OFFLINE=1` network guard) already exist.
Extend the existing gate with roster construction, a fake provider, and synthetic outcome settlement,
running under the existing guard — this is not a new design.

Closed-run-id protection is currently filesystem-presence-only (`run_v18_controlled_api.py` checks
whether `--out` already has a `CLOSED` marker or sidecar) — none of the closed v18 run artifacts are
tracked in git, so a fresh clone has zero protection for the 3 already-closed run-ids. Add a
git-tracked registry (e.g. `configs/closed_run_ids.json`) the runner consults at startup. The gate
should also assert `api_capture.py` (which reads a real key-file path by default) is never imported,
rather than relying on the network guard to catch it after the fact.

### Minor findings (low priority, non-blocking)

- The controlled-runner's incremental `responses.jsonl` sidecar stores only `response_sha256`; the
  parsed response content is written only at the very end. A mid-run crash loses the content of every
  response received so far. (Correction: `api_capture.py` itself does persist full redacted response
  bodies — the gap is specific to `run_v18_controlled_api.py`'s own incremental sidecar.)
- `_classify_relation_status` resets its comparison hash at every station-month boundary, so the
  first product of each month can never be classified `duplicate`. Track B-1's contract should state
  explicitly whether cross-month continuity is in scope.
- Some status docs reference a `plan/` directory not locatable in the current worktree — a stale doc
  pointer, not a code issue; needs a human to check against history.

## Horizon 2 — unlock D1 (redefined: not "one number")

Not "narrow 292–14,803 into a point estimate." Using Track B-0/B-1's frozen contract, compute the
`A`/`V(R)`/`C`/`U` counts across all 17,088 real targets with explicit denominators and bounded
unknowns. Preparable now, before D1: freeze the counting protocol itself (three denominators, an
objective, reproducible rule for what counts as "routine" rather than an eyeballed judgment, a
template for unknown-quantity bounds) — write and validate this with synthetic data now, so D1
execution doesn't require on-the-fly methodology design.

## Horizon 3 — P1 → Y1 (order unchanged; Y1's offline design work already done in Track D)

First real model dispatch (new run-id, locked budget/model/stop-rule, never touching the 3 closed
runs); then settle real Y using Track D's adapter.

## Horizon 4 — L1/L2 (prospective / live data capture)

Two of three independent reviews pushed back on sequencing this strictly last: L1's scaffolding
(fake clock, the REGISTER→OPEN→...→SETTLED lifecycle skeleton, fully offline-testable) can proceed
in parallel during Horizon 1 — only the actual dispatch of real prospective data collection needs to
wait for authorization. Scaffolding proceeds in parallel; real execution stays gated behind D1/P1/Y1
plus separate authorization. One review also flagged: before asserting "neither codebase has any
live-fetch code," do a read-only inventory of collector/forward_capture code outside the tracked
repo, in case that premise itself is wrong.

## Horizon 5 — explicitly parked

Multimodal/second-domain generalization, holdout confirmatory analysis.

## Authorization boundary (unchanged, confirmed verbatim by all three reviews)

D1/P1/Y1/L1/L2/H2 remain `BLOCKED_EXPLICIT_AUTHORIZATION`. Nothing in this document auto-unlocks any
of them because a synthetic version now exists or because it would be convenient. Note: "Horizon 2"
in this document's own numbering is unrelated to holdout authorization `H2` — kept explicitly
distinct to avoid confusion in future documents.
