# v21 execution 20260925_04 claim boundary

| Claim | Evidence | Status | Limit |
|---|---|---|---|
| The repaired TAF builder preserves metre visibility and conditional semantics on the bounded readset | `G1_DEV_EPISODES_V3.json`, builder tests | PASS_SCOPED | Four stations, January/March development months only |
| Registered public selectors can execute against bounded real TAF content without exposing outcomes | `REAL_DEV_SOURCE_BRIDGE.json` | PASS_SCOPED | Deterministic adapter; no provider/model call |
| All 24 bounded dev targets have a declared ASOS outcome | `REAL_DEV_ASOS_OUTCOMES.json` | PASS_SCOPED | First valid `vsby` observation in one-hour target window; evaluator-only |
| A fixed deterministic TAF-to-probability map improves over a 0.5 fixed prior | `REAL_DEV_DETERMINISTIC_SCORE.json` | DIAGNOSTIC | Two positive labels out of 24; baseline and map are preregistered but not a model result |
| The active public-age selector has an independent real-dev advantage | `REAL_DEV_DETERMINISTIC_SCORE.json` | INCONCLUSIVE | It ties earliest/hash controls on all 72 cells; no provider/model forecast |
| Shared-delay active mechanism replicates across 5090/H100 | `SHARED_DELAY_AGGREGATE.json`, `GPU_JOB_STATUS_V4.json` | PASS_SYNTHETIC_DIAGNOSTIC | Synthetic process; the repeated-retrieval arm is stronger under its unequal cost |
| Content-dependent active follow-up beats cost-matched fixed follow-ups in the declared process | `COST_MATCHED_ADAPTIVE_AGGREGATE.json`, `cost_matched_gpu/*/result.json` | CONDITIONAL_PASS_SYNTHETIC | 816/1152 cells; constructed signal process, not weather or novelty evidence |
| A provider-backed empirical forecast claim is established | No new provider artifact | BLOCKED | No credential in environment and no API run was started |
| The repository is a clean GitHub release | `SNAPSHOT_MANIFEST_V4.json`, git status | BLOCKED | Existing dirty tracked changes and large untracked historical trees remain |
| Research novelty/value is established | Combined artifacts | INCONCLUSIVE | Current evidence supports a conditional, cost-matched selection hypothesis only |
