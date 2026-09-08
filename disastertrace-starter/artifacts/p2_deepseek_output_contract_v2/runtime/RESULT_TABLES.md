# P2 Captured Result Tables

Mode: `model_http`. Model calls: 270. Complete audited matrix: True.

Execution: `6285f92ac7af631816b272b14ff51f975464a11aabdca731815f581d607d684c`.
Audit: `e56e25662cb2cbee123704b824b2486ea73c476c7ee85e006ed161e47cce152f`.

## Source Groups

Source groups, matched branches and checkpoints are dependent observations. AL092021 and AL062018 use primary cases; AL052019 uses secondary cases.

| Source | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |
| --- | --- | --- | --- | --- | --- | --- |
| AL052019 | snapshot | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL052019 | structured_state | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL052019 | answer_history | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL062018 | snapshot | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL062018 | structured_state | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL062018 | answer_history | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL092021 | snapshot | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL092021 | structured_state | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |
| AL092021 | answer_history | 30/30 (100.00%) | 94/94 (100.00%) | 94/94 (100.00%) | 26/26 (100.00%) | 30/30 (100.00%) |

## Pooled Fixed-Denominator Scores

| Metric | snapshot | structured_state | answer_history |
| --- | --- | --- | --- |
| schema_success | 90/90 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) |
| known_value_accuracy | 282/282 (100.00%) | 282/282 (100.00%) | 282/282 (100.00%) |
| known_grounded_accuracy | 282/282 (100.00%) | 282/282 (100.00%) | 282/282 (100.00%) |
| unknown_accuracy | 78/78 (100.00%) | 78/78 (100.00%) | 78/78 (100.00%) |
| overall_grounding | 360/360 (100.00%) | 360/360 (100.00%) | 360/360 (100.00%) |
| action_accuracy | 90/90 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) |
| update_success | 90/90 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) |
| preservation | 192/192 (100.00%) | 192/192 (100.00%) | 192/192 (100.00%) |
| provenance_refresh | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| support_recovery | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| same_window_correction | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) |
| stale_replay_preservation | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) |
| scope_preservation | 6/6 (100.00%) | 6/6 (100.00%) | 6/6 (100.00%) |
| all_correct_checkpoints | 90/90 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) |

## Predeclared Family By Method Format Screen

Complete audited matrix, at least 29/30 schema-valid, at most one length finish.

| Family | Method | Schema | Length | Cell Passed |
| --- | --- | --- | --- | --- |
| U1 | snapshot | 30/30 | 0 | True |
| U2 | snapshot | 30/30 | 0 | True |
| U3 | snapshot | 30/30 | 0 | True |
| U1 | structured_state | 30/30 | 0 | True |
| U2 | structured_state | 30/30 | 0 | True |
| U3 | structured_state | 30/30 | 0 | True |
| U1 | answer_history | 30/30 | 0 | True |
| U2 | answer_history | 30/30 | 0 | True |
| U3 | answer_history | 30/30 | 0 | True |

Overall thresholds passed: True. Measured model screen passed: True.

## Family Scores

| Family | Method | Schema | Known Value | Known Grounded | Unknown | All Correct |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | snapshot | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U1 | structured_state | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U1 | answer_history | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U2 | snapshot | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U2 | structured_state | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U2 | answer_history | 30/30 (100.00%) | 96/96 (100.00%) | 96/96 (100.00%) | 24/24 (100.00%) | 30/30 (100.00%) |
| U3 | snapshot | 30/30 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) | 30/30 (100.00%) | 30/30 (100.00%) |
| U3 | structured_state | 30/30 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) | 30/30 (100.00%) | 30/30 (100.00%) |
| U3 | answer_history | 30/30 (100.00%) | 90/90 (100.00%) | 90/90 (100.00%) | 30/30 (100.00%) | 30/30 (100.00%) |

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
    "prompt_tokens": 609487,
    "completion_tokens": 283699,
    "total_tokens": 893186
  },
  "verified_usage_responses": 270,
  "failure_counts": {},
  "failure_categories_overlap": true,
  "latency_seconds": {
    "count": 270,
    "mean": 8.59359543848162,
    "median": 6.820463279727846,
    "p95": 25.348523046821356,
    "maximum": 53.45186558831483
  },
  "cost_estimate": {
    "basis": "captured_price_snapshot",
    "usd": "0.267236704",
    "covered_attempts": 270,
    "all_attempts_covered": true,
    "statuses": {
      "estimated_from_capture": 270
    },
    "is_invoice": false
  },
  "conservative_settled_usd": "0.64265696",
  "unsettled_reservation_usd": "0",
  "unknown_reservation_usd": "0",
  "requested_output_tokens_reserved": 2211840
}
```

Generated without extra model calls, score repair, human item labels or an LLM judge.
