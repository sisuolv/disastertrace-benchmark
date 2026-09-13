# Portfolio E coverage and a jointly feasible source-only reference

This compares full registered portfolios with verified legal query paths, not a sum of incompatible per-target optima.
The reference omits forecasting computation and F utility; its gap is diagnostic headroom, not a failure penalty.

| Source requests / session | Individual reachability sum | Joint feasible E optimum | All opportunities |
| --- | ---: | ---: | ---: |
| 72 | 5646 | 2052.0 | 5832 |
| 144 | 5646 | 3984.0 | 5832 |
| 216 | 5646 | 5646.0 | 5832 |

| Method | Certified E | Source-only joint reference | Portfolio headroom | F gain over R base |
| --- | ---: | ---: | ---: | ---: |
| model/qwen3_8b/round_robin/base_bound_override | 1989 | 3984.0 | 1995.0 | -0.000308735 |
| model/qwen3_8b/risk/base_bound_override | 1986 | 3984.0 | 1998.0 | +0.000000000 |
| model/qwen3_8b/batch_complete/base_bound_override | 3771 | 3984.0 | 213.0 | -0.000650909 |
| model/qwen3_8b/llm/base_bound_override | 126 | 3984.0 | 3858.0 | +0.000000000 |
| model/qwen3_8b/round_robin/persistent_override | 1989 | 3984.0 | 1995.0 | -0.000154514 |
| model/qwen3_8b/risk/persistent_override | 1986 | 3984.0 | 1998.0 | +0.000000000 |
| model/qwen3_8b/batch_complete/persistent_override | 3771 | 3984.0 | 213.0 | +0.000000000 |
| model/qwen3_8b/llm/persistent_override | 126 | 3984.0 | 3858.0 | +0.000000000 |
| program/FOLLOW/base_bound_override | 0 | 3984.0 | 3984.0 | +0.000000000 |
| program/FOLLOW/persistent_override | 0 | 3984.0 | 3984.0 | +0.000000000 |
| program/round_robin/base_bound_override | 1989 | 3984.0 | 1995.0 | +0.000104189 |
| program/round_robin/persistent_override | 1989 | 3984.0 | 1995.0 | -0.000025026 |
| program/risk/base_bound_override | 1986 | 3984.0 | 1998.0 | -0.000004868 |
| program/risk/persistent_override | 1986 | 3984.0 | 1998.0 | -0.000113072 |
| program/coverage/base_bound_override | 1989 | 3984.0 | 1995.0 | +0.000104189 |
| program/coverage/persistent_override | 1989 | 3984.0 | 1995.0 | -0.000025026 |
| program/batch_complete/base_bound_override | 3771 | 3984.0 | 213.0 | +0.000015966 |
| program/batch_complete/persistent_override | 3771 | 3984.0 | 213.0 | -0.000095865 |
| program/all_read/base_bound_override | 5646 | 5646.0 | 0.0 | +0.000277918 |
| program/all_read/persistent_override | 5646 | 5646.0 | 0.0 | +0.000154119 |
| program/neighbor_persistence/base_bound_override | 5646 | 5646.0 | 0.0 | -0.034569484 |
| program/neighbor_persistence/persistent_override | 5646 | 5646.0 | 0.0 | -0.035420236 |
| program/capacity_revise_defer/base_bound_override | 1986 | 3984.0 | 1998.0 | -0.000033344 |
| program/capacity_revise_defer/persistent_override | 1986 | 3984.0 | 1998.0 | +0.000069400 |

Certified E describes the legally disclosed product facts, not the model's correctness at reading them.
E and F denominators differ when future outcomes are missing; all counts and state categories remain in REPORT.json.
Nothing in this comparison requires a rational F policy to maximize E coverage, or imputes F=0.5 when E is undetermined.
