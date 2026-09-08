# P6 paired Qwen3-8B results and NHC source review

## Actual execution

ACP job `pt-gxxtikov` is `FAILED`. One full H100 runs the entire paired matrix.
Execution: `1935624436c9ee3edface4c53a1dabab7516c7e0742440db3628ec435c700bf9`. Independent model audit: `c394013b6676c141ee039836488fe559eff3057fda41b1d50c9dca249aae1c5e`.
Received **2160/2160** model answers; attempted 2160; unresolved 0; unsubmitted 0.
The model capture is complete: `True`. Original worker subprocesses all pass: `False`.
The collector exits0 with all2160 answers. The original report and verify steps exit1 because the auditor incorrectly expected the rendered EOS marker despite include_stop_str_in_output=false. The ACP job therefore remains FAILED. A separately frozen CPU reviewer checks the exact bound stop-token rendering policy, preserves extraction/scoring and reconstructs the complete capture. All2160 runtime texts match that policy. Ten CPU regression tests and two installed-vLLM detokenizer tests pass; the initial two regression failures and original failed reports remain. The subsequent finalization_002 verifies the reports without another model generation.
Schema-valid answers: **2160/2160**. Fully correct checkpoints: **1861/2160 (86.2%)**.
Format screens passed: **36/36**.

The conditions are base and irrelevant_scope level4. Each contains36 development episodes, five checkpoints, three methods and two repeats. Sampling is paired across conditions; method and repeat remain in the seed key. Carriers are isolated by trajectory. No failed answer was retried, replaced or repaired.

## Method and repeat results

| Condition | Method | Repeat0 correct /180 | Repeat1 correct /180 | Combined /360 | Successful trajectories /72 | Episode pass^2 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| base | snapshot | 171 | 169 | 340 (94.4%) | 55 (76.4%) | 22/36 (61.1%) |
| base | structured_state | 171 | 178 | 349 (96.9%) | 64 (88.9%) | 30/36 (83.3%) |
| base | answer_history | 144 | 135 | 279 (77.5%) | 37 (51.4%) | 13/36 (36.1%) |
| irrelevant_scope | snapshot | 152 | 157 | 309 (85.8%) | 31 (43.1%) | 11/36 (30.6%) |
| irrelevant_scope | structured_state | 157 | 162 | 319 (88.6%) | 43 (59.7%) | 15/36 (41.7%) |
| irrelevant_scope | answer_history | 139 | 126 | 265 (73.6%) | 34 (47.2%) | 10/36 (27.8%) |

Episode success requires all five checkpoints to be fully correct. With exactly two repeats, pass^2 is the fraction of base episodes that succeed in both repeats; it is not a checkpoint-level pass@k metric or a confidence bound.

## Paired outcomes

| Method | Exposure slice | Pairs | Both correct | Base only correct | Scope only correct | Both wrong |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| snapshot | before_first_exposure | 144 | 144 | 0 | 0 | 0 |
| snapshot | exposed | 216 | 151 | 45 | 14 | 6 |
| structured_state | before_first_exposure | 144 | 144 | 0 | 0 | 0 |
| structured_state | exposed | 216 | 168 | 37 | 7 | 4 |
| answer_history | before_first_exposure | 144 | 144 | 0 | 0 | 0 |
| answer_history | exposed | 216 | 97 | 38 | 24 | 57 |

Both directions of change are retained. These are closed-loop trajectory comparisons, so later differences include any effects of earlier model outputs on the carrier. They are not estimates of a direct isolated intervention on a fixed carrier.

| Checkpoint | Received pairs | Identical requests | Identical final text |
| --- | ---: | ---: | ---: |
| c0 | 216 | 216 | 216 |
| c1 | 216 | 216 | 216 |
| c2 | 216 | 0 | 137 |
| c3 | 216 | 0 | 114 |
| c4 | 216 | 0 | 111 |

Shared sampling seeds do not by themselves prove bitwise deterministic execution. The before-exposure outcome table and request/final-text agreement are empirical checks; any pre-exposure differences cannot be attributed to exposure to the distractor.

## Error attribution

Across 8640 received field opportunities, deterministic attribution finds 123 value/status/invalid errors and 259 citation-only errors. This reconciles to the frozen scorer.
Action errors: 43; these can overlap field errors and must not be added as independent failures.

- `status_or_value_mismatch`: 123
- `superseded_same_value`: 116
- `unknown_record_id`: 42
- `wrong_valid_window_or_measurement_kind`: 35
- `out_of_bounds_line`: 26
- `wrong_entity`: 22
- `wrong_variable_or_unit`: 10
- `superseded_different_value`: 8

All field-level attributions are in `analysis/fields.jsonl`; `analysis/examples.json` contains the first twelve erroneous fields in frozen schedule order. Example selection is deterministic, and the full error inventory is retained.

## Runtime and verification

Prompt tokens: 6,864,298; completion tokens: 2,662,561; reasoning tokens: 2,088,798.
Summed generation-batch wall time: 123.39 minutes. Collector wall time including model preparation: 128.33 minutes. These are measured worker intervals, not an inferred billing amount.
Token-mask replay checks 571,603 final/EOS tokens; constraint violations: 0; reasoning-only sequences: 0.
Relocated CPU reconstruction: `passed`, with original project/weights/network blocked and no Torch/vLLM.

95 relevant CPU tests pass, plus one installed-vLLM cached-tokenizer regression. The initial live freeze was cancelled before any generation when that regression exposed an overly strict class-name check. Both generation-disabled H100 preflights, the initial failing regression, the cancellation claims and replacement freeze remain recorded. Correct/invalid program rehearsals are separate from all actual model results. Historical P6 offline acceptance reverifies without changing its5,703 bound files.

## Real forecast-source milestone

Planned NHC bodies:12; received:12; admitted:12; quarantined:0. The admitted products provide 95 forecast rows and 49 adjacent admitted-version pairs at identical absolute valid times; 23 pairs change sustained wind.
The selection is Francine AL062024005-010 and Ida AL092021009-014. All eight originally declared heldout storm IDs remain protected; Ian's supplied-plan exposure is recorded. Two independent parsers must agree. Failures go to automatic quarantine. Raw bytes, URLs, hashes, fetch metadata, canonical line/byte maps and lossless exports are retained.
26 source-pipeline CPU tests pass, including one80-example property test. The source stage performs zero LLM calls, human Gold annotations or LLM judging. Available-at and model initialization remain unknown; forecast pressure is not inferred from current pressure.
The first source command failed before networking because the minimal snapshot omitted package-import dependencies. source_execution_v2 supplies the preserved dependency closure without changing the frozen parsers, scope or original snapshot. finalization_003 verifies the import/scope, performs the single bounded acquisition and rebuilds its source review. No acquisition claim or HTTP attempt existed before that packaging correction.

See `../nhc_forecast_source_v1/PROTOCOL.md` and `../nhc_forecast_source_v1/review_v1/report.json` for coverage and quarantine reasons.

## Interpretation and next research step

The user requested more GPU parallelism during collection. The current TP=1 worker remained intact. A separate offline four-worker layout now assigns nine whole episodes, 540 opportunities,108 trajectories and270 pairs per worker, retaining all methods, conditions and repeats of an episode on the same GPU. Eighteen layout tests and actual schedule reconstruction pass. This is preparation for later collection/aggregation engineering; it submits no new GPU job and does not establish a measured speedup. See `../p6_parallel_preparation_v1/README.md`.

The model matrix contains only three independent storm sources and two repeats. Do not use synthetic variants as independent storms, report population significance, or declare a method universally superior. The source selection includes Francine as one candidate development storm beyond the existing Ida source; actual admission is reported above. It does not establish coverage across extreme-weather phenomena.

1. Freeze a separate forecast-claim task using exact absolute valid-time keys, explicit missing/terminal semantics and byte-grounded citations. Do not mix these archive facts with the controlled P6 scoreboard or label the task as numerical weather prediction.
2. Prepare equal-information JSON/text carrier controls with measured token differences and common input histories. Label raw and program-derived input tracks separately; the current normalized source exports are review artifacts, not an executed representation study.
3. After that task, scorer, split and context budget are frozen, specify one matching second-model matrix. More sources, heldout refreshes, new phenomena and training require their own explicit designs; none are silently added to the completed2160 matrix.

Detailed implementation order and acceptance gates: `NEXT_RESEARCH_PLAN.md`.
