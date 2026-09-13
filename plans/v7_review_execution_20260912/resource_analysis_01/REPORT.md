# Resource-use and full-calendar E diagnostics

All values reconstruct from traces already bound to completed calendar reports.
Source requests count archive slots; real bulk transport is a separate audit.

| Calendar | Arm | Calls | Selector calls | Token quota used | Compute quota used | Accepted overrides | E correct / forecast calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| calendar_analysis_bay_02 | model/qwen3_8b/round_robin/base_bound_override | 1296 | 0 | 17.70% | 1.72% | 2 | 155/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/risk/base_bound_override | 1296 | 0 | 17.53% | 1.75% | 0 | 154/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/batch_complete/base_bound_override | 1296 | 0 | 16.84% | 1.69% | 3 | 498/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/llm/base_bound_override | 1296 | 648 | 33.99% | 1.03% | 0 | 320/648 |
| calendar_analysis_bay_02 | model/qwen3_8b/round_robin/persistent_override | 1296 | 0 | 17.69% | 1.75% | 1 | 124/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/risk/persistent_override | 1296 | 0 | 17.51% | 1.75% | 0 | 112/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/batch_complete/persistent_override | 1296 | 0 | 16.83% | 1.91% | 0 | 486/1296 |
| calendar_analysis_bay_02 | model/qwen3_8b/llm/persistent_override | 1296 | 648 | 33.94% | 0.99% | 0 | 301/648 |
| calendar_analysis_front_02 | model/qwen3_8b/round_robin/base_bound_override | 1296 | 0 | 18.00% | 1.77% | 1 | 93/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/risk/base_bound_override | 1296 | 0 | 18.04% | 1.74% | 1 | 66/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/batch_complete/base_bound_override | 1296 | 0 | 17.10% | 1.69% | 1 | 457/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/llm/base_bound_override | 1296 | 648 | 34.47% | 0.97% | 0 | 317/648 |
| calendar_analysis_front_02 | model/qwen3_8b/round_robin/persistent_override | 1296 | 0 | 17.98% | 1.76% | 0 | 56/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/risk/persistent_override | 1296 | 0 | 18.03% | 1.81% | 0 | 35/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/batch_complete/persistent_override | 1296 | 0 | 17.08% | 1.78% | 0 | 450/1296 |
| calendar_analysis_front_02 | model/qwen3_8b/llm/persistent_override | 1296 | 648 | 34.42% | 0.98% | 0 | 290/648 |

Session minima/maxima, remaining reservation slack, complete E confusion and response errors are in REPORT.json and SESSIONS.json.
E denominators differ by selected target and exposed evidence; these rows do not rank selectors on a common E test set.
The balanced 96-case E diagnostic is a different diagnostic distribution and cannot replace full-calendar results.
A low Brier gain with no accepted overrides does not establish whether a better selector or forecaster would improve this task.
