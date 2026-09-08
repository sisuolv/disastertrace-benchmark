# P2 Captured Result Tables

Mode: `model_http`. Model calls: 270. Complete audited matrix: True.

Execution: `67b01bc7bf8d6e6ef8e27fd2aab31999e0745080b055acd887b9c5edbcabc8a4`.
Audit: `83f4e1a4432022a73befbab49cd3a4669b55973db8131ccc32ab5f24d1a56f95`.

## Source Groups

Source groups, matched branches and checkpoints are dependent observations. AL092021 and AL062018 use primary cases; AL052019 uses secondary cases.

| Source | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |
| --- | --- | --- | --- | --- | --- | --- |
| AL052019 | snapshot | 28/30 (93.33%) | 86/94 (91.49%) | 85/94 (90.43%) | 26/26 (100.00%) | 27/30 (90.00%) |
| AL052019 | structured_state | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL052019 | answer_history | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL062018 | snapshot | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL062018 | structured_state | 29/30 (96.67%) | 90/94 (95.74%) | 90/94 (95.74%) | 26/26 (100.00%) | 29/30 (96.67%) |
| AL062018 | answer_history | 29/30 (96.67%) | 91/94 (96.81%) | 91/94 (96.81%) | 25/26 (96.15%) | 29/30 (96.67%) |
| AL092021 | snapshot | 30/30 (100.00%) | 94/94 (100.00%) | 92/94 (97.87%) | 26/26 (100.00%) | 29/30 (96.67%) |
| AL092021 | structured_state | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL092021 | answer_history | 28/30 (93.33%) | 86/94 (91.49%) | 86/94 (91.49%) | 26/26 (100.00%) | 28/30 (93.33%) |

## Pooled Fixed-Denominator Scores

| Metric | snapshot | structured_state | answer_history |
| --- | --- | --- | --- |
| schema_success | 88/90 (97.78%) | 89/90 (98.89%) | 87/90 (96.67%) |
| known_value_accuracy | 274/282 (97.16%) | 278/282 (98.58%) | 271/282 (96.10%) |
| known_grounded_accuracy | 271/282 (96.10%) | 278/282 (98.58%) | 271/282 (96.10%) |
| unknown_accuracy | 78/78 (100.00%) | 78/78 (100.00%) | 77/78 (98.72%) |
| overall_grounding | 349/360 (96.94%) | 356/360 (98.89%) | 348/360 (96.67%) |
| action_accuracy | 88/90 (97.78%) | 89/90 (98.89%) | 87/90 (96.67%) |
| update_success | 90/90 (100.00%) | 90/90 (100.00%) | 88/90 (97.78%) |
| preservation | 181/192 (94.27%) | 188/192 (97.92%) | 183/192 (95.31%) |
| provenance_refresh | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| support_recovery | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| same_window_correction | 3/3 (100.00%) | 3/3 (100.00%) | 2/3 (66.67%) |
| stale_replay_preservation | 5/6 (83.33%) | 5/6 (83.33%) | 6/6 (100.00%) |
| scope_preservation | 5/6 (83.33%) | 6/6 (100.00%) | 6/6 (100.00%) |
| all_correct_checkpoints | 86/90 (95.56%) | 89/90 (98.89%) | 87/90 (96.67%) |

## Predeclared Family By Method Format Screen

Complete audited matrix, at least 29/30 schema-valid, at most one length finish.

| Family | Method | Schema | Length | Cell Passed |
| --- | --- | --- | --- | --- |
| U1 | snapshot | 30/30 | 0 | True |
| U2 | snapshot | 28/30 | 1 | False |
| U3 | snapshot | 30/30 | 0 | True |
| U1 | structured_state | 30/30 | 0 | True |
| U2 | structured_state | 29/30 | 1 | True |
| U3 | structured_state | 30/30 | 0 | True |
| U1 | answer_history | 30/30 | 0 | True |
| U2 | answer_history | 28/30 | 0 | False |
| U3 | answer_history | 29/30 | 0 | True |

Overall thresholds passed: False. Measured model screen passed: False.

## Family Scores

| Family | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | snapshot | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U1 | structured_state | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U1 | answer_history | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U2 | snapshot | 28/30 (93.33%) | 88/96 (91.67%) | 88/96 (91.67%) | 24/24 (100.00%) | 28/30 (93.33%) |
| U2 | structured_state | 29/30 (96.67%) | 92/96 (95.83%) | 92/96 (95.83%) | 24/24 (100.00%) | 29/30 (96.67%) |
| U2 | answer_history | 28/30 (93.33%) | 88/96 (91.67%) | 88/96 (91.67%) | 24/24 (100.00%) | 28/30 (93.33%) |
| U3 | snapshot | 30/30 (100.00%) | 90/90 (100.00%) | 87/90 (96.67%) | 30/30 (100.00%) | 28/30 (93.33%) |
| U3 | structured_state | 30/30 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) | 30/30 (100.00%) | 30/30 (100.00%) |
| U3 | answer_history | 29/30 (96.67%) | 87/90 (96.67%) | 87/90 (96.67%) | 29/30 (96.67%) | 29/30 (96.67%) |

## Operations

Failure categories may overlap. Conditional cost estimates are not invoices. P1's unknown original attempt 79 is outside this P2 ledger.

```json
{
  "planned": 270,
  "attempted": 270,
  "received": 270,
  "completed": 270,
  "unsubmitted": 0,
  "stop_reason": null,
  "usage": {
    "prompt_tokens": 459121,
    "completion_tokens": 329882,
    "total_tokens": 789003
  },
  "verified_usage_responses": 270,
  "failure_counts": {
    "answer_schema_invalid": 6,
    "empty_content": 2,
    "length": 2
  },
  "failure_categories_overlap": true,
  "latency_seconds": {
    "count": 270,
    "mean": 10.185769228233646,
    "median": 7.826996628660709,
    "p95": 26.625379300676286,
    "maximum": 69.52308638487011
  },
  "cost_estimate": {
    "basis": "captured_price_snapshot",
    "usd": "0.298880548",
    "covered_attempts": 270,
    "all_attempts_covered": true,
    "statuses": {
      "estimated_from_capture": 270
    },
    "is_invoice": false
  },
  "conservative_settled_usd": "0.63745748",
  "unsettled_reservation_usd": "0",
  "unknown_reservation_usd": "0",
  "requested_output_tokens_reserved": 2211840
}
```

Generated without extra model calls, score repair, human item labels or an LLM judge.
