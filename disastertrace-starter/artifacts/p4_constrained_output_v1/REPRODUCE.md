# Reconstruct P4 without model calls

The new launch at 2026-09-08 02:19 UTC is consumed. Never rerun `run_model.py` or
the production `collect` command. Model verification is a read-only reconstruction
of captured tokens, public prompts, method carriers and deterministic scores.

## Existing local CPU environment

The separate environment is
`/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1`. Its package inventory is
`review_cpu_environment.json`. It contains tokenizer/Jinja dependencies and project
CPU dependencies, without Torch, vLLM or XGrammar. It is created with virtualenv
because the system Python lacks ensurepip; packages use the Tsinghua mirror.

From the project directory, after the observer has completed:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p4_constrained_output_v1/execution_live/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python \
  -m disastertrace.constrained_eval.cli report \
  --execution artifacts/p4_constrained_output_v1/execution_live \
  --run work/p4-qwen3-constrained-v1 \
  --output artifacts/p4_constrained_output_v1/model_report \
  --require-model --verify
```

The loaded source inventory must match the execution snapshot. Do not combine
different historical versions under a single import namespace. Read the P3 free
report with its own frozen source if independently rerunning its audit.

## Relocated review

Copy `execution_live/`, the entire canonical model run, and `model_report/` to new
folders named `execution/`, `run/`, `model_report/` under a review directory. Set
PYTHONPATH to that copy's `execution/implementation_source/src`, then run
`verify_portable.py --copy REVIEW --original-project ORIGINAL --model-directory WEIGHTS`.
The script blocks access to original project data/model weights and all network
connections, and asserts Torch/vLLM are absent. The original canonical path recorded
in the claim is preserved as provenance; the copied run is read from the supplied path.
Use `--diagnostic` only for a diagnostic copy; it never upgrades diagnostic origins.

To create another CPU environment, install `requirements-review.txt` and record its
resolved inventory. Matching tokenizer versions matter for byte/token reconstruction.
No credential or API provider setup is required. An archive's per-member hashes
can be checked with Python's standard library even before dependencies are installed.

## Grammar validation versus score reconstruction

`validate_grammar.py` uses the unchanged GPU environment's XGrammar/Torch packages
for CPU token-mask replay. It does not load model weights or call LLM.generate.
`grammar_controls/` covers all predefined Gold/control outputs; `grammar_model/`
checks every actual final token after the reasoning delimiter. The score audit
itself does not require these libraries. Reasoning-only truncation cannot be turned
into a valid final answer by grammar replay.

`analyze_results.py --verify` and `compare_tracks.py --verify` reconstruct the saved
tables and paired descriptive comparison without generating answers. The comparison
also needs the P3 execution/run/report, whose hashes remain in the preservation
baseline; the P4 review archive includes those reference inputs. For relocation,
provide `analyze_results.py --run COPIED_P4_RUN` and
`compare_tracks.py --free-run COPIED_P3_RUN --constrained-run COPIED_P4_RUN`, retaining
`--verify` to compare saved results. The recorded original canonical paths stay
unchanged inside the execution and claim records.

The full 6,932-entry historical-preservation check requires the original repository
and its earlier archive-backed records. Those older stages are not duplicated in
the P4 archive; their completed preservation observations and baseline hashes are
included. This does not affect standalone reconstruction of P4 or the P3 comparison.
Stress context
calibration uses the existing predeclared candidates and ten program carrier types,
not actual LLM stress responses. All fixed output budgets and over-context failures
remain visible in `stress_context/report.json`.

The exact calibration source matching that report's script hash is
`calibration_source/calibrate_stress.py`; the top-level helper has equivalent string
line wrapping applied after the completed calibration. Both are preserved. The
review archive contains `review_contents.json`, an internal per-file inventory;
its external `archive_manifest.json` also binds the compressed archive itself.
`verify_review_portable.py` reconstructs the model report, analysis and track
comparison from a relocated project-shaped copy in one CPU-only process.
