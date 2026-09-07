# Pre-API pilot preparation

This records the completed pre-API stage. The subsequent authorized DeepSeek
trial is in [README_DEEPSEEK.md](README_DEEPSEEK.md), with a new source build,
483 passing tests and actual model results. Historical frozen artifacts below
retain their original implementation identity.

This is the current entry point for the first LLM pilot. The independent data,
protocol, scoring, collection and recovery checks run without a model service.
No new per-item human review or LLM judge is required. All executed programs in
the preparation package are deterministic diagnostics, not LLM results.

## Frozen scope

The pilot has 10 admitted Atlantic cyclone events, 20 base/delay branches and
100 checkpoints. Three events (30 checkpoints) are development; seven events
(70 checkpoints) are heldout. All 36 planned official NHC documents remain in
the acquisition inventory; 32 parse and 30 enter complete three-advisory events.
The source parser and original event split are unchanged. DisasterBench supplies
230 admitted planning controls; CyPortQA contributes a profile of 48 templates,
not a recovered 48-item QA set.

| Method | Carrier in each fresh request |
| --- | --- |
| `structured_state` | Last schema-valid model-authored decision, or null |
| `snapshot` | No prior model answer |
| `answer_history` | All prior schema-valid decisions within this branch, in order |

Every method gets the same cumulative legally delivered evidence. Invalid JSON
is retained as a failed attempt and excluded from the carrier; valid but wrong
answers propagate unchanged. Each branch starts with an empty carrier. These
methods compare declared input representations; full evidence at every step
means this experiment does not isolate causal reliance on memory.

`configs/pre_api_pilot_v1.json` fixes the following matrix before model results:

| Phase | Events | Checkpoints per cell | Models x methods | Maximum attempts |
| --- | --- | --- | --- | --- |
| Smoke | Ida, development only | 10 | 2 x 3 | 60 |
| Development | All 3 development events | 30 | 2 x 3 | 180 |
| Heldout | All 7 heldout events | 70 | 2 x 3 | 420 |

There is one repeat. The two model slots are unresolved identities; two different
model families are recommended. Smoke is a subset of development and must not
be pooled with development as independent data. If all phases are run separately,
there are at most 660 planned attempts; preparation executes none of them.
Freeze the actual model/version, endpoint, decoding settings, context limits,
prices and run limits before real comparisons. Do not tune prompts or the parser
on heldout model results. Scores retain per-event, event-macro and pooled counts;
grounded state is primary and coarse action accuracy is secondary.

## Completed package and reproduction

Current outputs use `work/build-pre-api-v1`, `work/pre-api-v1` and
`artifacts/pre_api_v1`. Exact test counts, hashes and command results are recorded
in `IMPLEMENTATION_STATUS.md` and the verification artifacts. Historical builds
are retained; new source changes require a new build and new output directories.

```bash
.venv/bin/disastertrace-auto build \
  --references ../references --nhc-snapshot ../references/nhc_cohort_v1 \
  --output work/my-pre-api-build
.venv/bin/disastertrace-auto preflight \
  --build work/my-pre-api-build --specification configs/pre_api_pilot_v1.json \
  --output work/my-pre-api-checks
.venv/bin/disastertrace-auto verify-preflight \
  --build work/my-pre-api-build --package work/my-pre-api-checks
```

All three commands are network-free with the cached snapshot. `preflight` runs
18 dynamic controls (3 methods x 3 backends x 2 splits), two inherited planning
controls, and three injected-transport partial/resume rehearsals. Controls must
meet their expected behavior before the artifact manifest is written. Every
rehearsal collects the first 3 Ida checkpoints, then continues in a new directory
to all 10 without reissuing the first 3 requests.

`preflight --verification-record artifacts/pre_api_v1/final_checks/test_result.json` attaches
the full-suite verification evidence when its implementation ID still matches.
Without this option the checks still run, but `offline_ready` remains false.
The verification record includes real command exit codes, test counts and log
hashes; copied logs use package-relative paths. `verify-preflight` rechecks
required artifacts, identities, dataset/matrix consistency and attached logs.
Checksums establish local consistency, not independently authenticated execution.
`live_ready` remains false until provider-specific preparation is completed.

The package contains `dataset_audit.json`, `experiment_matrix.json`, `readiness.json`,
`REPORT.md`, complete runs/scores, collection rehearsals, verification evidence
and a `manifest.json` binding every generated file. No credentials belong in it.
See `docs/DATA_AUDIT_METHOD.md` for exact duplicate and similarity definitions.

## Move to a real API

The remaining external inputs are served model IDs, compatible endpoint URLs,
credential environment-variable names and a trial spending limit. Place secret
values in the local environment, never in a config, conversation or artifact.
`configs/provider.example.json` is deliberately rejected by collection until its
placeholder model is replaced. It is sufficient for offline preparation:

```bash
.venv/bin/disastertrace-auto prepare-model \
  --build work/build-pre-api-v1 --config configs/provider.example.json \
  --split development --event-group AL092021 --method answer_history \
  --max-queries 10 --output work/my-first-request.json
```

The next command is a real-model example, not a record of an executed API call:

```bash
.venv/bin/disastertrace-auto collect-model \
  --build work/build-pre-api-v1 --config /path/to/selected-provider.json \
  --split development --event-group AL092021 --method structured_state \
  --max-queries 10 --max-request-bytes 262144 \
  --max-reserved-output-tokens 10240 --output work/my-model-a-smoke-state
```

The example reservation assumes `max_output_tokens=1024`; choose the value using
the actual server's output convention and schema needs. A 262144-byte body guard
is a local protective bound, not a token-context guarantee. Only actual provider
usage can establish token counts, and missing usage remains unknown. Neither
request caps nor output-token reservations enforce a currency budget or limit
unknown input/reasoning billing. Configure provider-side spending controls where
available and measure a small development probe before the full 60-attempt smoke.

Collection independently audits its journal before importing responses. The
scored run binds the collection files and audit, verifies exact actual public
requests, and rejects responses with no corresponding collected completion.
The imported run's logical query counters remain separate from provider attempts.

For a verified budget/guard-stopped prefix, resume into a new output directory:

```bash
.venv/bin/disastertrace-auto collect-model \
  --build work/build-pre-api-v1 --config /path/to/selected-provider.json \
  --split development --event-group AL092021 --method structured_state \
  --resume-from work/my-model-a-smoke-state/collection \
  --max-queries 10 --max-request-bytes 262144 \
  --max-reserved-output-tokens 10240 --output work/my-model-a-smoke-state-resumed
```

`--resume-from` names the directory containing `plan.json` and the JSONL journals.
Caps apply to the entire old-plus-new run, not just the continuation. Config,
method, episode order and transport kind must match. Invalid but received
responses are not retried. Provider errors or in-flight requests cannot be
automatically resumed because they may already have reached a billable service.
Original artifacts remain untouched; no automatic HTTP retry occurs.

## Interpretation limits

Automatic admission and deterministic scoring remove the new human-review
dependency for these tasks; they do not establish universal weather expertise.
Near-duplicate screening does not prove pretraining decontamination. Public
heldout reports share templates, release schedules are controlled, and numbered
advisories describe successive observations rather than same-valid-time forecast
corrections. The missing port reopening field tests insufficient evidence.

This package completes the independent preparation for the first API pilot.
Cross-hazard expansion, multimodal tasks, richer cancellation/correction tests,
adaptive Frontier search and broad statistical generalization remain later
research phases. They are not claimed as implemented by this package.
