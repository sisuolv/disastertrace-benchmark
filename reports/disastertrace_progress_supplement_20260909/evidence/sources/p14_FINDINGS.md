# P14: verified model-condition results

Qwen receives the same contract text in the user message, under default JSON separator spacing.

These are separately generated, pre-registered development runs: six storms,
36 original NHC products, 144 targets, 804 future checkpoints per method,
three methods and one repeat. All methods receive the same cumulative
visible source documents. Only their additional own-answer carriers differ.

## Fixed-denominator results

| Model | Returned / planned | Shape valid | Strict correct / planned | Strict % | Unattempted | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen/Qwen3-8B | 1628/2412 | 1628 | 952/2412 | 39.4693 | 780 | 4 |

Unreturned slots remain in the primary denominator. An audit pass means the
recorded run reconstructs; collection completeness and GPU success are separate.

## Qwen/Qwen3-8B

| Method | Returned / 804 | Strict correct / 804 | Whole targets correct / 144 | Fully captured targets / 144 |
| --- | ---: | ---: | ---: | ---: |
| snapshot | 543 | 315 | 8 | 18 |
| structured_state | 540 | 340 | 10 | 18 |
| answer_history | 545 | 297 | 10 | 18 |

### Reference status groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| DISSIPATED | 2/10 | 2/10 | 1/10 |
| not_stated | 180/196 | 188/196 | 181/196 |
| numeric | 133/598 | 150/598 | 115/598 |

### Reference storm groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| AL052019 | 51/134 | 68/134 | 57/134 |
| AL072022 | 53/134 | 54/134 | 48/134 |
| AL082021 | 54/134 | 53/134 | 51/134 |
| AL092020 | 50/134 | 50/134 | 42/134 |
| AL092024 | 51/134 | 52/134 | 44/134 |
| AL132023 | 56/134 | 63/134 | 55/134 |

### Reference transition groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| changed_wind | 26/96 | 17/96 | 6/96 |
| first_checkpoint | 115/144 | 119/144 | 112/144 |
| first_explicit | 33/97 | 34/97 | 32/97 |
| no_new_coverage | 48/326 | 75/326 | 57/326 |
| still_not_stated | 87/99 | 92/99 | 86/99 |
| unchanged_wind | 6/42 | 3/42 | 4/42 |

Numeric-only strict correctness is 398/1794 (22.1851%).
Headline correctness also includes not_stated and DISSIPATED cases.

### Errors, output and resources

Disjoint primary errors use precedence; component errors can overlap.

```json
{
  "correct": 952,
  "missing_response": 784,
  "wrong_key": 1,
  "wrong_locator": 339,
  "wrong_source_version": 15,
  "wrong_value_status_or_unit": 321
}
```

Observed unit strings among shape-valid outputs:

```json
{
  "latitude": {
    "deg": 1628
  },
  "longitude": {
    "deg": 1628
  },
  "max_sustained_wind": {
    "KT": 1628
  }
}
```

Finish reasons: `{"stop": 1628}`.
Shape by finish reason: `{"stop": {"shape_valid": 1628}}`.
Reasoning-extraction errors: 0.
Output tokens: 2212236; generation-job H100 allocation hours: 3.2605556.
Final-text whitespace characters: 43782; maximum per answer: 29.

Whitespace includes strings. Allocation hours include model loading and worker
lifetime, exclude separate preflights, and are neither device utilization nor cost.

| Worker | Job | ACP terminal state | Returned / planned | Stop reason | Error |
| --- | --- | --- | ---: | --- | --- |
| 0 | pt-x2iaxacb | FAILED | 778/1206 | unavailable | none |
| 1 | pt-tqcs7ii3 | FAILED | 850/1206 | unavailable | none |

All listed allocations are terminal and released. A context-guard failure
retains the original whole-worker stopping behavior; this phase does not
isolate the oversized trajectory or retry its unrelated remaining slots.

Report ID: `cfd6368dc983a2a0904a92623a69777e636164422d7db1cb2104adb79ba3e054`.
Analysis ID: `854d2892fed6cad0944322b95f932febbf7ae02d8312e48daa2212416536e863`.
Verified finalization: `artifacts/p14_qwen_prompt_role_v1/finalization_qwen3_01`.
Analysis location record: `artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_p14_qwen3.json`.

## Verification and interpretation limits

Report construction/verification, token-mask replay, relocated CPU review and
descriptive-analysis reconstruction all have successful command receipts.
Preserved initial CPU-observer failures and any fresh CPU continuation are
identified by the LOCATION record; no GPU answer is replaced by that recovery.

Default JSON separator spacing does not constrain correct values, units, source
versions or line locators. It must not be described as compact JSON with no spaces.
P11/P12/P13/P14 have their own generated histories. Their three role/spacing
cells are not a full factorial. Later dispatches have less time before the shared
02:05:16 UTC deadline; any resulting censoring is not a pure prompt-role effect.

The public deterministic resolver solves the task without private Gold. This
measures understanding and citation of published forecasts, not numerical weather
prediction. Six early-advisory development storms, English inputs, one repeat,
no terminal-revision checkpoints, uncertain historical availability and shared
Qwen ancestry limit population and model-family conclusions.

No unit normalization, answer repair, model retries, paid API, training, heldout
inference or per-item human/LLM judging is introduced.
