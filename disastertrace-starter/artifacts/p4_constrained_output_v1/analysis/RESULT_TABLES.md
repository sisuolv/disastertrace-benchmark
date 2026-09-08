# Qwen3-8B constrained-output balanced development results

Automatically generated from independently audited captures.

| Method | Schema | Known Value | Known Grounded | Unknown | All Correct | Action |
| --- | --- | --- | --- | --- | --- | --- |
| answer_history | 180/180 | 553/564 | 529/564 | 156/156 | 145/180 | 178/180 |
| snapshot | 180/180 | 562/564 | 547/564 | 156/156 | 167/180 | 178/180 |
| structured_state | 180/180 | 562/564 | 562/564 | 156/156 | 178/180 | 178/180 |

| Family | Method | Schema | Length | Screen |
| --- | --- | --- | --- | --- |
| U1 | snapshot | 60/60 | 0 | pass |
| U2 | snapshot | 60/60 | 0 | pass |
| U3 | snapshot | 60/60 | 0 | pass |
| U1 | structured_state | 60/60 | 0 | pass |
| U2 | structured_state | 60/60 | 0 | pass |
| U3 | structured_state | 60/60 | 0 | pass |
| U1 | answer_history | 60/60 | 0 | pass |
| U2 | answer_history | 60/60 | 0 | pass |
| U3 | answer_history | 60/60 | 0 | pass |

Development only; three source groups, dependent checkpoints, one repeat.
Free and constrained decoding are separate output tracks.
