# Development diagnostic matrix

This is zero-API verification of diagnostic programs, not an LLM evaluation.
Three existing development storms, six controlled branches and 30 checkpoints are replayed per configuration.
All three methods receive cumulative delivered evidence. No heldout episode is evaluated.

| Method | Diagnostic backend | Known grounded | Overall grounded | Semantic changes | Stable semantics | Source refresh |
| --- | --- | --- | --- | --- | --- | --- |
| structured_state | rule | 96/96 | 150/150 | 64/64 | 56/56 | 8/8 |
| structured_state | last-arrival | 72/96 | 126/150 | 55/64 | 47/56 | 5/8 |
| structured_state | no-update | 0/96 | 54/150 | 0/64 | 24/56 | 0/8 |
| snapshot | rule | 96/96 | 150/150 | 64/64 | 56/56 | 8/8 |
| snapshot | last-arrival | 72/96 | 126/150 | 55/64 | 47/56 | 5/8 |
| snapshot | no-update | 0/96 | 54/150 | 0/64 | 24/56 | 0/8 |
| answer_history | rule | 96/96 | 150/150 | 64/64 | 56/56 | 8/8 |
| answer_history | last-arrival | 72/96 | 126/150 | 55/64 | 47/56 | 5/8 |
| answer_history | no-update | 0/96 | 54/150 | 0/64 | 24/56 | 0/8 |

All nine configurations have identical fixed Gold denominators, including unsuccessful/correctness-independent opportunities.
The rule parser supports all 96 known slots. Last-arrival gets 72/96 known slots grounded and exposes 24 stale citations.
No-update gets 0/96 known slots grounded; its 54 correctly unknown slots do not conceal that failure in known-only metrics.
These controls test scorer behavior and method wiring. They do not establish differences or equivalence between LLM methods.

Saved files include exact traces, v1/v2 scores, selected source episodes, the evidence index, source snapshots and hashes.
The script refuses an existing output directory. To reproduce, run the same command with a fresh output path; timestamps and elapsed time will differ.
