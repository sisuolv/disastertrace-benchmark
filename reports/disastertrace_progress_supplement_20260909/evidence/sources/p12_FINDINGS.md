# P12: verified model-condition results

The system contract is retained; XGrammar uses default JSON separator spacing.

These are separately generated, pre-registered development runs: six storms,
36 original NHC products, 144 targets, 804 future checkpoints per method,
three methods and one repeat. All methods receive the same cumulative
visible source documents. Only their additional own-answer carriers differ.

## Fixed-denominator results

| Model | Returned / planned | Shape valid | Strict correct / planned | Strict % | Unattempted | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | 1994/2412 | 1943 | 9/2412 | 0.3731 | 418 | 0 |
| Qwen/Qwen3-8B | 2412/2412 | 2412 | 1060/2412 | 43.9469 | 0 | 0 |

Unreturned slots remain in the primary denominator. An audit pass means the
recorded run reconstructs; collection completeness and GPU success are separate.

## deepseek-ai/DeepSeek-R1-Distill-Qwen-7B

| Method | Returned / 804 | Strict correct / 804 | Whole targets correct / 144 | Fully captured targets / 144 |
| --- | ---: | ---: | ---: | ---: |
| snapshot | 667 | 3 | 0 | 34 |
| structured_state | 661 | 1 | 0 | 31 |
| answer_history | 666 | 5 | 0 | 39 |

### Reference status groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| DISSIPATED | 0/10 | 0/10 | 0/10 |
| not_stated | 3/196 | 1/196 | 5/196 |
| numeric | 0/598 | 0/598 | 0/598 |

### Reference storm groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| AL052019 | 1/134 | 0/134 | 0/134 |
| AL072022 | 1/134 | 0/134 | 0/134 |
| AL082021 | 0/134 | 0/134 | 2/134 |
| AL092020 | 0/134 | 0/134 | 3/134 |
| AL092024 | 1/134 | 0/134 | 0/134 |
| AL132023 | 0/134 | 1/134 | 0/134 |

### Reference transition groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| changed_wind | 0/96 | 0/96 | 0/96 |
| first_checkpoint | 3/144 | 1/144 | 4/144 |
| first_explicit | 0/97 | 0/97 | 0/97 |
| no_new_coverage | 0/326 | 0/326 | 0/326 |
| still_not_stated | 0/99 | 0/99 | 1/99 |
| unchanged_wind | 0/42 | 0/42 | 0/42 |

Numeric-only strict correctness is 0/1794 (0.0000%).
Headline correctness also includes not_stated and DISSIPATED cases.

### Errors, output and resources

Disjoint primary errors use precedence; component errors can overlap.

```json
{
  "correct": 9,
  "invalid_json_shape": 51,
  "missing_response": 418,
  "wrong_key": 362,
  "wrong_locator": 1,
  "wrong_source_version": 4,
  "wrong_value_status_or_unit": 1567
}
```

Observed unit strings among shape-valid outputs:

```json
{
  "latitude": {
    "00": 1,
    "D": 10,
    "DE": 32,
    "DE Laurenso": 1,
    "DECTAC": 1,
    "DEGREE": 6,
    "DEK": 1,
    "DET": 1,
    "DFT": 5,
    "DMS": 5,
    "DPT": 2,
    "DST": 4,
    "Degrees": 1,
    "D\u58ee": 1,
    "KT": 14,
    "N": 1268,
    "NM": 3,
    "NT": 1,
    "S": 1,
    "SCT": 1,
    "d": 2,
    "deg": 198,
    "degree": 130,
    "degrees": 209,
    "kt": 2,
    "latitude": 1,
    "\u00b0": 19,
    "\u00b0D": 1,
    "\u00b0N": 22
  },
  "longitude": {
    "'": 1,
    "00": 1,
    "D": 8,
    "DD": 4,
    "DE": 19,
    "DE Laurenso": 1,
    "DECTAC": 1,
    "DEGREE": 6,
    "DEK": 1,
    "DET": 1,
    "DFT": 5,
    "DG": 1,
    "DL": 1,
    "DMS": 5,
    "DPT": 2,
    "DST": 4,
    "DT": 1,
    "Degrees": 1,
    "D\u58ee": 1,
    "E": 78,
    "EW": 1,
    "KT": 14,
    "NM": 3,
    "NT": 1,
    "OF": 2,
    "SCT": 1,
    "W": 1196,
    "d": 2,
    "deg": 198,
    "degree": 130,
    "degrees": 209,
    "kt": 2,
    "longitude": 1,
    "\u00b0": 18,
    "\u00b0D": 1,
    "\u00b0E": 15,
    "\u00b0W": 7
  },
  "max_sustained_wind": {
    "": 2,
    "KT": 1922,
    "Knots": 1,
    "knots": 10,
    "kt": 6,
    "kts": 1,
    "mph": 1
  }
}
```

Finish reasons: `{"length": 51, "stop": 1943}`.
Shape by finish reason: `{"length": {"shape_invalid": 51}, "stop": {"shape_valid": 1943}}`.
Reasoning-extraction errors: 12.
Output tokens: 2094655; generation-job H100 allocation hours: 2.6797222.
Final-text whitespace characters: 51783; maximum per answer: 53.

Whitespace includes strings. Allocation hours include model loading and worker
lifetime, exclude separate preflights, and are neither device utilization nor cost.

| Worker | Job | ACP terminal state | Returned / planned | Stop reason | Error |
| --- | --- | --- | ---: | --- | --- |
| 0 | pt-f7z0k9zq | FAILED | 928/1206 | exception | ValueError: context budget exceeded; no truncation allowed |
| 1 | pt-t2ldse6g | FAILED | 1066/1206 | exception | ValueError: context budget exceeded; no truncation allowed |

All listed allocations are terminal and released. A context-guard failure
retains the original whole-worker stopping behavior; this phase does not
isolate the oversized trajectory or retry its unrelated remaining slots.

Report ID: `1de6e0c9e946358255996f17eb02027f55b59a636ec37b7ff94e62426fb2008e`.
Analysis ID: `8b094b7555ed18f8706c3609557e6ad81ae801d28fb63f2b9b5d8cade67633c3`.
Verified finalization: `artifacts/p12_compact_grammar_v1/finalization_deepseek_r1_02`.
Analysis location record: `artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_p12_deepseek_r1.json`.

## Qwen/Qwen3-8B

| Method | Returned / 804 | Strict correct / 804 | Whole targets correct / 144 | Fully captured targets / 144 |
| --- | ---: | ---: | ---: | ---: |
| snapshot | 804 | 369 | 6 | 144 |
| structured_state | 804 | 369 | 23 | 144 |
| answer_history | 804 | 322 | 13 | 144 |

### Reference status groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| DISSIPATED | 2/10 | 7/10 | 4/10 |
| not_stated | 176/196 | 184/196 | 185/196 |
| numeric | 191/598 | 178/598 | 133/598 |

### Reference storm groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| AL052019 | 65/134 | 67/134 | 64/134 |
| AL072022 | 57/134 | 55/134 | 57/134 |
| AL082021 | 55/134 | 56/134 | 45/134 |
| AL092020 | 60/134 | 64/134 | 42/134 |
| AL092024 | 65/134 | 69/134 | 61/134 |
| AL132023 | 67/134 | 58/134 | 53/134 |

### Reference transition groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| changed_wind | 39/96 | 27/96 | 6/96 |
| first_checkpoint | 108/144 | 116/144 | 108/144 |
| first_explicit | 34/97 | 26/97 | 29/97 |
| no_new_coverage | 79/326 | 97/326 | 81/326 |
| still_not_stated | 90/99 | 93/99 | 94/99 |
| unchanged_wind | 19/42 | 10/42 | 4/42 |

Numeric-only strict correctness is 502/1794 (27.9822%).
Headline correctness also includes not_stated and DISSIPATED cases.

### Errors, output and resources

Disjoint primary errors use precedence; component errors can overlap.

```json
{
  "correct": 1060,
  "wrong_key": 10,
  "wrong_locator": 488,
  "wrong_source_version": 32,
  "wrong_value_status_or_unit": 822
}
```

Observed unit strings among shape-valid outputs:

```json
{
  "latitude": {
    "deg": 2412
  },
  "longitude": {
    "deg": 2412
  },
  "max_sustained_wind": {
    "KT": 2412
  }
}
```

Finish reasons: `{"stop": 2412}`.
Shape by finish reason: `{"stop": {"shape_valid": 2412}}`.
Reasoning-extraction errors: 0.
Output tokens: 3276610; generation-job H100 allocation hours: 5.0730556.
Final-text whitespace characters: 65823; maximum per answer: 29.

Whitespace includes strings. Allocation hours include model loading and worker
lifetime, exclude separate preflights, and are neither device utilization nor cost.

| Worker | Job | ACP terminal state | Returned / planned | Stop reason | Error |
| --- | --- | --- | ---: | --- | --- |
| 0 | pt-q7di6zkl | SUCCEEDED | 1206/1206 | complete | none |
| 1 | pt-rreg5y15 | SUCCEEDED | 1206/1206 | complete | none |

All listed allocations are terminal and released. A context-guard failure
retains the original whole-worker stopping behavior; this phase does not
isolate the oversized trajectory or retry its unrelated remaining slots.

Report ID: `e7725945d1128b8ef7f0b56289fd406b373aab2008b5d1a2cc6744fed5a1ca2b`.
Analysis ID: `9646b79d544535fb083e79abb8f10cc516d309b74101ea76bd5e6ff12ca238ab`.
Verified finalization: `artifacts/p12_compact_grammar_v1/finalization_qwen3_02`.
Analysis location record: `artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_p12_qwen3.json`.

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
