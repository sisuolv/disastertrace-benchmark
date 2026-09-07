# DeepSeek development method calibration

Status: incomplete_descriptive_only.

Descriptive development calibration: one model and one repeat; event count is explicit. All methods see all delivered evidence. Branches and checkpoints within a storm are dependent. No statistical significance, universal ranking, causal memory benefit, heldout result or certified leaderboard claim is established. Fixed-denominator rates retain unsuccessful and unsubmitted checkpoints. Conditional self-error recovery is reported separately. Fixed method order can confound latency and provider-cache comparisons with execution order.

Independent storms: 3; collector attempts: 79/90; provider calls admitted by external ledger: 79; methods present: 3/3. This report itself makes zero provider requests.

## V2 metrics

| Metric | snapshot | structured_state | answer_history |
| --- | --- | --- | --- |
| schema_success | 14/30 (46.67%) | 30/30 (100.00%) | 14/30 (46.67%) |
| state_accuracy | 70/150 (46.67%) | 150/150 (100.00%) | 70/150 (46.67%) |
| grounded_state | 69/150 (46.00%) | 150/150 (100.00%) | 70/150 (46.67%) |
| known_value_accuracy | 40/96 (41.67%) | 96/96 (100.00%) | 44/96 (45.83%) |
| known_grounded_accuracy | 39/96 (40.62%) | 96/96 (100.00%) | 44/96 (45.83%) |
| action_accuracy | 14/30 (46.67%) | 30/30 (100.00%) | 14/30 (46.67%) |
| unknown_accuracy | 30/54 (55.56%) | 54/54 (100.00%) | 26/54 (48.15%) |
| known_answer_coverage | 40/96 (41.67%) | 96/96 (100.00%) | 44/96 (45.83%) |
| gold_transition_success | 21/64 (32.81%) | 64/64 (100.00%) | 30/64 (46.88%) |
| gold_transition_value_success | 21/64 (32.81%) | 64/64 (100.00%) | 30/64 (46.88%) |
| gold_preservation | 29/56 (51.79%) | 56/56 (100.00%) | 25/56 (44.64%) |
| gold_preservation_grounded | 28/56 (50.00%) | 56/56 (100.00%) | 25/56 (44.64%) |
| self_error_recovery | 11/13 (84.62%) | 0/0 (undefined) | 0/0 (undefined) |
| self_error_recovery_value | 12/13 (92.31%) | 0/0 (undefined) | 0/0 (undefined) |
| provenance_refresh | 3/8 (37.50%) | 8/8 (100.00%) | 2/8 (25.00%) |
| all_correct_checkpoints | 13/30 (43.33%) | 30/30 (100.00%) | 14/30 (46.67%) |

V1 conditional change/preservation and V2 conditional self-error recovery are not interchangeable with fixed opportunity metrics. Zero opportunities are undefined, not perfect performance.

## Per-event grounding

| Method | Storm | V1 known grounding | V2 known grounding | V2 unknown |
| --- | --- | --- | --- | --- |
| snapshot | AL052019 | 12/32 (37.50%) | 12/32 (37.50%) | 8/18 (44.44%) |
| snapshot | AL062018 | 7/32 (21.88%) | 11/32 (34.38%) | 13/18 (72.22%) |
| snapshot | AL092021 | 16/32 (50.00%) | 16/32 (50.00%) | 9/18 (50.00%) |
| structured_state | AL052019 | 30/32 (93.75%) | 32/32 (100.00%) | 18/18 (100.00%) |
| structured_state | AL062018 | 24/32 (75.00%) | 32/32 (100.00%) | 18/18 (100.00%) |
| structured_state | AL092021 | 31/32 (96.88%) | 32/32 (100.00%) | 18/18 (100.00%) |
| answer_history | AL052019 | 0/32 (0.00%) | 0/32 (0.00%) | 0/18 (0.00%) |
| answer_history | AL062018 | 12/32 (37.50%) | 12/32 (37.50%) | 8/18 (44.44%) |
| answer_history | AL092021 | 32/32 (100.00%) | 32/32 (100.00%) | 18/18 (100.00%) |

## Telemetry

| Method | Collector attempts | Accepted / invalid | Prompt / completion tokens | Mean / p50 / p95 seconds | Estimated USD |
| --- | --- | --- | --- | --- | --- |
| snapshot | 30 | 14 / 16 | 94360 / 84860 | 19.832 / 25.157 / 30.067 | 0.066161104 |
| structured_state | 30 | 30 / 0 | 98081 / 27457 | 6.782 / 5.816 / 13.521 | 0.022414064 |
| answer_history | 19 | 14 / 4 | 63050 / 33090 | 13.980 / 9.693 / 31.720 | unknown |

metadata.elapsed_seconds: monotonic time immediately before HTTP transport through return of all response bytes; excludes response parsing, scoring and inter-request work. Failed transport attempts have no saved latency. p50/p95 use linear interpolation at (n-1)*q on sorted observed durations.

Reported totals: prompt_tokens=255491, completion_tokens=145407, total_tokens=400898, prompt_cache_hit_tokens=135296, prompt_cache_miss_tokens=120195, reasoning_tokens=135081.
Reasoning tokens are included in completion tokens and are not charged again.
Cost uses the captured pricing file and returned cache hit/miss counts. It is an estimate, not an invoice; unknown usage is not replaced with zero.

## Paired method differences

| Difference | Event-macro V2 known grounding difference | Paired events |
| --- | --- | --- |
| structured_state minus snapshot | +59.38 percentage points | 3/3 |
| answer_history minus snapshot | +5.21 percentage points | 3/3 |
| answer_history minus structured_state | -54.17 percentage points | 3/3 |

Full numerator/denominator metrics, event macro values, branch differences, failed checkpoints, citation reason counts and input hashes are in report.json. All received invalid answers and all unsubmitted checkpoints stay in scoring denominators.

Original collection/score artifacts are preserved. Each derived package was independently replayed and verified before aggregation. No heldout calls or additional model repeats are represented here.
