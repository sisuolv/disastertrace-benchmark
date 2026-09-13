# Portfolio E coverage and a jointly feasible source-only reference

This compares full registered portfolios with verified legal query paths, not a sum of incompatible per-target optima.
The reference omits forecasting computation and F utility; its gap is diagnostic headroom, not a failure penalty.

| Source requests / session | Individual reachability sum | Joint feasible E optimum | All opportunities |
| --- | ---: | ---: | ---: |
| 72 | 5814 | 1974.0 | 5832 |
| 144 | 5814 | 3918.0 | 5832 |
| 216 | 5814 | 5814.0 | 5832 |

| Method | Certified E | Source-only joint reference | Portfolio headroom | F gain over R base |
| --- | ---: | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000171074 |
| model/qwen3_8b/risk/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000171074 |
| model/qwen3_8b/batch_complete/base_bound_override | 3876 | 3918.0 | 42.0 | -0.000171186 |
| model/qwen3_8b/llm/base_bound_override | 0 | 3918.0 | 3918.0 | +0.000000000 |
| model/qwen3_8b/round_robin/persistent_override | 1959 | 3918.0 | 1959.0 | +0.000000000 |
| model/qwen3_8b/risk/persistent_override | 1959 | 3918.0 | 1959.0 | +0.000000000 |
| model/qwen3_8b/batch_complete/persistent_override | 3876 | 3918.0 | 42.0 | +0.000000000 |
| model/qwen3_8b/llm/persistent_override | 0 | 3918.0 | 3918.0 | +0.000000000 |
| program/FOLLOW/base_bound_override | 0 | 3918.0 | 3918.0 | +0.000000000 |
| program/FOLLOW/persistent_override | 0 | 3918.0 | 3918.0 | +0.000000000 |
| program/round_robin/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000125148 |
| program/round_robin/persistent_override | 1959 | 3918.0 | 1959.0 | -0.000116201 |
| program/risk/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000107929 |
| program/risk/persistent_override | 1959 | 3918.0 | 1959.0 | -0.000099184 |
| program/coverage/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000125148 |
| program/coverage/persistent_override | 1959 | 3918.0 | 1959.0 | -0.000116201 |
| program/batch_complete/base_bound_override | 3876 | 3918.0 | 42.0 | -0.000159127 |
| program/batch_complete/persistent_override | 3876 | 3918.0 | 42.0 | -0.000149416 |
| program/all_read/base_bound_override | 5814 | 5814.0 | 0.0 | -0.000207031 |
| program/all_read/persistent_override | 5814 | 5814.0 | 0.0 | -0.000196985 |
| program/neighbor_persistence/base_bound_override | 5814 | 5814.0 | 0.0 | -0.013835100 |
| program/neighbor_persistence/persistent_override | 5814 | 5814.0 | 0.0 | -0.013837930 |
| program/capacity_revise_defer/base_bound_override | 1959 | 3918.0 | 1959.0 | -0.000075920 |
| program/capacity_revise_defer/persistent_override | 1959 | 3918.0 | 1959.0 | -0.000116610 |

Certified E describes the legally disclosed product facts, not the model's correctness at reading them.
E and F denominators differ when future outcomes are missing; all counts and state categories remain in REPORT.json.
Nothing in this comparison requires a rational F policy to maximize E coverage, or imputes F=0.5 when E is undetermined.
