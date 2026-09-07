# Evidence scoring v2: completed offline work package

On 2026-09-06, the P0 optimization package was implemented and verified. It adds
restricted equivalent-citation support, fixed-reference transition metrics and
immutable historical rescoring. It uses deterministic code, requires no new
per-item human annotation/review, and makes **zero new model API requests**.

## Actual saved DeepSeek result

The same ten Ida development responses were scored with both implementations.
The archived v1 implementation exactly reproduces the original saved score.

| Metric | Original v1 | Derived v2 |
| --- | --- | --- |
| Valid responses | 10/10 | 10/10 |
| State values/statuses | 50/50 | 50/50 |
| Overall grounded fields, including correct unknowns | 49/50 | 50/50 |
| Known-only grounded fields | 31/32 | 32/32 |
| Correct unknown fields | 18/18 | 18/18 |
| Research-rule actions | 10/10 | 10/10 |

The known-only v1 count is derived by excluding its 18 correctly unknown slots.
There is exactly one changed field: maximum wind at base c4. The model reports
105 mph and cites advisory 011 line 88, an explicit current wind observation.
V1 accepts only summary line 21; v2 accepts the supported body citation too.
This corrects evidence validation of an unchanged answer, not model behavior.

New fixed-reference metrics report 22/22 semantic transitions, 18/18 semantic
preservations and 2/2 provenance refreshes. Semantic self-error recovery has
zero opportunities and is reported as 0/0 with a null rate, not perfect recovery.
The original model-dependent v1 metrics remain separately labeled diagnostics.

This is still one storm, one model and one method. It is not a heldout result,
cross-model ranking, general extreme-weather evaluation or isolated memory test.

## What is implemented

- `evidence_support.py`: existing summary locations plus bounded, declared NHC
  current-observation body forms for wind, latitude, longitude and pressure.
  It checks latest actually delivered report, entity/time applicability, field,
  exact canonical value/unit, locator and source-bound evidence-index integrity.
- `scoring_v2.py`: every supplied citation must pass; known facts need at least
  one citation. Known-only correctness, fixed Gold changes/preservation, source
  refresh, conditional error recovery, per-event macro and paired-branch
  correctness retain explicit counts and failed attempts.
- `rescoring.py`: verifies archived build/run/collection, loads the saved code
  in an isolated temporary namespace, reproduces v1 and saves v2 plus a complete
  per-field difference report under independent implementation/manifest hashes.

The body evaluator is a restricted extraction policy over admitted NHC records.
It is not general natural-language entailment. Unsupported forms return
`evaluator_unverifiable`; that reason must not automatically be called a model
hallucination. The canonical fact parser, episodes, answer schema, original
prompts and historical scores remain unchanged.

## Verification and artifacts

Full suite: **611 passed in 35.59 seconds, zero skipped**. Scoped Ruff
correctness/import checks pass, all 38 automated source/test files pass format
checks, and `pip check` passes. This adds 128 tests to the prior 483-test suite.
Regression-first failures, including the original strict-locator failure and
subsequent context-qualifier failures, are retained in the verification archive.

- Derived package: `work/deepseek-ida-rescore-v2/`.
- Original and new scores: `baseline_v1.json` and `score_v2.json` in that package.
- Per-field differences: `comparison.json`; evidence spans: `evidence_index_v2.json`.
- Full test command/log records: `artifacts/optimization_p0/final_checks/`.
- Real historical replay command/log records:
  `artifacts/optimization_p0/historical_rescore_checks/`.
- Independent acceptance: `artifacts/optimization_p0/acceptance.json` verifies
  exact v1 reproduction, 13 v2 metric expectations, one grounding difference,
  and 80 unchanged historical/protected files.

Implementation ID:
`58acc19bf32eb83709344c7f8c001b2d86d8b665339ef251a5cd7b774784e716`.
Derived package ID:
`e9450ff3b175e1ecc4999eb679a364cd4bbb1749e47b20e2404a20c9e521d049`.

The package binds raw saved requests/responses and reaudits their collection.
Verification recomputes both scoring versions and the comparison from saved
source snapshots. It does not merely trust reported metric values or file names.

An additional offline diagnostic matrix covers all three development storms,
three input methods and three program backends: nine configurations and 270
diagnostic responses, with zero API requests. Each configuration has 30
checkpoints, 150 fields, 64 fixed changes, 56 preservations and eight source
refresh opportunities. These denominators are identical across all nine runs.

| Diagnostic backend | Known-only grounded | Overall grounded | Fixed changes | Source refresh |
| --- | --- | --- | --- | --- |
| rule | 96/96 | 150/150 | 64/64 | 8/8 |
| last-arrival | 72/96 | 126/150 | 55/64 | 5/8 |
| no-update | 0/96 | 54/150 | 0/64 | 0/8 |

The rule program passes and both defective programs expose their intended
failures. Last-arrival has 24 stale-citation failures; correctly unknown answers
cannot hide no-update's zero known-field grounding. The results match across
methods for these programs, not necessarily for LLMs. Script, traces, scores,
source identities, all 39 verified result files and the report are under
`artifacts/optimization_p0/dev_diagnostics/`; command records are in
`execution.json`. No heldout event is evaluated by this diagnostic package.

## Commands

Verify the completed package without an API key:

```bash
.venv/bin/python -m disastertrace.automated.rescoring verify \
  --output work/deepseek-ida-rescore-v2
```

Reproduce into a fresh output directory:

```bash
.venv/bin/python -m disastertrace.automated.rescoring rescore \
  --build work/build-deepseek-v1 \
  --run work/deepseek-ida-state-v1/imported_run \
  --historical-score artifacts/deepseek_probe_v1/rescore.json \
  --output work/my-ida-rescore-v2
```

Original implementation/build guards are retained. Adding new source modules
changes the current implementation identity, so new model collections require
a fresh matching build; existing runs use the archived rescoring route above.
Never rewrite historical manifests or reuse existing output paths to bypass this.

Detailed specifications:
[evidence support](docs/EVIDENCE_SUPPORT_V2.md),
[metrics](docs/METRICS_V2.md), and
[offline rescoring](docs/OFFLINE_RESCORING.md).

## Next executable research package

P1 compares the 30 development checkpoints across structured_state, snapshot
and answer_history with fixed DeepSeek settings: 90 requests for one complete
repeat. Freeze its new build, scoring version, model configuration and spending
allowance before execution. The ten historical answers are not automatically
subtracted from that matrix. No broader model batch or heldout evaluation has
been executed by this work package. Richer controlled tasks and event expansion
remain subsequent phases in `OPTIMIZATION_ROADMAP.md`.
