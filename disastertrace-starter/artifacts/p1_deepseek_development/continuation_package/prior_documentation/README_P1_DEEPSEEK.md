# P1 DeepSeek development experiment and restart recovery

Date: 2026-09-06. The original experiment was interrupted by a machine restart.
It admitted 79 of 90 planned requests and saved 78 responses. Attempt 79 has no
saved response or usage; 11 requests were never admitted. The original files
remain unchanged. Offline finalization, independent audit and reporting are
complete with all 90 planned scoring opportunities retained.

This is an incomplete, descriptive development comparison. In particular,
answer_history's unattempted Dorian checkpoints are missing observations, not
observed model errors. Do not rank the three methods using these partial rates.

## Actual coverage and results

Model: deepseek-v4-flash, high reasoning, thinking enabled, max_tokens=4096,
temperature omitted. The fixed order is snapshot, structured_state,
answer_history. Each method has three development storms (Ida, Florence,
Dorian), two branches and five checkpoints per branch. There are no heldout
calls, no reused answers from the earlier ten-response trial, no new per-item
human annotation and no LLM judge.

| Method | Admitted / received | Schema valid / planned | V2 known grounding | V2 overall grounding |
| --- | --- | --- | --- | --- |
| snapshot | 30 / 30 | 14/30 | 39/96 (40.625%) | 69/150 (46.00%) |
| structured_state | 30 / 30 | 30/30 | 96/96 (100.00%) | 150/150 (100.00%) |
| answer_history, interrupted | 19 / 18 | 14/30 | 44/96 (45.83%) | 70/150 (46.67%) |

Known grounding requires the correct known value and a citation accepted by the
frozen evidence policy. Overall grounding also includes required unknown fields.
All invalid, uncertain and unattempted checkpoints remain in their denominators.
The full metric/event/branch tables, latency and input bindings are in
`work/p1-deepseek-development-v1-interrupted-finalization/report/REPORT.md` and
the adjacent `report.json`. Paired differences there are descriptive arithmetic;
the interruption prevents a complete method comparison.

### What the observed failures mean

Snapshot has 16 invalid answers: 14 hit the output limit (12 empty final answers
and two partial JSON answers), one uses an object for action, and one swaps the
state/action structure. The 14 valid answers have correct values/statuses on all
70 fields. One citation fails: Florence/delay c2 reports the correct 45 mph wind
but cites advisory 009 line 18, a movement-speed line, instead of the wind line
17. The frozen policy labels this evaluator_unverifiable; the concrete observed
problem is the locator, not a wrong wind value.

Structured_state has 30 valid answers with 150/150 value/status and grounded
fields. Its fixed Gold changes, preservation and provenance refresh are
64/64, 56/56 and 8/8. Self-error recovery has no opportunities (0/0, undefined).

Answer_history has 14 valid and four invalid received answers; all four invalid
answers (Florence/base c0-c3) exhaust 4096 reasoning/output tokens with empty
final content. All 70 fields in the valid answers are correct and grounded.
Its other 12 planned answers consist
of one uncertain in-flight request and 11 unattempted checkpoints. Valid-only
figures here are secondary diagnostics, not replacements for the planned
denominators or evidence about the missing answers.

The public prompt implies action labels through the policy but does not state
the action's string type explicitly. Previous valid answers also supply format
examples to the two carrier methods. This is a plausible contributor to method
differences that needs a separate controlled test. All methods receive cumulative
delivered evidence, so the experiment does not isolate memory dependence.

V1 and V2 scores are both retained. Overall grounding is 65/150 versus 69/150
for snapshot, 139/150 versus 150/150 for structured_state, and 70/150 in both
versions for the partial answer_history run. These are evaluations of identical
saved answers using rules frozen before this batch, not model improvements.

## Usage, cost and interruption accounting

The 78 received responses report 255,491 prompt tokens and 145,407 completion
tokens, totaling 400,898. The 135,081 reasoning tokens are already included in
completion tokens. Cache hits total 135,296 prompt tokens and misses 120,195.

Using the captured Sunday prices, the received-response cost subtotal is
USD 0.123358592: snapshot USD 0.066161104, structured_state USD 0.022414064,
and the received answer_history prefix USD 0.034783424. The full experiment's
cost is unknown because attempt 79 has no returned usage. These are estimates,
not provider billing receipts.

The original conditional USD 1 guard retains USD 0.46678016 for the uncertain
request, in addition to USD 0.30435328 conservatively settled at peak rates.
Its remaining allowance is USD 0.22886656. One new request would require total
reserved accounting of USD 1.23791360, so the original guard cannot admit it.
The retained reservation is not a measured charge.

Mean transport latency for received responses is 19.832 seconds (snapshot),
6.782 seconds (structured_state), and 13.980 seconds (answer_history prefix).
The timer covers the HTTP transport through receipt of response bytes; it
excludes parsing, scoring and setup. Fixed execution order and provider caching
confound speed/cost comparisons. There is no latency measurement for attempt 79.

## Preserved artifacts and offline recovery

- Original capture: `work/p1-deepseek-development-v1/`.
- Frozen experiment and protocol: `artifacts/p1_deepseek_development/experiment.json`
  and `artifacts/p1_deepseek_development/PROTOCOL.md`.
- Independent interruption audit: `artifacts/p1_deepseek_development/interruption_audit/result.json`.
- Detached offline finalizer, tests and actual command/exit records:
  `artifacts/p1_deepseek_development/interruption_recovery/`.
- Derived partial run, rescore and report:
  `work/p1-deepseek-development-v1-interrupted-finalization/`.

The original running/pending flags reflect an unfinalized capture; they do not
mean the old process is still running. Its exit code and precise termination
time were not observed and are not invented. The finalizer preserves all 19
answer_history requests, 18 responses and 18 received-outcome records. It adds
one explicitly labeled local administrative interruption disposition in a NEW
collection so the existing audit/import/scoring pipeline can close the record.
The legacy schema calls it provider_error, but no DeepSeek error response was
captured. `interruption_finalization.json` records provider_returned_error=false.
The original ledger and its pending reservation remain unchanged.

Completed method directories in the derived package are read-only input aliases
to the preserved originals. The partial answer_history directory is a separate
derived copy. The finalizer adds no model response, makes zero API calls and
passes the original independent audit, trace binding and v1/v2 verification.

The core implementation retains its previously verified 611-test identity. P1
runner and reporter checks passed 37 and 14 tests respectively; recovery adds
10 passing focused tests. These are separate test executions, not a newly run
single combined suite. All 177 protected historical files and all 83 files in
the original P1 capture are unchanged. Recovery and report commands exit 0.

The closed partial experiment is archived in
`artifacts/p1_deepseek_development/partial_package/`. Its manifest binds 246
files, including immutable copies of these then-current entry documents.
Verification of all 247 SHA256SUMS entries (including the manifest) exits 0.
Later background-continuation preparation is a separate package and does not
rewrite this archived partial result.

Recheck the partial derived score offline:

```bash
.venv/bin/python -m disastertrace.automated.rescoring verify --output work/p1-deepseek-development-v1-interrupted-finalization/rescores/answer_history
```

Regenerate the report into a fresh output directory, with zero model calls:

```bash
.venv/bin/python artifacts/p1_deepseek_development/report_results.py \
  --experiment artifacts/p1_deepseek_development/experiment.json \
  --runs-root work/p1-deepseek-development-v1-interrupted-finalization/runs \
  --rescores-root work/p1-deepseek-development-v1-interrupted-finalization/rescores \
  --rates artifacts/p1_deepseek_development/docs/rates.json \
  --output work/p1-partial-report-recheck-001
```

## Background continuation and next calibration

The user requests background resubmission after the restart. The concrete
amendment proposal is `artifacts/p1_deepseek_development/restart_proposal.json`:
USD 1.5 cumulative allowance, at most 12 additional requests, explicitly retry
only the one uncertain request, and at most 91 cumulative provider attempts.
The 78 received answers, including every invalid answer, are retained. This
requires confirmation because the previous experiment fixed USD 1 and no
retries. No additional API calls have been made during offline recovery.

The continuation implementation is now prepared and frozen under
`artifacts/p1_deepseek_development/background_resume/`. Its final 22 offline
tests pass in 43.30 seconds, including a full simulated continuation and
independent scoring; lint and formatting also pass. `prepared/amendment.json`
binds the source and prefix, and `offline_checks.json` records verification.
The continuation worker has not been launched. Its README gives the exact
one-use launch command and required actual-authorization record.

A continuation must keep the original partial experiment, uncertain attempt
and reservation intact; freeze a separate amendment; use a detached process
with durable logs/PID/exit status; and label any resulting comparison as an
amended continuation. A total of 91 attempts would still contain only 90
benchmark answer opportunities and one unresolved original attempt.

After recovering the experiment, prioritize a new, explicit public output
contract shared by all methods and a predeclared output-budget comparison.
Then extend the controlled track with partial updates, same-window corrections
and recoverable missing evidence. Keep the current seven heldout storms unused
while designing those changes, and preserve deterministic references/scoring
without introducing per-item human review or an LLM judge.
