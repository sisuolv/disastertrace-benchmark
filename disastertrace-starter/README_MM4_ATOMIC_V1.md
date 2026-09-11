# MM-4: atomic multimodal diagnostics

Forty actual Qwen3-VL-8B-Instruct responses are collected and reviewed. All are
structurally valid, query complete and EOS; strict success is spatial 8/9, watch
3/9, privileged logic 9/12 and metadata selection 7/10. These distinct tasks do
not form an overall capability score. Data still comes from one development event.

The spatial model calls all six map-present points inside, missing the sole outside
point. Watch values also match a simple presence-only pattern. Read the class and
missing-evidence breakdown before interpreting the headline rates.

- [Detailed Chinese results](artifacts/multimodal_v1/mm4_atomic_20260909/RESULTS_CN.md)
- [Next execution plan](artifacts/multimodal_v1/mm4_atomic_20260909/NEXT_STEP_CN.md)
- [ChatGPT Pro review guide](artifacts/multimodal_v1/mm4_atomic_20260909/REVIEW_GUIDE_CN.md)
- [Review ZIP](artifacts/multimodal_v1/mm4_atomic_20260909/MM4_REVIEW.zip)
- [Acceptance](artifacts/multimodal_v1/mm4_atomic_20260909/COMPLETED.json)
- [Predeclared protocol](artifacts/multimodal_v1/mm4_atomic_20260909/EXECUTION_PLAN_CN.md)
- [Machine-readable report](artifacts/multimodal_v1/mm4_atomic_20260909/REPORT.json)
- [Implementation record](artifacts/multimodal_v1/mm4_atomic_20260909/IMPLEMENTATION_STATUS.md)

Four one-H100 jobs all succeed and release. A retained STARTING-replica accounting
failure separates the first shard from the three-shard continuation; actual peak
concurrency is three. No worker or request is retried. All 40 processor/token
captures reconstruct, and relocated CPU review reconstructs requests, automatic
references, public controls and raw-response scoring. The original MM-3 V1/V2
results and 1,986 prior evidence bindings remain unchanged. No paid API or heldout
inference runs. The 40/40 revision gate fails; new scopes must preserve that result.
