# Independent-event pilot and model collection

Historical second-package record. The current implementation and commands are
in [README_PRE_API.md](README_PRE_API.md); new source changes require a fresh
build. Current collection adds three methods, independent audit and safe resume.

The second work package expands the original single-storm example into a frozen
event cohort, with separate development/heldout runs and per-event scoring. It
also adds a configurable model transport and sequential response collector.
The executed results are diagnostic programs, not actual LLM experiments.

Start with [work/REPORT-cohort-v1.md](work/REPORT-cohort-v1.md) and
[DATA_CARD_COHORT_V1.md](DATA_CARD_COHORT_V1.md). The full test suite passes:
322 tests, zero skips. No additional dependencies, model weights, or hosted model
calls were needed.

## Actual data coverage

The catalogue fixes 12 named Atlantic storms and advisories 009, 010, and 011
before acquisition. All 36 source records were downloaded. The unchanged source
parser admits 32 records, and the complete-triple rule admits 10 storm events:

| Split | Planned storms | Admitted storms | Branches | Checkpoints |
| --- | --- | --- | --- | --- |
| development | 4 | 3 | 6 | 30 |
| heldout | 8 | 7 | 14 | 70 |

Thirty records enter episodes. Two parsed Harvey records remain in the inventory
but cannot form a complete event because its third record is a remnants advisory.
Matthew's older uppercase publisher header is outside the frozen parser contract.
The two excluded events and all four source rejections are retained; no records
are substituted and no source text or inherited answer is repaired.

## Reproduce the data and scores

Run commands from this project directory. The environment already exists here;
see README_AUTOMATED.md and requirements-verified.txt for installation elsewhere.
Use new output names rather than overwriting existing artifacts.

```bash
.venv/bin/disastertrace-auto acquire-nhc \
  --catalogue configs/nhc_cohort_v1.json --output ../references/my-nhc-snapshot
.venv/bin/disastertrace-auto build \
  --references ../references --nhc-snapshot ../references/my-nhc-snapshot \
  --output work/my-cohort-build
.venv/bin/disastertrace-auto run \
  --build work/my-cohort-build --track dynamic --backend rule \
  --split development --max-queries 30 --output work/my-development-run
.venv/bin/disastertrace-auto score \
  --build work/my-cohort-build --run work/my-development-run \
  --output work/my-development-score.json
.venv/bin/disastertrace-auto report \
  --build work/my-cohort-build --scores work/my-development-score.json \
  --output work/my-development-report.md
```

Acquisition is the only network step above. To rebuild entirely offline, use the
existing `../references/nhc_cohort_v1` snapshot. New acquisition timestamps change
the snapshot's provenance; rebuilding from the same frozen snapshot reproduces
the same build identity. The completed build is `work/build-cohort-v1`.

Use `--split heldout --max-queries 70` for all currently admitted heldout
checkpoints. The other diagnostics are `last-arrival` and `no-update`. Every
attempt remains in the scoring denominator. A query budget shorter than the
selected set yields scored budget-exhausted attempts; it does not shrink the set.
DisasterBench retains its original 230 admitted planning tasks and does not claim
these weather-event splits.

## Model preparation and collection

No endpoint or model is configured in this workspace. The example file contains
an explicit placeholder, which the collector refuses to use. The following
preparation command validates configuration and renders the first legal request
without reading a secret value or sending HTTP:

```bash
.venv/bin/disastertrace-auto prepare-model \
  --build work/build-cohort-v1 --config configs/provider.example.json \
  --split development --max-queries 10 --output work/my-model-preparation.json
```

Only the first checkpoint request is prepared. Later requests must use the actual
model's preceding accepted response; they cannot be precomputed with reference
states. The example preparation is not a connectivity or model-availability test.

After selecting a model and endpoint, create a separate configuration following
[docs/PROVIDER_INTERFACE.md](docs/PROVIDER_INTERFACE.md). Use an environment
variable for the credential, never an inline key in the config. `max_tokens` and
`max_completion_tokens` are explicit alternative conventions; model/provider
compatibility must be verified for the selected service.

The command below makes configured model requests and can incur provider charges.
It was tested with fixture transports but was not executed against a real LLM:

```bash
.venv/bin/disastertrace-auto collect-model \
  --build work/build-cohort-v1 --config /path/to/model-config.json \
  --split development --max-queries 10 --output work/my-model-collection
```

The collector then imports `collection/responses.jsonl` and runs the existing
deterministic scorer. Its output directory contains:

| File | Meaning |
| --- | --- |
| `build_context.json` | Frozen build/code identity, event split, config-file hash |
| `collection/plan.json` | Selected checkpoint plan and nonsensitive model configuration |
| `collection/requests.jsonl` | Actual public requests and exact wire payloads, flushed before attempts |
| `collection/outcomes.jsonl` | Raw successful responses, reported usage, failures, actual accepted state |
| `collection/responses.jsonl` | Exact import-format response strings, without output repair |
| `collection/summary.json` | Collection attempts/completions, missing usage, artifact hashes |
| `imported_run/` | Offline reconstruction and input/state validation |
| `score.json` | Full selected-set scores and per-event summaries |

The cap counts `complete()` attempts, including failures before an HTTP request
such as a missing credential. It is not a verified count of billed model calls.
Collection stops at the first provider error, keeps partial artifacts, and does
not automatically retry or resume. Invalid model JSON remains a scored failure;
the prior accepted state is preserved. Semantically incorrect but valid state is
carried forward without correction.

The offline import makes zero provider calls. Its logical checkpoint count is
separate from the collector's attempts and reported token usage. Response usage
may be missing, and no aggregate token or monetary cap is enforced. Agree on the
service and trial budget before using a paid endpoint. Current outputs remain
ineligible for a certified LLM leaderboard; fixture transports are never LLMs.

## Versioning and interpretation

The final 17 executed commands, output logs, and reproducibility assertions are
in `artifacts/cohort_v1/`. The new build was reproduced byte-for-byte at the
manifest level. The source parser is byte-identical to the first work package.
Original v1/v2 artifacts remain unchanged.

To rescore a historical v2 run after the current code has changed, use its saved
Python sources in an isolated import path:

```bash
PYTHONPATH=work/build-v2/implementation_source .venv/bin/python -m automated score \
  --build work/build-v2 --run work/runs/rule-v2 --output work/my-historical-score.json
```

This historical path was executed and reproduced the old result exactly. New
code requires a new build rather than reinterpreting old run metadata.

All branches stay within their storm group. Exact source-byte duplicates are
checked across splits; broader near-duplicate/template similarity and pretraining
contamination are not established. The heldout set uses the same source template
and task schema and is not a hidden benchmark. Weather phases differ across the
fixed advisory numbers. Read the data card before interpreting model comparisons.
