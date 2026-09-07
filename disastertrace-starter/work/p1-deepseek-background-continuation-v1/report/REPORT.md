# P1 explicitly amended DeepSeek continuation

Status: completed_amended_continuation. Original interrupted no-retry experiment is retained separately.

The primary score is V2 known-value grounding on all 96 known-field opportunities per method. Correct values must have citations accepted by the frozen policy. Schema failures and missing checkpoints remain in denominators.

| Method | Received / planned | Schema | V2 known grounding (primary) | V2 all fields | V1 all fields |
| --- | --- | --- | --- | --- | --- |
| snapshot | 30/30 | 14/30 (46.67%) | 39/96 (40.62%) | 69/150 (46.00%) | 65/150 (43.33%) |
| structured_state | 30/30 | 30/30 (100.00%) | 96/96 (100.00%) | 150/150 (100.00%) | 139/150 (92.67%) |
| answer_history | 30/30 | 24/30 (80.00%) | 76/96 (79.17%) | 120/150 (80.00%) | 120/150 (80.00%) |

## Per-event V2 results

| Method | Storm | Schema | Known grounding | All-field grounding |
| --- | --- | --- | --- | --- |
| snapshot | AL052019 | 4/10 (40.00%) | 12/32 (37.50%) | 20/50 (40.00%) |
| snapshot | AL062018 | 5/10 (50.00%) | 11/32 (34.38%) | 24/50 (48.00%) |
| snapshot | AL092021 | 5/10 (50.00%) | 16/32 (50.00%) | 25/50 (50.00%) |
| structured_state | AL052019 | 10/10 (100.00%) | 32/32 (100.00%) | 50/50 (100.00%) |
| structured_state | AL062018 | 10/10 (100.00%) | 32/32 (100.00%) | 50/50 (100.00%) |
| structured_state | AL092021 | 10/10 (100.00%) | 32/32 (100.00%) | 50/50 (100.00%) |
| answer_history | AL052019 | 9/10 (90.00%) | 28/32 (87.50%) | 45/50 (90.00%) |
| answer_history | AL062018 | 5/10 (50.00%) | 16/32 (50.00%) | 25/50 (50.00%) |
| answer_history | AL092021 | 10/10 (100.00%) | 32/32 (100.00%) | 50/50 (100.00%) |

Full V1/V2 per-event, event-macro, branch and descriptive paired differences are in report.json. No significance inference is made from three storms and one repeat.

## Failures and conditional diagnostics

- snapshot: {'empty_final_at_output_limit': 12, 'partial_or_invalid_json_at_output_limit': 2, 'state_action_structure_swapped': 1, 'wrong_action_json_type': 1}. Secondary valid-only: 14 checkpoints, grounded fields 69/70 (98.57%).
- structured_state: {}. Secondary valid-only: 30 checkpoints, grounded fields 150/150 (100.00%).
- answer_history: {'empty_final_at_output_limit': 6}. Secondary valid-only: 24 checkpoints, grounded fields 120/120 (100.00%).

Valid-only diagnostics select on successful formatting and must not replace the fixed-denominator scores. evaluator_unverifiable is a restricted-grammar support result, not automatically a hallucination.

## Calls, usage, costs and timing

Cumulative admitted calls: 91; new continuation calls: 12; received benchmark responses: 90; planned scoring opportunities: 90.

Original attempt 79 remains unresolved outside the benchmark collection; attempt 80 explicitly reissues its exact payload. The received 78 original answers, including invalid answers, are retained without retry.

Actual total expense remains unknown. Cache-aware received-response subtotal at declared rates: USD 0.146989544. This subtotal is not the total bill and excludes unreported usage from original attempt 79.

Conservative reported peak-rate accounting: USD 0.354178; pending reservation: USD 0.46678016; remaining conditional allowance: USD 0.67904184. The original USD 0.46678016 reservation is retained; reservations are not measured charges.

Reported token totals: {'prompt_tokens': 293816, 'completion_tokens': 170378, 'total_tokens': 464194, 'prompt_cache_hit_tokens': 141312, 'prompt_cache_miss_tokens': 152504, 'reasoning_tokens': 158370}. Reasoning tokens are already included in completion tokens.

| Method | Transport mean seconds | p50 | p95 | Observed cache-aware subtotal USD |
| --- | --- | --- | --- | --- |
| snapshot | 19.832 | 25.157 | 30.067 | 0.066161104 |
| structured_state | 6.782 | 5.816 | 13.521 | 0.022414064 |
| answer_history | 14.154 | 10.286 | 31.630 | 0.058414376 |

metadata.elapsed_seconds: monotonic time immediately before HTTP transport through return of all response bytes; excludes response parsing, scoring and inter-request work. Failed transport attempts have no saved latency. p50/p95 use linear interpolation at (n-1)*q on sorted observed durations.

## Interpretation and provenance

Descriptive development calibration: one model and one repeat; event count is explicit. All methods see all delivered evidence. Branches and checkpoints within a storm are dependent. No statistical significance, universal ranking, causal memory benefit, heldout result or certified leaderboard claim is established. Fixed-denominator rates retain unsuccessful and unsubmitted checkpoints. Conditional self-error recovery is reported separately. Fixed method order can confound latency and provider-cache comparisons with execution order. This is an explicitly amended continuation with a machine restart and one authorized uncertain-request retry. Total cost remains unknown.

The continuation is a separately authorized amendment with USD 1.5 cumulative conditional allowance, at most 12 additional and 91 cumulative attempts, one explicit uncertain-request retry, no automatic retries and no heldout calls. It is not the original uninterrupted 90-request experiment. The restart adds a time/cache confound.

The output prompt does not explicitly state that action is a string; prior valid carrier answers also supply format examples. These are candidate explanations to test in a later controlled output-contract and output-budget study, not proven causes. All methods see cumulative delivered evidence; this experiment does not isolate memory dependence.

Original source files, raw answers, frozen code/data/scorers, journals and prior partial results are preserved. This report makes zero API calls and uses deterministic scoring without new item-level human annotation or an LLM judge.
