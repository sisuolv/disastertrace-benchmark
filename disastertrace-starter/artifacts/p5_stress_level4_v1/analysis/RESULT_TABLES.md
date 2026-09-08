# P5 actual Qwen3-8B level-4 stress results

Fixed denominators; independent deterministic audit; no answer repair.

| Factor | Method | Contract | Known Value | Known Grounded | Unknown | All Correct | Action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revision_chain | answer_history | 180/180 | 543/564 | 515/564 | 156/156 | 135/180 | 178/180 |
| revision_chain | snapshot | 180/180 | 563/564 | 525/564 | 156/156 | 150/180 | 180/180 |
| revision_chain | structured_state | 180/180 | 559/564 | 546/564 | 156/156 | 164/180 | 175/180 |
| irrelevant_scope | answer_history | 180/180 | 546/564 | 511/564 | 156/156 | 135/180 | 178/180 |
| irrelevant_scope | snapshot | 180/180 | 558/564 | 522/564 | 156/156 | 155/180 | 177/180 |
| irrelevant_scope | structured_state | 180/180 | 554/564 | 525/564 | 156/156 | 154/180 | 174/180 |
| late_stale_replay | answer_history | 180/180 | 540/564 | 513/564 | 156/156 | 132/180 | 174/180 |
| late_stale_replay | snapshot | 180/180 | 562/564 | 543/564 | 156/156 | 163/180 | 178/180 |
| late_stale_replay | structured_state | 180/180 | 561/564 | 556/564 | 156/156 | 172/180 | 177/180 |

One repeat, three dependent source groups, full H100 workers. Timings are descriptive shared-batch measurements, not per-request latency or a hardware-controlled P4 comparison.
