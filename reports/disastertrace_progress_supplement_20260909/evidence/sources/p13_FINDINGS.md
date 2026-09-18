# P13: verified model-condition results

DeepSeek receives the same contract text in the user message, under default JSON separator spacing.

These are separately generated, pre-registered development runs: six storms,
36 original NHC products, 144 targets, 804 future checkpoints per method,
three methods and one repeat. All methods receive the same cumulative
visible source documents. Only their additional own-answer carriers differ.

## Fixed-denominator results

| Model | Returned / planned | Shape valid | Strict correct / planned | Strict % | Unattempted | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek-ai/DeepSeek-R1-Distill-Qwen-7B | 2064/2412 | 2011 | 6/2412 | 0.2488 | 348 | 0 |

Unreturned slots remain in the primary denominator. An audit pass means the
recorded run reconstructs; collection completeness and GPU success are separate.

## deepseek-ai/DeepSeek-R1-Distill-Qwen-7B

| Method | Returned / 804 | Strict correct / 804 | Whole targets correct / 144 | Fully captured targets / 144 |
| --- | ---: | ---: | ---: | ---: |
| snapshot | 686 | 0 | 0 | 26 |
| structured_state | 686 | 3 | 0 | 26 |
| answer_history | 692 | 3 | 0 | 32 |

### Reference status groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| DISSIPATED | 0/10 | 0/10 | 0/10 |
| not_stated | 0/196 | 3/196 | 3/196 |
| numeric | 0/598 | 0/598 | 0/598 |

### Reference storm groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| AL052019 | 0/134 | 1/134 | 0/134 |
| AL072022 | 0/134 | 0/134 | 1/134 |
| AL082021 | 0/134 | 0/134 | 1/134 |
| AL092020 | 0/134 | 1/134 | 0/134 |
| AL092024 | 0/134 | 0/134 | 1/134 |
| AL132023 | 0/134 | 1/134 | 0/134 |

### Reference transition groups

Cells show strict correct / planned; checkpoints within a storm are dependent.

| Group | snapshot | structured_state | answer_history |
| --- | ---: | ---: | ---: |
| changed_wind | 0/96 | 0/96 | 0/96 |
| first_checkpoint | 0/144 | 3/144 | 2/144 |
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
  "correct": 6,
  "invalid_json_shape": 53,
  "missing_response": 348,
  "unseen_source": 1,
  "wrong_key": 338,
  "wrong_locator": 2,
  "wrong_source_version": 1,
  "wrong_value_status_or_unit": 1663
}
```

Observed unit strings among shape-valid outputs:

```json
{
  "latitude": {
    "D": 17,
    "D basketball": 1,
    "DE": 32,
    "DEGREE": 3,
    "DFT": 7,
    "DFTC": 1,
    "DMS": 3,
    "DST": 2,
    "DT": 2,
    "KT": 8,
    "N": 1326,
    "NE": 1,
    "NM": 1,
    "NN": 4,
    "abs": 1,
    "d": 5,
    "deg": 271,
    "degree": 130,
    "degrees": 177,
    "kn": 1,
    "kt": 1,
    "latitude": 1,
    "string": 3,
    "\u00b0": 2,
    "\u00b0C": 1,
    "\u00b0N": 10
  },
  "longitude": {
    "D": 11,
    "D kite": 1,
    "DD": 2,
    "DE": 17,
    "DEGREE": 3,
    "DFT": 6,
    "DFTC": 1,
    "DL": 2,
    "DMS": 3,
    "DST": 4,
    "DT": 4,
    "E": 114,
    "EE": 5,
    "EW": 1,
    "KT": 8,
    "NE": 1,
    "NM": 1,
    "NS": 1,
    "W": 1223,
    "abs": 1,
    "d": 2,
    "deg": 271,
    "degree": 130,
    "degrees": 177,
    "f": 2,
    "kt": 2,
    "longitude": 1,
    "s": 1,
    "string": 3,
    "\u00b0": 2,
    "\u00b0C": 1,
    "\u00b0E": 4,
    "\u00b0W": 6
  },
  "max_sustained_wind": {
    "": 2,
    "KNOT": 1,
    "KT": 1995,
    "knots": 5,
    "kt": 8
  }
}
```

Finish reasons: `{"length": 53, "stop": 2011}`.
Shape by finish reason: `{"length": {"shape_invalid": 53}, "stop": {"shape_valid": 2011}}`.
Reasoning-extraction errors: 7.
Output tokens: 2265726; generation-job H100 allocation hours: 2.8650000.
Final-text whitespace characters: 53711; maximum per answer: 50.

Whitespace includes strings. Allocation hours include model loading and worker
lifetime, exclude separate preflights, and are neither device utilization nor cost.

| Worker | Job | ACP terminal state | Returned / planned | Stop reason | Error |
| --- | --- | --- | ---: | --- | --- |
| 0 | pt-hlskn0oj | FAILED | 1030/1206 | exception | ValueError: context budget exceeded; no truncation allowed |
| 1 | pt-ynwy8zym | FAILED | 1034/1206 | exception | ValueError: context budget exceeded; no truncation allowed |

All listed allocations are terminal and released. A context-guard failure
retains the original whole-worker stopping behavior; this phase does not
isolate the oversized trajectory or retry its unrelated remaining slots.

Report ID: `c9af22d325fa63892a8db69475d9a371583eafda426064586b54119730010421`.
Analysis ID: `a1f88a82f7bf16681e48e48a76d7b15e69b6ca42f4e6044ea51833743d88e197`.
Verified finalization: `artifacts/p13_prompt_role_v1/finalization_deepseek_r1_01`.
Analysis location record: `artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_p13_deepseek_r1.json`.

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
