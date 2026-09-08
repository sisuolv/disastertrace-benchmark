# CPU reproduction and review entry

The sole model launch and all program-diagnostic claims are consumed. The commands
here only verify saved evidence. They do not require an API key, model weights,
or a GPU. Do not execute launch-model, collect/model, old phase launchers, or the
consumed finalize_after_worker.py or finalize_review_v2.py as a reproduction step.

## Core model report

The supplied CPU review environment uses Python3.10.12, transformers4.55.2,
tokenizers0.21.4 and Jinja2 3.1.6, with no Torch or vLLM. The frozen package carries
its own tokenizer/configuration, source, parent dataset, schedule and backend code.

```bash
DT_PROJECT=/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter
DT_EXEC="$DT_PROJECT/artifacts/p6_live_v1/execution_live_02"
DT_CPU=/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$DT_PROJECT/artifacts/p6_live_v1/token_text_review_v2/review_source/src" \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
"$DT_CPU" -m disastertrace.repeat_live_review.cli verify-report \
  --execution "$DT_EXEC" \
  --run "$DT_PROJECT/work/p6-live-v1/model" \
  --output "$DT_PROJECT/artifacts/p6_live_v1/reports/model_review_v2"
```

Verification rebuilds the schedule, public requests, paired seeds, actual prompt
tokens, accepted carriers, parsed answers and fixed-denominator statistics. It
starts from raw batches and checks saved parsed records instead of trusting them.
The model runtime's CachedQwen2TokenizerFast wrapper is checked against the frozen
vLLM profile; CPU reconstruction uses the original Qwen2TokenizerFast. Actual
prompts and tokens must still match exactly.

Report files: audit.json, trace.json and scores.json. The score report includes
per-repeat/method/condition cells,36 format screens, source-repeat tables, paired
outcomes in both directions, exposure slices, episode pass^2 and trajectory errors.

## Actual relocation proof

The CPU continuation creates work/p6-live-portable-review-v2 with execution, run,
report and separately frozen reviewer-source copies. Its verification runs with the copied source while an audit
hook blocks reads under the original project/model directory and blocks socket
connections. It also rejects a review environment containing Torch or vLLM.
CPU_RELOCATION.json records the actual outcome and imported source path.

The original run/registry/model paths inside frozen JSON are provenance strings.
They are not remapped or read during CPU reconstruction. Editing them would alter
the execution identity. The tokenizer is loaded from the copied model_config.

## Token-mask replay

grammar_model/report.json records a separate CPU replay of every received final
token and EOS against XGrammar0.1.23. This requires the existing Qwen Python
environment because it contains XGrammar and Torch; CUDA_VISIBLE_DEVICES is empty
and no model is loaded or sampled. A missing reasoning delimiter or truncated
answer remains visible independently of mask validity. Do not interpret a mask
check as proof that the answer's values or citations are correct.

The exact command, output and exit code are under
finalization_002/03_token_mask_replay. Environment/code hashes are bound in the
live execution and actual preflight observation.

## NHC source review

The parser logic uses Python's standard library; importing the project package
also requires its preserved models module and existing Pydantic dependency.
acquisition_source retains the original minimal parser snapshot. source_execution_v2
adds the complete package-import closure after an initial pre-network import failure.
Its parser files exactly match the original frozen scope. Its review_v1
folder stores both parser outputs, raw/normalized views, provenance and revision
pairs. No network call occurs during review verification.

```bash
DT_SOURCE="$DT_PROJECT/artifacts/nhc_forecast_source_v1"

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$DT_SOURCE/source_execution_v2/src" \
"$DT_CPU" -m disastertrace.forecast_source.pipeline verify \
  --bundle "$DT_SOURCE" \
  --output "$DT_SOURCE/review_v1"
```

Inspect all12 planned body records, including HTTP/parser failures and terminal
rows with null numerical fields. Same-valid-time revision pairs are formed only
after independent parser agreement. The raw forecast exports and derived columns
are source-review artifacts; there is no source-track LLM score or new model call.

## Historical and completed acceptance

After phase completion, verify the new evidence inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$DT_PROJECT/src" \
"$DT_PROJECT/.venv/bin/python" \
  "$DT_PROJECT/artifacts/p6_live_v1/accept_completed.py" --verify
```

The old artifacts/p6_offline_v1/accept_offline.py --verify command remains valid.
Its status and zero model-generation count describe that unchanged historical
offline milestone, not the current live phase. Its5,703 files include historical
root navigation/status documents, which therefore remain unchanged.
CURRENT_PHASE.md is a new mutable navigation pointer outside scientific inventories.

## Suggested review focus

1. Check model/diagnostic origin separation, cancelled-v1 claims, paired seeds,
   no-retry scheduling and complete opportunity denominators.
2. Inspect raw batch durability and independent carrier reconstruction, especially
   invalid outputs and interrupted-batch cases.
3. Reconcile headline checkpoint scores with episode pass^2, all paired outcomes
   and the three-source/two-repeat limits.
4. Verify that the output grammar constrains structure only and never contains
   request-specific correct numbers, actions or citation IDs.
5. Inspect the NHC time semantics, exact-valid-time pairing, heldout protection,
   source-line provenance and automatic quarantine. Two parsers of the same
   advisory are not two independent data sources.
6. Check future claims carefully: this milestone does not establish general
   extreme-weather coverage, population significance, operational forecast skill,
   a second-model comparison, or a raw-versus-normalized model experiment.

## Preserved stop-token audit failure and CPU recovery

The model collector exits0 with2160/2160 captured answers. The original report
and verify commands exit1 because the raw runtime text omits EOS as configured,
while its token-ID list retains EOS. The original ACP job therefore remains
FAILED. Do not relabel it SUCCEEDED. Original logs and finalization_001 remain.

repeat_live_review is a separately frozen CPU audit version. It removes exactly
the recognized terminal token from the runtime-text comparison only when the
bound model settings and stop termination require it. Extraction, accepted
carriers and primary scoring still use the unchanged full token sequence. Real
content differences remain errors. All2160 captures reconcile;10 CPU tests and
2 installed-vLLM renderer tests pass, without loading a model or sampling. The
initial two regression failures are retained. Use the reviewer source path in
the command above; the historical reviewer is intentionally unchanged.

The supplementary_relocation_001 receipts cover exact attribution reconstruction
and NHC consensus reconstruction in a copied directory, with path/network guards
exercised before verification. The parent preparation script is one-use; inspect
its receipts instead of relaunching it. Four-worker layout preparation is documented
separately in ../p6_parallel_preparation_v1/README.md.
