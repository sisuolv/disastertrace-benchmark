# Review the P5 ACP execution

## Entry points

Start with `../../README_P5_ACP_V1.md`, the actual result tables under `analysis/`,
and the factor-level paired tables in `stress_comparison/comparison.json`.
`FINDINGS.md` and `OFFLINE_ACCEPTANCE.json` describe the earlier offline phase;
their program answers are distinct from the subsequent actual model outputs.

Read `ACP_EXECUTION_PLAN.md`, `LIVE_ACCEPTANCE.json` and each live execution before
checking raw runs. The exact 64-file implementation snapshot is frozen before
dispatch. The independently bound launcher lives outside that snapshot. No frozen
P4 or P5 task/scorer/runtime module changes in this ACP extension.

## Questions the artifacts can answer

- Do all 36 episodes and 540 opportunities remain in each factor, including six
  zero-effect revision-chain controls? Do values, statuses, current citations,
  research actions and every metric/checkpoint denominator equal the matched base?
- Does the real ACP worker use the pinned package/model/backend inventory with
  the original single-GPU settings and structure-only grammar? Full H100 versus
  P4 MIG and new factor slot seeds are disclosed as comparison limitations.
- Does every live answer originate in its own factor run? Does a wrong but valid
  answer propagate through that method's history, while invalid answers retain
  the last valid carrier? Are all failures retained without selective retry?
- Are job IDs, platform states, worker claims and observed subprocess exits
  consistent with the raw captures and report audit IDs? The preflight calls no
  model generation, and submission acceptance does not establish completion.
- Do token-mask replay and a relocated CPU review independently reproduce the
  reports and descriptive paired comparison? CPU review blocks original data,
  weights and network and contains no Torch/vLLM.

The aggregate metric uses all planned checkpoints. Supplementary breakdowns by
source, family, case, checkpoint and effective control status do not replace it.
Both directions of paired change remain visible, even when their net difference
is small. Source groups, factor variants and successive checkpoints are dependent.

## Preserved failures and implementation history

The first new inherited-verification wrapper refers to `local_model_calls` in a
return object that actually uses `model_calls`; its log and exact source are kept
in `validation/inherited_acceptance_check/`. The corrected wrapper completes all
three independent audits. The collector, original audit and model answers are
unchanged. The completed revised source is also preserved separately from later
formatting. Initial postprocessing lint failure and its correction remain recorded.

The review package establishes deterministic reconstruction and content bindings,
not hardware attestation or broad extreme-weather competence. It evaluates
controlled weather-record reasoning, not forecasting accuracy. Optional design
or code review is separate from automatic per-item Gold and scoring.
