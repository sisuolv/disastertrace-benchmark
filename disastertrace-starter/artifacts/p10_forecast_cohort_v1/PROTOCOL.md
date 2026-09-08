# Six additional development storms: native forecast cohort v1

This version expands sources while preserving the P7 forecast task's answer
contract, latest-explicit-covering authority, complete source renderer and scorer.
P7/P8/P9 data, model histories, seeds, results and accepted code remain unchanged.
This protocol is fixed before any model output for the expanded cohort exists.
The P7 development findings were already inspected; this is subsequent development,
not an independent heldout confirmation or preregistration before all prior results.

## Sources and automatic references

Use the complete sealed P10 review_v2: Dorian AL052019, Isaias AL092020,
Henri AL082021, Fiona AL072022, Lee AL132023 and Helene AL092024. Exactly the
first six numbered NHC forecast/advisories per storm were selected before source
acquisition. All 36 original bodies are retained. The initial review admitted
26/36; a versioned parser supports the publisher's POTENTIAL TROP CYCLONE center
header in the remaining 10. Original bytes and failures remain in the new review.
Re-run both independent source parsers and canonical byte/line mapping before
compilation. The model-visible public resolver remains the unchanged third path.

This is a curated six-year development cohort, not a probability sample. All
eight declared heldout storm IDs remain excluded. Source pretraining exposure is
unknown. No manual per-item Gold, model reference generator or LLM judge is used.

Enumerate every storm's union of explicit absolute valid times against all six
delivery steps; include only valid_at strictly later than that step's issue time.
This gives 144 target episodes, 864 candidates, 804 included checkpoints and 60
explicit nonfuture exclusions. No error-dependent, revision-only or length-based
selection is permitted. It contains 138 successive-covering source revisions,
96 changed-wind checkpoints and 42 unchanged-wind checkpoints. Covering versions
can be separated by intervening products on alternating forecast grids.

Issue time is used for the replay cutoff. Historical availability and forecast
initialization time remain unknown; delivery steps are controlled. This is
understanding and updating already published forecasts, not predicting weather.
A newer product that omits the exact horizon does not erase the older explicit
claim under this task contract. That convention is not a statement of NHC
operational forecast validity. There are 326 such no-new-coverage checkpoints.

## Methods, repeats and model comparison

Use snapshot, structured_state and answer_history with identical cumulative
source evidence. Each request is fresh and receives only its own target/method
history. Never correct a model's state with Gold or reuse program histories in
model requests. Invalid and missing prior answers retain the inherited markers.

Use exactly repeat 0 from the inherited forecast_task schedule. This separate
cohort has one sampling repeat per model, explicitly fewer than P7/P9. The 804
queries times three methods give 2412 planned answers per model, 4824 across
Qwen3-8B and DeepSeek-R1-Distill-Qwen-7B. Retain inherited seed derivation on these
new target identities. Each model produces its own later histories; cross-model
matching does not imply identical later inputs or a shared-prefix intervention.

The same published system/user contract applies to both models. Native chat
templates and reasoning parsers differ. DeepSeek's card recommends avoiding a
system prompt; this design instead fixes the common task instruction across
models, as disclosed in P9. The distill model shares Qwen architectural ancestry.

Use the already pinned checkpoints, BF16, TP1, batch4, context32768, max8192
generated tokens including reasoning, temperature0.6, top_p0.95, top_k20 and the
same static shape-only XGrammar as P7/P9. Schema validity is not semantic credit.
The cap is 19,759,104 requested output tokens per model, 39,518,208 combined.
Every live prompt must pass the full output reservation without truncation.

Before GPU dispatch, require a separate tested live execution implementation,
whole-target ownership, explicit worker/model assignments, full program controls,
independent audit, actual no-generation H100 preflight and one-use claims.
At most four H100 allocations may exist at once across all phases. The live
design will assign two replicas per model to run the matched cohort together,
with one shared deadline no later than 2026-09-09T02:05:16.104344+00:00.
If preparation cannot finish in time, retain the completed offline package.
This offline package has no dispatch path or generation authorization.

## Validation, scoring and interpretation

Run all nine inherited public program controls on all 2412 slots. The legal
latest-explicit resolver must achieve full correctness; every deliberately wrong,
invalid or missing answer stays in its denominator. Check every unique diagnostic
prompt with both pinned tokenizers, then reconstruct source admission, dataset,
requests, scores and token counts in a copied CPU environment with original
project/model paths, network and child processes blocked.

For model results report full planned and received counts; shape, exact key,
status, value, unit, current authority, locator and complete correctness; token
usage; elapsed allocation time; every stopped or unattempted slot. Report method
and model differences by storm, transition and target trajectory. Checkpoints
and horizons within a storm are dependent. Report descriptive paired differences
and storm-level sensitivity, without treating 804 queries as 804 independent
weather events. There is one repeat and no sampling-repeat reliability estimate.

The new cohort contains four terminal source rows and ten DISSIPATED-reference
checkpoints, but no terminal-revision checkpoint under the inherited definition.
Do not claim that expanding the storm count solves terminal-transition coverage.
No weather forecast skill, global hazard generalization, leaderboard validity,
causal benefit of memory or architecture-independent comparison follows from this
development matrix. No paid API, training, heldout inference, retries, extra
model probes or selective repair is part of the phase.
