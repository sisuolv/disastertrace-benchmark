# Bounded E execution-order audit

These are the same 96 exposed-development cases with unchanged messages and settings.
Each row is one executed condition; repeated cases are not new weather samples.

| Batch | Condition | Correct | Original correct | Invalid | Status changes | Raw changes | Tokens | Compute ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gpu_e_order_8b_ab_01 | E_only | 65/96 | 65/96 | 0 | 0 | 0 | 75297 | 20001 |
| gpu_e_order_8b_ab_01 | E_fact_table | 51/96 | 51/96 | 0 | 0 | 0 | 41287 | 17734 |
| gpu_e_order_8b_ba_01 | E_fact_table | 51/96 | 51/96 | 0 | 0 | 0 | 41287 | 20295 |
| gpu_e_order_8b_ba_01 | E_only | 65/96 | 65/96 | 0 | 0 | 0 | 75297 | 20445 |
| gpu_e_order_32b_ab_01 | E_only | 81/96 | 81/96 | 0 | 0 | 0 | 74894 | 36949 |
| gpu_e_order_32b_ab_01 | E_fact_table | 88/96 | 88/96 | 0 | 0 | 0 | 40879 | 31917 |
| gpu_e_order_32b_ba_01 | E_fact_table | 88/96 | 88/96 | 0 | 0 | 0 | 40879 | 31986 |
| gpu_e_order_32b_ba_01 | E_only | 81/96 | 81/96 | 0 | 0 | 0 | 74894 | 35279 |

Unverified batches: none

REPORT.json records complete confusion matrices and paired changes; CASES.json retains raw answers for every paired case.
Case order is checked against trace order. Condition order is bound by the frozen sequential worker, with no synchronized cross-task timestamps.
This analysis makes no F, isolated causal-effect, independent-weather or multimodal improvement claim.
