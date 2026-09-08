# Qwen3-8B balanced development results

Automatically generated from independently audited captures.

| Method | Schema | Known Value | Known Grounded | Unknown | All Correct | Action |
| --- | --- | --- | --- | --- | --- | --- |
| answer_history | 52/180 | 62/564 | 60/564 | 146/156 | 50/180 | 52/180 |
| snapshot | 80/180 | 171/564 | 168/564 | 147/156 | 75/180 | 79/180 |
| structured_state | 68/180 | 125/564 | 125/564 | 147/156 | 68/180 | 68/180 |

| Family | Method | Schema | Length | Screen |
| --- | --- | --- | --- | --- |
| U1 | snapshot | 27/60 | 0 | fail |
| U2 | snapshot | 25/60 | 0 | fail |
| U3 | snapshot | 28/60 | 0 | fail |
| U1 | structured_state | 22/60 | 0 | fail |
| U2 | structured_state | 24/60 | 0 | fail |
| U3 | structured_state | 22/60 | 0 | fail |
| U1 | answer_history | 14/60 | 0 | fail |
| U2 | answer_history | 20/60 | 0 | fail |
| U3 | answer_history | 18/60 | 0 | fail |

Development only; three source groups, dependent checkpoints, one repeat.
Historical 270-version scores are not ranked with this 540-version result.
