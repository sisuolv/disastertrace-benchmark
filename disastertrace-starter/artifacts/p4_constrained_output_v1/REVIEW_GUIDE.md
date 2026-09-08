# P4 review guide

## Read in this order

1. `../../README_P4_CONSTRAINED_OUTPUT_V1.md` and `FINDINGS.md` for the measured
   outcome, scope and scientific interpretation.
2. `../../docs/P4_CONSTRAINED_OUTPUT_V1.md` for the frozen protocol; `NEXT_PHASE_PLAN.md`
   for the next bounded implementation and research tasks.
3. `execution_live/execution.json`, `constraint.json` inside that execution,
   `frozen_acceptance.json`, and `gpu_preflight.json` for bound configuration.
4. `model_report/report.json`, `model_report/audit.json`, `analysis/analysis.json`
   and `track_comparison/comparison.json` for deterministic results and comparison.
5. `execution_live/implementation_source/` for the exact implementation used in
   collection and audit. Current root files are not a substitute for this snapshot.
6. `validation/`, `runtime/`, `grammar_model/` and `stress_context/` for execution
   observations, token-mask verification and the next difficulty calibration.

## Questions worth checking

- Does the schema constrain only output shape, rather than source membership,
  correct numerical values, unknown consistency or the scored action relation?
- Are vLLM's real reasoning gate, engine options and exact schema property order
  bound? The grammar recognizes final EOS 151645; the model also has EOS 151643,
  which remains possible during unconstrained reasoning. This is a decoder detail.
- Does the original parser still reject invalid ranges/precision/identifiers,
  while semantically wrong but contract-valid decisions remain in their own history?
- Are all 540 opportunities retained, including missing, invalid and length outputs?
  Do all three validity layers agree with the original schema_success count?
- Do comparison checks cover identical episodes, Gold, source/scorer bytes, public
  evidence and base sampling? Histories can differ as outputs differ across tracks.
- Does the report remain reconstructible without a GPU, weights, credentials or
  network, and is diagnostic/model provenance kept separate?
- Are level-16 context failures and zero-effect chain controls disclosed, without
  presenting 216 generated variants as 216 independent storms?

## What this package establishes

Code/content binding and deterministic reconstruction are checked automatically.
The records are local execution evidence, not hardware attestation. Dependency
versions and selected backend source hashes are frozen; the archive does not contain
a complete GPU runtime or model weights. Third-party source copies have their
licenses under `third_party_licenses/`. The initial official GitHub source download
times out; the preserved installed backend sources and actual tests are the local
capability evidence, with the tagged URLs retained for external verification.

The benchmark measures controlled weather-record updates, scope selection, citation
refresh and a research action rule. It does not establish weather forecasting
accuracy, broad coverage of extreme-weather hazards, or causal internal-memory
superiority. The same three development source groups and one sample per slot remain.
No human/LLM judge assigns item labels or scores. Optional code/design review is
separate from the benchmark's automatic scoring pipeline.

## Preserved unsuccessful checks

`validation/lint_initial/` records formatting/import issues before cleanup.
`validation/tests_initial/` retains the incorrect all-unknown prior-state test
assumption and the initial pytest configuration warning; the corrected 44-test
suite passes with the actual last-valid-state rule. `validation/official_sources/`
retains the network timeout. The first context-test fixture duplicated delivery
IDs and was correctly rejected before reaching the length guard; the revised
fixture uses distinct replay delivery IDs. None of these changes alter frozen P3
files or repair model output. Exact commands and observed exits are in the logs.
