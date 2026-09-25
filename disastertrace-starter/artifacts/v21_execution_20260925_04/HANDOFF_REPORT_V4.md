# v21 execution 20260925_04 handoff

## Starting and final code state

The run started and ended at HEAD `9dffe43e81c0a2b47f79ad08139e9d1f0d243f4e` on `codex/v18-repaired-release-20260923`. The worktree remained dirty by design: 11 pre-existing tracked modifications and many historical untracked trees were preserved. No reset, commit, push, or cleanup was performed. The new source and evaluator scripts are explicitly hashed in `SNAPSHOT_MANIFEST_V4.json`.

## Completed engineering work

- Rebuilt the bounded TAF roster as `G1_DEV_EPISODES_V3.json`: 24 episodes and 72 checkpoints, with metre visibility and preserved TEMPO/PROB semantics.
- Added `run_v21_real_dev_source_bridge.py` and ran 72 bounded Natural selector traces over real TAF projections. All traces terminated; outcomes never entered actor state.
- Added `bind_v21_dev_asos_outcomes.py`. It read only KDEN/KJFK/KORD/KSFO, January/March 2025 ASOS files, converted statute-mile `vsby` to metres, and bound 24/24 target windows.
- Added `run_v21_real_dev_deterministic_score.py`. The four deterministic arms share a single forecast map and checkpoint denominator; it records no provider/model calls.
- Added unit coverage for the ASOS unit parser and normalized-TAF probability map. v17-v21 regression now passes 226 tests; compileall, Ruff critical checks, diff check, and secret scan pass.

## GPU jobs and findings

Six tide jobs completed. The first three (RTX 5090 `om-9ztw5ypm`, RTX 5090 `om-qolmuk6c`, H100 share `om-elhqpnle`) ran the 144-cell shared-evidence/reliability/delay/coverage surface with 1,000,000 targets per cell. Across 432 rows, active minus fixed mean loss was `-0.026375`; active minus best non-active was `+0.006161`, with 31 wins. That surface is synthetic and its repeated-retrieval arm has unequal cost.

The follow-up three (RTX 5090 `om-2i6w8d3y`, RTX 5090 `om-hkd7uz7t`, H100 share `om-bdekxc0e`) ran the 384-cell cost-matched adaptive surface with 500,000 targets per cell. `source_rr`, `source_hash`, and `active` all used two queries, the same F, and the same denominator. Across 1,152 rows, active minus best non-active was `-0.011311`, with 816 wins; active minus fixed was `-0.043942`. This supports testing content-dependent follow-up selection under an equal-cost contract, but remains synthetic mechanism evidence.

## Development outcome result

The evaluator-only ASOS binding has 22 `y=0` and 2 `y=1` labels. The deterministic source arms all have mean Brier `0.1104167`; active, earliest, and hash are exactly tied on all 72 checkpoint cells. The active-minus-fixed difference is `-0.1395833`, but this is driven by the fixed 0.5 prior and the highly imbalanced small sample. It is not evidence for an active-policy advantage or novelty.

## Resolved and remaining issues

Resolved: bounded real source parsing now has explicit units and conditional semantics; source-to-Natural bridge is executable; ASOS outcome contract is explicit and fully bound on the allowed dev set; all six tide jobs are auditable and completed.

Blocked or inconclusive: no provider/model run was launched because no credential was available in the environment; no holdout/quarantine/protected data was read; active has no independent advantage in the real deterministic diagnostic; the shared-delay synthetic comparator is not cost matched; the worktree is not a clean release.

## Current research judgment

The project has a credible engineering/protocol base and a falsifiable conditional hypothesis: content-dependent follow-up selection may help when evidence has finite cost, delayed availability, and calibrated reliability. The cost-matched synthetic gate supports that mechanism, while the real deterministic dev diagnostic shows no independent selector gain. The next experiment must preserve equal retrieval/model-call cost, include strong non-adaptive and latest-source controls, pre-register calibration and harm guards, and then run a new provider-backed development pilot with a complete denominator. Only after that should any broader weather or novelty claim be considered.

## Reproduction entry points

- `G1_DEV_EPISODES_V3.json`
- `REAL_DEV_SOURCE_BRIDGE.json`
- `REAL_DEV_ASOS_OUTCOMES.json`
- `REAL_DEV_DETERMINISTIC_SCORE.json`
- `SHARED_DELAY_AGGREGATE.json`
- `COST_MATCHED_ADAPTIVE_AGGREGATE.json`
- `PROTOCOL_GATE_V4.json`
- `TEST_STATUS_V4.json`
- `GPU_JOB_STATUS_V4.json`
- `SNAPSHOT_MANIFEST_V4.json`

The main local command is:

```bash
cd /mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter
.venv/bin/python -m pytest tests/test_v17*.py tests/test_v18*.py tests/test_v19*.py tests/test_v21*.py -q
```
