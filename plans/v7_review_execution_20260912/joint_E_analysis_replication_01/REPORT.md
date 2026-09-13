# Portfolio E coverage and a jointly feasible source-only reference

This compares full registered portfolios with verified legal query paths, not a sum of incompatible per-target optima.
The reference omits forecasting computation and F utility; its gap is diagnostic headroom, not a failure penalty.

| Source requests / session | Individual reachability sum | Joint feasible E optimum | All opportunities |
| --- | ---: | ---: | ---: |
| 72 | 5718 | 1974.0 | 5832 |
| 144 | 5718 | 3915.0 | 5832 |
| 216 | 5718 | 5718.0 | 5832 |

| Method | Certified E | Source-only joint reference | Portfolio headroom | F gain over R base |
| --- | ---: | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 1953 | 3915.0 | 1962.0 | +0.000000000 |
| model/qwen3_8b/risk/base_bound_override | 1938 | 3915.0 | 1977.0 | +0.000000000 |
| model/qwen3_8b/batch_complete/base_bound_override | 3804 | 3915.0 | 111.0 | +0.000000000 |
| model/qwen3_8b/llm/base_bound_override | 48 | 3915.0 | 3867.0 | -0.000172175 |
| model/qwen3_8b/round_robin/persistent_override | 1953 | 3915.0 | 1962.0 | +0.000000000 |
| model/qwen3_8b/risk/persistent_override | 1938 | 3915.0 | 1977.0 | +0.000000000 |
| model/qwen3_8b/batch_complete/persistent_override | 3804 | 3915.0 | 111.0 | +0.000000000 |
| model/qwen3_8b/llm/persistent_override | 48 | 3915.0 | 3867.0 | +0.000000000 |
| program/FOLLOW/base_bound_override | 0 | 3915.0 | 3915.0 | +0.000000000 |
| program/FOLLOW/persistent_override | 0 | 3915.0 | 3915.0 | +0.000000000 |
| program/round_robin/base_bound_override | 1953 | 3915.0 | 1962.0 | -0.000000279 |
| program/round_robin/persistent_override | 1953 | 3915.0 | 1962.0 | -0.000000911 |
| program/risk/base_bound_override | 1938 | 3915.0 | 1977.0 | -0.000000180 |
| program/risk/persistent_override | 1938 | 3915.0 | 1977.0 | -0.000000808 |
| program/coverage/base_bound_override | 1953 | 3915.0 | 1962.0 | -0.000000279 |
| program/coverage/persistent_override | 1953 | 3915.0 | 1962.0 | -0.000000911 |
| program/batch_complete/base_bound_override | 3804 | 3915.0 | 111.0 | -0.000000812 |
| program/batch_complete/persistent_override | 3804 | 3915.0 | 111.0 | -0.000001408 |
| program/all_read/base_bound_override | 5718 | 5718.0 | 0.0 | -0.000001224 |
| program/all_read/persistent_override | 5718 | 5718.0 | 0.0 | -0.000001876 |
| program/neighbor_persistence/base_bound_override | 5718 | 5718.0 | 0.0 | -0.013163629 |
| program/neighbor_persistence/persistent_override | 5718 | 5718.0 | 0.0 | -0.013167085 |
| program/capacity_revise_defer/base_bound_override | 1938 | 3915.0 | 1977.0 | +0.000000000 |
| program/capacity_revise_defer/persistent_override | 1938 | 3915.0 | 1977.0 | +0.000000000 |

Certified E describes the legally disclosed product facts, not the model's correctness at reading them.
E and F denominators differ when future outcomes are missing; all counts and state categories remain in REPORT.json.
Nothing in this comparison requires a rational F policy to maximize E coverage, or imputes F=0.5 when E is undetermined.
