# P1 DeepSeek development comparison after authorized continuation

Date: 2026-09-06. The authorized background continuation completed successfully,
with 12 new requests and 90 saved benchmark responses across all three methods.
Both the launcher and detached worker exit 0. This completes an explicitly
amended development comparison; the original no-retry experiment remains
preserved as an interrupted partial capture.

There are 91 cumulative provider attempts: 90 with received responses and one
unresolved original attempt from the machine restart. The user explicitly
approved its single reissue and a USD 1.5 cumulative conditional allowance.
All 78 previously received answers, including 20 invalid answers, are retained
without being requested again. Model settings, evidence and scoring are unchanged.

## Actual coverage and results

Model: deepseek-v4-flash, high reasoning, thinking enabled, max_tokens=4096,
temperature omitted. The fixed order is snapshot, structured_state,
answer_history. Each method has three development storms (Ida, Florence,
Dorian), two branches and five checkpoints per branch. There are no heldout
calls, no reused answers from the earlier ten-response trial, no new per-item
human annotation and no LLM judge.

| Method | Responses / planned | Schema valid / planned | V2 known grounding | V2 overall grounding |
| --- | --- | --- | --- | --- |
| snapshot | 30 / 30 | 14/30 | 39/96 (40.625%) | 69/150 (46.00%) |
| structured_state | 30 / 30 | 30/30 | 96/96 (100.00%) | 150/150 (100.00%) |
| answer_history, continued | 30 / 30 | 24/30 | 76/96 (79.17%) | 120/150 (80.00%) |

Known grounding requires the correct known value and a citation accepted by the
frozen evidence policy. Overall grounding also includes required unknown fields.
All invalid answers remain in their planned denominators. No benchmark answer
opportunity is missing after continuation; the unresolved original physical
attempt remains separately counted and is not treated as an extra scored item.
The full metric/event/branch tables, latency and input bindings are in
`work/p1-deepseek-background-continuation-v1/report/REPORT.md` and the adjacent
`report.json`. Paired differences are descriptive arithmetic for three selected
development storms, one model and one repeat. No heldout ranking or statistical
significance is established, and the restart adds a further execution-time factor.

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

Answer_history has 24 valid and six invalid received answers. All six invalid
answers exhaust 4096 reasoning/output tokens with empty final content:
Florence/base c0-c3, Florence/delay c4 and Dorian/base c3. All 120 fields in its
valid answers are correct and grounded. Its fixed Gold changes, grounded
preservation and provenance refresh are 53/64, 42/56 and 7/8. Valid-only figures
are secondary diagnostics, not replacements for the planned denominators.

Across the three methods, 20 received answers hit the output limit and two have
structural JSON errors. All 68 schema-valid answers have correct values/statuses;
one citation fails. This identifies output delivery and contract clarity as
priorities for calibration. It does not establish factual performance for the
invalid answers or broad saturation of an extreme-weather benchmark.

The public prompt implies action labels through the policy but does not state
the action's string type explicitly. Previous valid answers also supply format
examples to the two carrier methods. This is a plausible contributor to method
differences that needs a separate controlled test. All methods receive cumulative
delivered evidence, so the experiment does not isolate memory dependence.

V1 and V2 scores are both retained. Overall grounding is 65/150 versus 69/150
for snapshot, 139/150 versus 150/150 for structured_state, and 120/150 in both
versions for answer_history. These are evaluations of identical
saved answers using rules frozen before this batch, not model improvements.

## Usage, cost and interruption accounting

The 90 received responses report 293,816 prompt tokens and 170,378 completion
tokens, totaling 464,194. The 158,370 reasoning tokens are already included in
completion tokens. Cache hits total 141,312 prompt tokens and misses 152,504.

Using the captured Sunday prices, the received-response cost subtotal is
USD 0.146989544: snapshot USD 0.066161104, structured_state USD 0.022414064,
and answer_history USD 0.058414376. The 12 new responses contribute
USD 0.023630952; the prior received-response subtotal was USD 0.123358592.
The full experiment's
cost is unknown because attempt 79 has no returned usage. These are estimates,
not provider billing receipts.

The amended conditional USD 1.5 ledger retains USD 0.46678016 for the original
uncertain request, in addition to USD 0.35417800 conservatively settled at peak
rates. Their sum is USD 0.82095816, leaving USD 0.67904184 of allowance. There
are no active new requests. The old reservation is not a measured charge and
was not released when its replacement received a response. All 79 original
ledger rows are unchanged in the cumulative ledger.

Transport latency in the report covers HTTP transport through receipt of response
bytes; it excludes parsing, scoring and setup. Fixed order, restart timing and
provider caching confound speed/cost comparisons. There is no latency observation
for the unresolved original attempt. All 90 responses return deepseek-v4-flash
and the same available system fingerprint; this does not authenticate an
immutable underlying model version.

## Preserved artifacts and offline recovery

- Original capture: `work/p1-deepseek-development-v1/`.
- Frozen experiment and protocol: `artifacts/p1_deepseek_development/experiment.json`
  and `artifacts/p1_deepseek_development/PROTOCOL.md`.
- Independent interruption audit: `artifacts/p1_deepseek_development/interruption_audit/result.json`.
- Detached offline finalizer, tests and actual command/exit records:
  `artifacts/p1_deepseek_development/interruption_recovery/`.
- Derived partial run, rescore and report:
  `work/p1-deepseek-development-v1-interrupted-finalization/`.
- Completed amended continuation: `work/p1-deepseek-background-continuation-v1/`.
- Authorization, frozen amendment, launcher and its 22 offline tests:
  `artifacts/p1_deepseek_development/background_resume/`.
- Independent continuation integrity and cost audit:
  `artifacts/p1_deepseek_development/continuation_audit/`.
- Final result, file manifest and immutable documentation snapshots:
  `artifacts/p1_deepseek_development/continuation_package/`.

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

The continuation reuses an independently audited 18-response answer_history
prefix and makes 12 new calls. Original attempt 79 is retained separately, and
the first new cumulative attempt (80) has its identical request hash. Distinct
checkpoints with identical payloads remain valid distinct opportunities. An
exclusive amendment claim prevents duplicate background launches.

The core implementation retains its previously verified 611-test identity. P1
runner and reporter checks passed 37 and 14 tests respectively; recovery adds
10 passing focused tests. These are separate test executions, not a newly run
single combined suite. All 177 protected historical files and all 83 files in
the original P1 capture are unchanged. Recovery and report commands exit 0.
The detached continuation's 22 tests passed before launch; the amended report
adds 23 passing tests in 7.24 seconds with lint/format checks. Its executed
command exits 0. Independent continuation audit passes 1,887 checks, including
exact prefix/ledger identity, authorization, per-request caps and cost arithmetic.
Final independent report review passes 372 checks; its inputs, source and output
hashes, all metric tables, timing and accounting match the saved results.

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

Regenerate the completed amended report into a fresh directory, with zero calls:

```bash
.venv/bin/python artifacts/p1_deepseek_development/continuation_report/report_continuation.py \
  --amendment artifacts/p1_deepseek_development/background_resume/prepared/amendment.json \
  --continuation work/p1-deepseek-background-continuation-v1 \
  --output work/p1-amended-report-recheck-001
```

Regenerate the original partial report into a fresh directory, with zero calls:

```bash
.venv/bin/python artifacts/p1_deepseek_development/report_results.py \
  --experiment artifacts/p1_deepseek_development/experiment.json \
  --runs-root work/p1-deepseek-development-v1-interrupted-finalization/runs \
  --rescores-root work/p1-deepseek-development-v1-interrupted-finalization/rescores \
  --rates artifacts/p1_deepseek_development/docs/rates.json \
  --output work/p1-partial-report-recheck-001
```

## Background continuation and next calibration

The user approved the concrete USD 1.5 / 12-additional / 91-cumulative amendment
and one explicit uncertain-request retry. The actual approval record is
`artifacts/p1_deepseek_development/background_resume/authorization.json`.
The original no-retry protocol and its partial report remain untouched.

The continuation implementation is now prepared and frozen under
`artifacts/p1_deepseek_development/background_resume/`. Its final 22 offline
tests pass in 43.30 seconds, including a full simulated continuation and
independent scoring; lint and formatting also pass. `prepared/amendment.json`
binds the source and prefix, and `offline_checks.json` records verification.
The one-use launch completed at 2026-09-06T16:38:46Z. Exact command, PID and
launcher exit code are in `background_resume/launch_command.json`; worker
`status.json`, `exit.json`, `execution.json` and `worker.log` are in the output.
The worker used PID/session 16909 and closed stdin. All 12 new calls completed
within the conditional allowance; no further request or retry is planned.

Next, prioritize a new, explicit public output
contract shared by all methods and a predeclared output-budget comparison.
Then extend the controlled track with partial updates, same-window corrections
and recoverable missing evidence. Keep the current seven heldout storms unused
while designing those changes, and preserve deterministic references/scoring
without introducing per-item human review or an LLM judge.
