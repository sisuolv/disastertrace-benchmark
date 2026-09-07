# Implementation Status

## Active milestone: P1 authorized continuation and amended report complete

2026-09-06: the user explicitly approves the USD 1.5 cumulative conditional
allowance, one reissue of unresolved original request 79, and at most 12 new /
91 cumulative requests. The actual authorization is recorded in
`artifacts/p1_deepseek_development/background_resume/authorization.json` against
frozen amendment ecd9840f5e679a8f789192b904d231c2eaef990bd1e40c197932d1c2bf672456.
The detached worker completes all 12 new requests and exits 0 at 16:38:46 UTC.
Entry: `README_P1_DEEPSEEK.md`; live output:
`work/p1-deepseek-background-continuation-v1/`.

Executed once, using the existing credential through a non-echoing prompt:

```bash
.venv/bin/python artifacts/p1_deepseek_development/background_resume/resume_background.py launch --amendment artifacts/p1_deepseek_development/background_resume/prepared/amendment.json --authorization artifacts/p1_deepseek_development/background_resume/authorization.json --output work/p1-deepseek-background-continuation-v1 --live
.venv/bin/python artifacts/p1_deepseek_development/continuation_report/report_continuation.py --amendment artifacts/p1_deepseek_development/background_resume/prepared/amendment.json --continuation work/p1-deepseek-background-continuation-v1 --output work/p1-deepseek-background-continuation-v1/report
```

Launcher, detached worker and report command exit 0. The worker PID/session is
16909 with closed stdin; normal finish is recorded in status.json and exit.json.
Exact command/log/hash evidence is in `background_resume/launch_command.json`
and `continuation_report/execution.json` under the P1 artifact directory.

The amended comparison has 90 received answers over 90 benchmark checkpoints,
but 91 cumulative provider attempts because original attempt 79 remains unknown.
All 78 prior responses, including 20 invalid answers, are retained. The final
per-method scores are:

| Method | Schema | V2 known grounding | V2 overall grounding |
| --- | --- | --- | --- |
| snapshot | 14/30 | 39/96 | 69/150 |
| structured_state | 30/30 | 96/96 | 150/150 |
| answer_history | 24/30 | 76/96 | 120/150 |

Snapshot's 14 length failures and two structural errors remain unchanged.
Answer_history has six empty-final length failures, including two newly received
ones; they are not retried. All 68 schema-valid answers have correct field values
and actions. One snapshot citation is evaluator_unverifiable at a movement-speed
line, although its wind value is correct. These diagnostics do not replace the
fixed denominators or prove a causal carrier effect.

Reported usage for 90 responses: 293,816 prompt + 170,378 completion = 464,194
tokens. The 158,370 reasoning tokens are already included in completion.
Captured-price received-response subtotal is USD 0.146989544; the 12 new
responses contribute USD 0.023630952. Total incurred cost remains unknown.
The cumulative ledger keeps all 79 old rows unchanged, including the original
USD 0.46678016 pending reservation; conservative settled accounting is
USD 0.35417800. Sum USD 0.82095816, remaining allowance USD 0.67904184.

All three collection/rescore packages verify. The new report composes frozen
scoring/report functions with explicit 91-attempt accounting, original-prefix
and suffix matching, authorization and per-request budget checks. It is labeled
completed_amended_continuation; the original interrupted no-retry report and
its archived partial package remain unchanged.

Independent continuation audit: 1,887 checks pass, plus the original partial
package's 247 checksum entries. All 177 protected historical files and 83
original P1 capture files remain unchanged. Continuation preparation's final
22 tests passed before launch; the new amended reporter separately passes
23 tests in 7.24 seconds with lint/format checks. Core code retains the previously
verified 611-test identity; no combined fresh suite is claimed. Verification
records are under `continuation_audit/` and `continuation_report/` in P1 artifacts.
Final independent report review passes 372 checks. Its initial three comparison
failures came from an audit helper comparing enriched V1 metrics against the raw
metric dictionary; the corrected audit checks all original metrics plus the two
independently recomputed known-only rates. Initial evidence is preserved, and
neither report nor scorer changes. See `continuation_audit/report_review_final.json`.

This authorized batch is complete and its one-use launch claim is consumed.
No further API request, selective retry, heldout evaluation or scorer change
was performed. Next recommended package: an explicit common public output
contract with offline regressions, followed by a separately predeclared output
budget comparison. Task-coverage expansion follows that calibration.

## Previous milestone: P1 interrupted capture audited and reported

2026-09-06: executed the authorized fresh DeepSeek development comparison with
the frozen model, three methods, three storms and 90 planned opportunities.
The user reports a machine restart. The original runner is absent after 79
admitted requests and 78 received responses, with request 79 unresolved and
11 not attempted. Its persisted execution.json is an unfinalized running
snapshot, not evidence of an active process. No original exit code is known.
Current entry point: `README_P1_DEEPSEEK.md`.

Snapshot completed 30 requests: 14 valid, 16 invalid, v2 known grounding 39/96
and overall grounding 69/150. Structured_state completed 30 requests: 30 valid,
96/96 known and 150/150 overall grounding. Answer_history stopped at 19 attempts
and 18 received answers: 14 valid, four invalid; its full-denominator partial
scores are 44/96 known and 70/150 overall grounding. The last method is incomplete;
these rates do not establish a method ranking. Snapshot's invalid answers
include 14 output-limit failures and two structural JSON errors. Every valid
received answer has correct field values/statuses; one snapshot citation points
to the wrong field's source line. Frozen v1 and v2 scores are both retained.

The original live command was:

```bash
.venv/bin/python artifacts/p1_deepseek_development/run_experiment.py --experiment artifacts/p1_deepseek_development/experiment.json --output work/p1-deepseek-development-v1
```

Its observed CLI exit code is null after interruption, explicitly recorded in
`artifacts/p1_deepseek_development/interruption_recovery/original_live_command.json`.
The 78 responses report 400,898 total tokens; cache-aware received-response cost
subtotal is USD 0.123358592. Full cost is unknown because attempt 79 has no usage.
The unchanged original ledger retains USD 0.46678016 for that attempt, plus
USD 0.30435328 conservative settled accounting. No uncertain charge is set to zero.

Completed a detached, network-disabled offline finalizer into
`work/p1-deepseek-development-v1-interrupted-finalization/`. It copies the partial
capture and adds one explicit local administrative interruption disposition,
not a provider-returned error or invented response. Independent collection audit,
offline import, trace binding, v1 score, v2 rescore and replay verification pass.
All 90 planned opportunities remain represented. The frozen reporter also exits 0
with matrix_status=incomplete_descriptive_only. Original 83 capture files and
177 protected historical files remain unchanged. Recovery makes zero API calls.

Actual command/exit/log records are under
`artifacts/p1_deepseek_development/interruption_recovery/execution.json` and
`interruption_recovery/report_checks/result.json`; the independent interruption
audit is `artifacts/p1_deepseek_development/interruption_audit/result.json`.
Recovery tests: 10 passed, zero skips, with focused lint and format checks passing.
Earlier P1 runner/reporter checks are separately 37 and 14 passed. The unchanged
core retains P0's 611-test verification; no combined fresh suite is claimed.

The user now requests background resubmission. A concrete restart proposal
retains all 78 received answers and the uncertain original attempt, raises the
conditional total allowance to USD 1.5 and permits exactly one explicit retry
plus 11 unattempted checkpoints (at most 12 new / 91 cumulative attempts).
This budget/retry amendment is awaiting the user's answer. The original USD 1
guard cannot reserve another request: required accounting would be USD 1.23791360.
Next executable task is the separately versioned detached continuation after
that confirmation; no further live request has been sent during recovery.

Background continuation preparation is now complete in
`artifacts/p1_deepseek_development/background_resume/`. Final tests: 22 passed
in 43.30 seconds, zero skips; Ruff and formatting pass. The simulated full
12-call continuation verifies inherited invalid answers, the 91-call cap,
retained unknown reservation, all 30 answer_history opportunities and v1/v2
audit/replay. A canonical one-use amendment claim prevents duplicate launches
across output directories; the first durable ledger already includes the old
79 attempts. The frozen amendment ID is
`ecd9840f5e679a8f789192b904d231c2eaef990bd1e40c197932d1c2bf672456`.
`offline_checks.json` records exact commands/hashes; `prepared/amendment.json`
is ready for the actual user authorization record. No worker or new live call
has started. The original partial package is separately archived with 246 bound
files and all 247 SHA256SUMS entries verified, exit 0.

## Previous milestone: P0 scoring and offline migration complete

2026-09-06: executed the user's approved next offline work package. Entry point:
`README_SCORING_V2.md`. Added `evidence_support.py`, `scoring_v2.py`, and
`rescoring.py`, their regression suites and three detailed specifications.
No source parser, task/answer schema, original dynamic scorer, model requests,
collection runtime or historical result was changed. No API request was made.

Implemented restricted deterministic support for the four existing numerical
fields, versioned source/index bindings, known-only metrics, fixed-reference
change/preservation opportunities, provenance refresh, conditional self-error
recovery, event macro and paired-branch correctness. Unsupported citation
grammar is reported as evaluator_unverifiable, not automatically hallucination.
The new policy is restricted to admitted NHC observation expressions; it does
not claim general natural-language entailment or require per-item human review.

### Actual verification and historical replay

The original saved-answer regression reproduces 49/50 under strict v1 where
supported-citation expectations require 50/50; its expected failing command is
retained in `artifacts/optimization_p0/legacy_regression/`. New module tests were
written before implementation; discovered context/suffix counterexamples were
also recorded failing before fixes. Their separate logs are under validator,
metric and migration checks in `artifacts/optimization_p0/`.

Executed:

```bash
.venv/bin/python artifacts/pre_api_v1/run_checks.py --output artifacts/optimization_p0/final_checks
.venv/bin/python -m disastertrace.automated.rescoring rescore --build work/build-deepseek-v1 --run work/deepseek-ida-state-v1/imported_run --historical-score artifacts/deepseek_probe_v1/rescore.json --output work/deepseek-ida-rescore-v2
.venv/bin/python -m disastertrace.automated.rescoring verify --output work/deepseek-ida-rescore-v2
.venv/bin/python artifacts/optimization_p0/verify_acceptance.py --package work/deepseek-ida-rescore-v2 --score-v1 work/deepseek-ida-rescore-v2/baseline_v1.json --score-v2 work/deepseek-ida-rescore-v2/score_v2.json --output artifacts/optimization_p0/acceptance.json
```

All four commands exit 0. Full suite: **611 passed in 35.59 seconds, zero skips**.
Scoped Ruff correctness/import and formatting checks pass for 38 automated
source/test files; `pip check` passes. Exact commands, logs, hashes and counts:
`artifacts/optimization_p0/final_checks/test_result.json` and
`artifacts/optimization_p0/historical_rescore_checks/result.json`.

Archived implementation replay exactly matches the original v1 result: 49/50
overall grounding, equivalent to 31/32 on known fields. V2 gives 50/50 overall
and 32/32 known-only grounding from the same ten saved responses. Exactly one
field changes: the supported 105 mph body citation at base c4. Values/statuses
remain 50/50, actions 10/10, unknowns 18/18, fixed Gold changes 22/22,
preservation 18/18 and provenance refresh 2/2. Self-error recovery has no
opportunities (0/0, null), not a perfect success rate.

The package reaudits the historical collection and binds old/new code, original
requests/responses, trace and evidence index. `acceptance.json` verifies 13
metric expectations and 80 unchanged protected files. The original v1 package,
scores and manifests remain untouched. This is changed evidence evaluation of
the same model outputs, not newly measured model improvement.

Current implementation ID:
`58acc19bf32eb83709344c7f8c001b2d86d8b665339ef251a5cd7b774784e716`.
Derived package `work/deepseek-ida-rescore-v2`, ID:
`e9450ff3b175e1ecc4999eb679a364cd4bbb1749e47b20e2404a20c9e521d049`.
Existing normal build/run identity guards remain unchanged; new collection work
must use a fresh matching build, while historical rescoring uses saved code.

Additional offline development diagnostics: all three development storms,
three methods and rule/last-arrival/no-update backends produce nine
configurations and 270 explicitly diagnostic responses, zero API requests.
Per method, known-only grounding is 96/96, 72/96 and 0/96 respectively; overall
grounding is 150/150, 126/150 and 54/150. All nine have identical fixed
denominators: 64 changes, 56 preservations, eight provenance refreshes. The
last-arrival program exposes 24 stale citations. These are program controls,
not additional LLM results or proof that the methods are equivalent.
The diagnostic script, its three successful command records and all 39
verified result files are in `artifacts/optimization_p0/dev_diagnostics/`.

Next executable package: P1, a complete 90-request DeepSeek development matrix
with fixed model/method settings, v2 scoring identity and spending limits. No
new API batch, heldout evaluation or richer controlled-task release is included
in this completed P0 package.

## Previous planning update: optimization roadmap prepared

2026-09-06: prepared `OPTIMIZATION_ROADMAP.md` in response to the user's request
to plan further benchmark improvements. It supplements the integrated v0.3 plan;
the proposed scorer, metric and task changes are not implemented or frozen.
The roadmap prioritizes a versioned deterministic evidence-support validator,
immutable offline rescoring, metric clarification, a complete 90-request
DeepSeek development comparison, and controlled capability/event expansion.
It preserves the requirement for no new per-item human annotation or review.

This planning step makes zero additional model API calls and changes no source
code, data, build, trace or historical score. Only the roadmap and documentation
entry/status references are updated. A `.venv/bin/python -` documentation check
exited 0: all six roadmap evidence references exist, the new document is ASCII,
and the 90/180/420 request counts and 31/32 known-only strict-grounding arithmetic
are consistent. The full code suite was not rerun for this documentation-only
step; the 483-pass result below is verification from the completed live-trial
implementation, not a new test result.

Next recommended executable package: P0 evidence-support specification and
regression tests, separate scorer/migration identities, v1/v2 rescoring of the
saved ten responses, and fixed-reference metric definitions. This package needs
zero new inference requests. P1 follows with a declared model/method matrix and
cost limits; no broader live batch has been started by this planning request.

## Previous milestone: first DeepSeek live trial complete

2026-09-06: the user supplied a DeepSeek credential and explicitly requested
trying `deepseek-v4-flash`, high reasoning effort and thinking enabled. One SDK
probe and a bounded ten-checkpoint Ida development trial completed. Entry point:
`README_DEEPSEEK.md`. The credential was held in process memory/environment and
was not written to project scripts, configs or logs. No further model calls are
required for this bounded trial.

### Implementation and verification

- Installed OpenAI SDK 3.8.0 in `.venv`; saved exact environment versions to
  `artifacts/deepseek_probe_v1/requirements.txt`. Installation and `pip check`
  exited 0. Initial index DNS retries and slow wheel downloads recovered.
- Fetched five official DeepSeek documentation pages (HTTP 200), preserving raw
  HTML, extracted text, URLs, timestamps and hashes under
  `artifacts/deepseek_probe_v1/docs/`. Exact model/effort/thinking support is
  documented. Additional OpenAI official documentation requests returned 403;
  the real SDK response establishes the recorded DeepSeek integration.
- Added typed optional `reasoning_effort` and `thinking_type` configuration to
  the existing provider. Existing eight required fields remain supported;
  arbitrary extra-body overrides are rejected. Options bind the wire/config
  hashes. Reasoning response data is recorded, not put into the answer carrier.
- Regression-first options tests initially failed 26 cases; the updated targeted
  provider/collection/audit suite passed 152. Final full suite: **483 passed in
  29.25 seconds, zero skips**, exit 0. Scoped Ruff check and formatting of 32
  automated source/test files, plus `pip check`, pass. Logs and commands:
  `artifacts/deepseek_probe_v1/offline_checks/test_result.json`.
- New build: `work/build-deepseek-v1`, ID
  `bff26da089e371f798436ac0645f309d479eaa5e69b6a401d29db8a733beb81c`.
  All 15 data artifacts match the pre-API build byte-for-byte; the source parser
  is unchanged. Earlier frozen packages retain their own saved implementation.

### Actual execution

The following commands exited 0. The credential was supplied through the scripts'
non-echoing prompt, not an argument or saved config:

```bash
.venv/bin/python examples/probe_deepseek.py --output work/deepseek-probe-v1
.venv/bin/python examples/run_deepseek_ida.py --build work/build-deepseek-v1 --config configs/provider.deepseek-flash.example.json --output work/deepseek-ida-state-v1
.venv/bin/disastertrace-auto score --build work/build-deepseek-v1 --run work/deepseek-ida-state-v1/imported_run --output artifacts/deepseek_probe_v1/rescore.json
```

SDK probe: returned `Hello! How can I help you today?`, elapsed 2.495 seconds,
89 input / 62 output tokens, including 52 reasoning tokens, finish_reason=stop.
Benchmark: 10 actual HTTP requests, 10 received schema-valid answers, all
finish_reason=stop, no retries, about 73.9 seconds end-to-end. Configuration:
structured_state, Ida development only, max_tokens=4096 per request,
reasoning_effort=high, thinking enabled, temperature omitted. Global attempt
cap=10, output reservation=40960, request-body cap=262144 bytes.

| Metric | Observed score |
| --- | --- |
| Schema success | 10/10 |
| State value/status accuracy | 50/50 |
| Strict reference citation plus state | 49/50 |
| Rule actions | 10/10 |
| Required unknown | 18/18 |
| Known answer coverage | 32/32 |
| Required changes | 22/22 |
| Eligible preservation | 18/18 |

The collection audit passes and independent rescoring reproduces the result.
Actual requests, raw responses, audit and score are in
`work/deepseek-ida-state-v1/`. Usage/report: `artifacts/deepseek_probe_v1/`.

Combined usage for the 11 responses: 51,024 prompt tokens, 10,734 completion
tokens, 61,758 total. Completion includes 9,125 reasoning tokens (not added
again). Prompt cache hits=15,104; misses=35,920. Using the captured official
Sunday off-peak rates gives an estimated USD 0.015092568, not a billing receipt.
Every response reports usage; no heldout or extra model/method calls were made.

### Finding and next research task

The lone citation deduction is at base c4, maximum_wind_mph: actual 105 mph cites
advisory 011 line 88, whose text explicitly states 105 mph. The frozen scorer
accepts only summary line 21, also stating 105 mph. This exposes overly narrow
reference-locator matching; do not interpret it as a demonstrated unsupported
model claim. Source answers and the 49/50 strict score remain unchanged.

Before broad comparisons, implement/test a separately versioned deterministic
equivalent-citation policy on development data and report both scoring versions.
Larger runs still need their model/method selection and cost limits fixed.
This one public development event does not establish heldout performance,
method superiority or broad extreme-weather competence.

## Pre-API pilot preparation (completed history)

2026-09-06: completed all independent preparation for the first LLM pilot, as
requested before actual API testing. The current entry point is
`README_PRE_API.md`. Actual model/service, credential environment variable and
trial spending limit remain unresolved; **zero real LLM calls** were made.

### Current implementation and frozen artifacts

- Three declared methods: structured_state, snapshot and answer_history. Fresh
  messages receive identical cumulative delivered evidence and only the declared
  actual-answer carrier. Valid wrong answers propagate; invalid/missing attempts
  remain in the scoring denominator. Methods, event selections and traces bind.
- Independent dataset audit: all 13 checks pass. Exact source-hash screening
  covers all 36 acquisition records. All 32 parsed records, including two Harvey
  orphans, yield 496 similarity pairs / 231 cross-split pairs. No exact,
  normalized or Jaccard >= 0.9 candidates; maximum cross-split Jaccard is 0.166588.
  This is a lexical screen, not proof of pretraining decontamination.
- Independent collection audit reconstructs actual requests, wire bodies,
  completion envelopes, model-reported usage and accepted state/history. Imported
  scoring binds the audited collection and rejects uncollected extra responses.
- Safe resume into a new directory from a verified completed prefix. Caps count
  old plus new attempts/reservations. No retry of received invalid responses,
  provider errors or uncertain in-flight requests. Request-byte and aggregate
  output-reservation guards are implemented; monetary and total-token caps are not.
- Frozen matrix: two unresolved model slots x three methods x one repeat.
  Ida-only smoke = 60 attempts, development = 180, heldout = 420. Smoke overlaps
  development; its observations cannot count as additional independent samples.
- New CLI: `preflight`, `verify-preflight`, `audit-dataset`, `audit-collection`;
  method/event-group selection, resume and guards integrated into run/model CLI.

Build: `work/build-pre-api-v1`, ID
`1e0d400a5b3dbc39b8d8bd883c1dfbb937fe68dd3ac1ab476f78dac3b194d8e6`.
Frozen package: `work/pre-api-v1`, ID
`a471c0beecde637b08cf295907d4ff03010904f91decbf2ce357dd362208febc`.
The manifest binds **116 files**, including audit, matrix, full traces/scores,
rehearsals, command/test evidence and report. `readiness.json` records
`offline_ready=true`, `live_ready=false` and pending provider configuration.

### Actual verification

Final full suite: **443 passed in 29.34 seconds, zero skips**, exit 0.
Scoped Ruff correctness/import checks and formatting of 31 automated source/test
files pass; `pip check` reports no broken requirements. Exact commands, logs,
implementation ID and test-file hashes are in
`artifacts/pre_api_v1/final_checks/test_result.json` and adjacent logs.

```bash
.venv/bin/python artifacts/pre_api_v1/run_checks.py --output artifacts/pre_api_v1/final_checks
.venv/bin/python artifacts/pre_api_v1/run_package.py
```

Both commands exited 0. The script outputs already exist; use new paths/names
when reproducing rather than overwriting historical results.
All **11 final CLI commands** exited 0: cached-source build, preflight, package
verification, repeated build, independent dataset audit, and model preparation
plus collection audit for each method. Exact commands/output hashes are in
`artifacts/pre_api_v1/commands.json` and `artifacts/pre_api_v1/cli/`.

Reproducibility checks in `artifacts/pre_api_v1/reproducibility.json` confirm:
repeated build manifests match; the current implementation matches the build;
the source parser is unchanged; all 15 nonimplementation data artifacts match
the previous cohort build byte-for-byte. No historical output was overwritten.

The original sandbox attempt had 438 passing tests and one PermissionError when
creating the loopback test server. It was retained under `sandbox_attempt/`.
The permitted rerun passed all 439 tests of that intermediate source revision.
Four further readiness-record regressions were reproduced and fixed before the
443-test final verification. No test was deleted or skipped to obtain a pass.

Other new regression-first fixes include unaudited extra response/method injection,
prefix source rereading after audit, failed controls accepted by preflight, and
an empty rehashed package manifest being accepted. Verification creation and
revalidation now share the same record checks and retain portable attached logs.

### Executed offline results

All 18 dynamic diagnostic runs meet their expected behavior. Every method gives
the following fixture results, which establish protocol behavior, not real LLM
method equivalence or benefits:

| Split / diagnostic | Grounded fields | Correct rule actions |
| --- | --- | --- |
| development / rule | 150/150 | 30/30 |
| development / last-arrival | 126/150 | 28/30 |
| development / no-update | 54/150 | 6/30 |
| heldout / rule | 350/350 | 70/70 |
| heldout / last-arrival | 294/350 | 70/70 |
| heldout / no-update | 126/350 | 14/70 |

Two inherited-plan controls score 230/230 (reference fixture) and 0/230 (empty).
Three injected-transport rehearsals each stop after three completed requests and
resume to ten, with exactly ten total fixture calls, no repeated prefix request
and identical collected/scored public requests. They make zero live model calls.
Full results: `work/pre-api-v1/REPORT.md`, scores and rehearsal subdirectories.

### Next executable task and scope

Obtain the user's actual model/service configuration and trial spending limit,
freeze version/decoding/context/pricing information, then run a small Ida-only
API probe and the planned two-model/three-method smoke. Credential values belong
only in local environment variables. Actual endpoint support and costs require
provider-specific verification; byte/output reservations are not currency caps.
No new per-item human annotation/review is needed for this pilot.

The whole research agenda is not declared complete: cross-hazard/multimodal
expansion, richer correction/cancellation variants, adaptive Frontier search and
population-level statistical conclusions remain later phases. The existing
10-event Atlantic cohort is a selected pilot with controlled release schedules.

## Second work package (completed history)

2026-09-06: independent-event expansion, frozen event splits, per-event scoring,
and model-interface preparation are complete. Real LLM execution is awaiting the
user's model/service and trial budget; no endpoint or key was configured and no
hosted/model call was made. The user was asked while the independent work ran.

### Implemented and executed

- Frozen catalogue: 12 Atlantic storms, each with advisories 009/010/011; four
  development and eight heldout assignments fixed before acquisition.
- Actual acquisition: all 36 records downloaded/extracted, with original HTML,
  unchanged PRE text, hashes, all planned records and per-attempt logs saved to
  `../references/nhc_cohort_v1/`. No failed-download substitution.
- Unchanged parser: 32 source records pass. Complete triples admit 10 storm
  events, using 30 records; 3 development events/30 checkpoints and 7 heldout
  events/70 checkpoints. Harvey and Matthew are quarantined, not relabelled.
- Event grouping: paired base/delay branches inherit their storm's split;
  cross-split exact source-byte duplication is checked. Per-event, event-macro,
  pooled, and paired-branch results retain their separate denominators.
- Provider transport and collector: exact public/wire requests, response bytes,
  actual model-authored state, reported usage, sanitized errors, durable request
  logs, and a global attempt limit. No automatic retries, monetary cap or resume.
- CLI: `acquire-nhc`, optional `build --nhc-snapshot`, `run --split`,
  `prepare-model`, and `collect-model`. Collection imports saved responses into
  the existing scorer; offline import call counters remain separate.

### Verification and final artifacts

Full suite: `.venv/bin/python -m pytest -o addopts= -q` exits 0 with
**322 passed in 6.02 seconds, zero skips**. Log and command record are in
`artifacts/cohort_v1/full_pytest.log` and `artifacts/cohort_v1/test_result.json`.
The earlier 165 tests remain included; no existing test was removed or skipped.
Scoped Ruff correctness/import and formatting checks pass for 22 automated
source/test files. No new dependencies or model weights were installed.

Real-source integration exposed a catalogue/parser storm-name case difference
(`IDA` versus `Ida`). A failing regression was added before case-insensitive
metadata matching was implemented; raw text, parsed source names and the source
parser are preserved.

All 17 final CLI commands exit 0, including both split runs for all three
diagnostics, scores/report, network-free model preparation, a repeated build,
and replay of the historical v2 scorer from its saved source copy. Commands and
outputs are recorded in `artifacts/cohort_v1/commands.json`; equality checks are
in `artifacts/cohort_v1/reproducibility.json`.

Final build: `work/build-cohort-v1`, ID
`204681b7be7600a23ad57a7517e2ce5847d2bb5746d978d7b4a144775752f484`.
The repeated build `work/repro-build-cohort-v1` has an identical manifest.
Current report: `work/REPORT-cohort-v1.md`. Model preparation:
`work/model-preparation-cohort-v1.json` (placeholder model, no network).

| Split / diagnostic | Grounded fields | Correct actions |
| --- | --- | --- |
| development / rule | 150/150 | 30/30 |
| development / last-arrival | 126/150 | 28/30 |
| development / no-update | 54/150 | 6/30 |
| heldout / rule | 350/350 | 70/70 |
| heldout / last-arrival | 294/350 | 70/70 |
| heldout / no-update | 126/350 | 14/70 |

These remain diagnostic programs, not LLM scores. The heldout last-arrival control
demonstrates that coarse action accuracy alone can hide incorrect grounded state.
Full interpretation and source exclusions are in `DATA_CARD_COHORT_V1.md`.
Reproduction/model commands are in `README_COHORT.md`.

### Remaining next task

Configure the user's chosen model/service and trial budget, validate actual
endpoint parameter support, and perform a small development-only collection.
Tokens are reported when supplied by the provider; missing usage remains unknown.
Request/output-token caps are not a monetary spending cap. No current hosted
model compatibility or real model behavior is claimed from mock/loopback tests.

The heldout set shares the task template and is not private or decontaminated.
Near-duplicate/template analysis, richer task variants, cross-disaster coverage,
larger statistical samples, and Frontier search remain subsequent work. New
variants should be developed without changing this frozen heldout Gold.

## First work package (completed history)

2026-09-06: the v0.3 offline first work package is complete. Real-source
build/run/score/report and isolated-environment verification have passed.
The current specification is
`../INTEGRATED_BENCHMARK_PLAN.md`; the packaged historical plan applies only where
consistent with the user's latest scope. No new per-item human review is required.

## Starting point

- Safely extracted the existing handoff archive into this directory (43 entries).
- Python 3.10.12; global Pydantic 2.6.4 is below the declared dependency, and orjson/ijson are missing.
- The original archive and reference snapshots remain unchanged.

## Completed implementation

- Added `src/disastertrace/automated/` incrementally, preserving legacy modules and
  their tests. New results do not depend on the legacy scorer/runtime.
- Implemented strict DisasterBench source admission and inherited-plan scoring,
  CyPortQA template profiling, and NHC identity/time/unit/locator validation.
- Implemented fresh dynamic requests, controlled delay/repeat schedules, actual
  prior-state carriers, deterministic scoring, and non-LLM diagnostic controls.
- Added `disastertrace-auto` and the standard-library source-tree entry point with
  build/run/score/report, logical budgets, strict JSONL submissions, and explicit
  provenance. Missing/invalid/budget-exhausted attempts remain in denominators.
- Bound generated artifacts to source and implementation hashes; copied exact
  automated Python sources into the final build. Existing outputs are preserved.
- Added `README_AUTOMATED.md`, schema examples, `THIRD_PARTY_NOTICES.md`, and
  regression/integration tests. No paid API, model weights, or real tools are used.

## Real-source artifacts

Final build: `work/build-v2`, build ID
`78bf330d1d1690b0d6737beeae2f8cd9fcafdd99a6f48d5a3b47b1ca2e583da5`.
The earlier `work/build-v1` and all v1 runs/scores remain as development history.

| Item | Observed result |
| --- | --- |
| DisasterBench | 233 source tasks, 230 admitted, 3 quarantined, 26 tools |
| Quarantine | Tasks 3 and 191 reference undeclared outputs; task 119 duplicates a step |
| CyPortQA | 48 templates profiled; not a recovered full QA dataset |
| NHC | 3 selected official Ida advisories, unchanged raw text |
| Dynamic | 2 controlled schedules, 10 checkpoint attempts, 1 independent storm |
| New human reviews / live model calls | 0 / 0 |

Final report: `work/REPORT-v2.md`. Detailed traces and scores are in
`work/runs/*-v2/` and `work/scores/*-v2.json`.

| Diagnostic backend | Grounded fields | Actions | Exact inherited plans |
| --- | --- | --- | --- |
| rule | 50/50 | 10/10 | N/A |
| last-arrival | 42/50 | 8/10 | N/A |
| no-update | 18/50 | 2/10 | N/A |
| reference-fixture | N/A | N/A | 230/230 |
| empty-control | N/A | N/A | 0/230 |

These are software diagnostic results, not LLM performance. Reference-fixture
intentionally reads private labels. The rule backend independently parses the
public raw text rather than receiving the reference compiler's parsed fields.
The importer examples were also run/scored: one valid initial dynamic response
with nine missing attempts, and one invalid empty plan with 229 missing tasks.

## Verification

Executed command details, timestamps, exit codes and outputs for all 16 final
offline CLI commands are in `artifacts/verification/offline_commands_v2.json`
and its referenced logs. All 16 exit codes are zero. The main commands are:

```bash
PYTHONPATH=src python -m disastertrace.automated build --references ../references --output work/build-v2
PYTHONPATH=src python -m disastertrace.automated run --build work/build-v2 --track dynamic --backend rule --max-queries 10 --output work/runs/rule-v2
PYTHONPATH=src python -m disastertrace.automated score --build work/build-v2 --run work/runs/rule-v2 --output work/scores/rule-v2.json
PYTHONPATH=src python -m disastertrace.automated report --build work/build-v2 --scores work/scores/rule-v2.json work/scores/last-arrival-v2.json work/scores/no-update-v2.json work/scores/reference-fixture-v2.json work/scores/empty-control-v2.json --output work/REPORT-v2.md
```

Use new output paths to rerun these commands.

Global-environment component verification: DisasterBench 22 tests, source parsing
43 tests, dynamic 68 tests, and workflow 26 tests passed after their fixes. The
initial global legacy test run passed five and skipped one because pytest-asyncio
was missing; it is not recorded as six passed.

Final isolated verification:

```bash
.venv/bin/python -m pytest -o addopts= -q
.venv/bin/python -m pip check
```

Both exit zero: **165 passed in 3.74 seconds, zero skipped**, and **No broken
requirements found**. The original six tests also pass independently, including
the async runner. Full output is in `artifacts/bootstrap/full_pytest.log` and
`artifacts/bootstrap/original_tests.log`; package versions and native CLI/import
checks are in `artifacts/bootstrap/environment_verification.json`.

The installed `disastertrace-auto` rebuilt `work/repro-build-v2` with a manifest
identical to `work/build-v2` and rescored the rule trace with an identical parsed
result. Installed Ruff correctness/import and formatting checks also pass. All
five additional commands and both equality checks are recorded in
`artifacts/verification/environment_commands_v2.json`.

Regressions first reproduced and then fixed: empty/duplicate scoring episode
sets, empty checkpoint collections, malformed submission ID types, invalid trace
status/counters, responses attached to exhausted slots, and declared budgets that
disagree with trace/prediction counts. The real NHC parser also required a fix to
distinguish the current-summary header from the watches/warnings heading.

The canonical DisasterBench comparison was checked against the pinned upstream
evaluator on 920 cases (230 admitted tasks times four mutations), with agreement
for all four comparison metrics. This does not validate the inherited labels as
real-world truth or establish equivalence with the upstream completion parser.

Ruff correctness/import checks (`--select E4,E7,E9,F,I`) and formatting checks pass
for the 8 new automated Python modules and 4 automated test files. The full
default Ruff style rule set and static mypy analysis are not claimed as passed.

Environment bootstrap logs in `artifacts/bootstrap/` record missing ensurepip,
network timeouts, and verified parallel wheel retrieval. Recovery completed with
an offline editable installation of the project plus all dev dependencies.
`requirements-verified.txt` records installed dependency versions excluding the
editable project. The isolated environment uses Python 3.10.12, Pydantic 2.13.5,
pytest 9.1.1 and pytest-asyncio 1.4.0. No system Python packages were modified.

## Interpretation and deferred work

The weather sample is development-only. Release time is controlled rather than
historically proven, and observations at successive issue times are not
same-valid-time forecast revisions. Every request receives all evidence delivered
so far; this does not prove causal use of the explicit carrier. The port-reopening
field is a missing-evidence control, not a reconstruction of actual port recovery.

DisasterBench is broad-disaster planning agreement, not an extreme-weather-only
task set or actual tool execution. No official upstream leaderboard result is
claimed. Submitted files retain unverified external provenance.

Live provider integration, per-request crash recovery/resume, independent-event
expansion, model comparisons, train/test split freezing and Frontier search are
not implemented in this milestone.

## First package follow-up (now implemented above)

Expand automatic NHC admission to independent storms using the frozen parser and
event-group splits.
After that, add an explicitly configured provider adapter that records the actual
requests, model/version, decoding settings, retries, token/cost budget and raw
responses. Keep acquisition failures and rejected sources in the inventory.
