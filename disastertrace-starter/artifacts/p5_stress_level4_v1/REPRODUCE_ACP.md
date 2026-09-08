# Reconstruct P5 ACP evaluation without model calls

The ACP phase is a one-use execution. Never rerun `launch_p5.py`, `acp_worker.py`
or a production `collect` command from the completed run. Preserve every capture,
including invalid, length-limited or wrong answers. Read-only progress is available
through `python3 artifacts/p5_stress_level4_v1/status.py` from the project root.

## Frozen implementation and CPU environment

The unchanged implementation used for each factor is under
`units/<factor>/execution_live/implementation_source/`. Exact environment, model
configuration, tokenizer, backend source and data are bound inside that execution.
The portable review does not need model weights, Torch, vLLM, credentials or network.
Install the CPU requirements copied as `requirements-review.txt`; the recorded
environment is `review_cpu_environment.json`. The existing local CPU interpreter is
`/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python`.

Example from the project root, with that CPU interpreter available as `python`:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p5_stress_level4_v1/units/revision_chain/execution_live/implementation_source/src \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m disastertrace.stress_eval.cli report \
  --execution artifacts/p5_stress_level4_v1/units/revision_chain/execution_live \
  --run work/p5-qwen3-revision-chain-v1 \
  --output artifacts/p5_stress_level4_v1/units/revision_chain/model_report \
  --require-model --verify
```

Repeat the verification with the other two factor names and their corresponding
run names (underscores in factor directories, hyphens in run names). A report from
`diagnostic` or `live_diagnostic` is a program fixture, and `--require-model`
correctly rejects it. Current working files do not replace the frozen source.

## Independent relocation

The review archive uses project-relative paths. It includes the three P5
executions, raw runs and reports, plus the P4 constrained execution/run/report
needed for matched comparisons. After extraction, use the copied P5 frozen source
as `PYTHONPATH`. `verify_review.py --copy COPIED_PROJECT --original-project ORIGINAL
--model-directory ORIGINAL_WEIGHTS` rebuilds all four reports, analysis and paired
comparison while blocking original data/weights and network connections. It writes
a new `verification_result.json` exclusively, so use a fresh extraction for a new
verification. The original canonical paths inside claims stay as provenance;
the auditor reads the supplied copied run paths.

`compare_stress.py --verify --base-run COPIED_P4_RUN --runs-root COPIED_PROJECT/work`
and `analyze_p5.py --verify --runs-root COPIED_PROJECT/work` verify saved
postprocessing without generation. The former checks unchanged Gold, model,
sampling (except the predeclared new slot seeds), all metric denominators,
checkpoint opportunities, public evidence and source mappings.

Full historical preservation additionally needs the older repository records
and archives. Those older stages are not all duplicated in this review archive;
their observed checks and baseline hashes are included. This limitation does not
affect standalone P4/P5 report and comparison reconstruction.

## Actual grammar replay and resource evidence

`validate_grammar.py --execution UNIT/execution_live --run COPIED_RUN --output NEW_DIR`
uses the pinned XGrammar/Torch libraries on CPU to check actual final tokens.
It does not load model weights or generate answers. This optional replay requires
more dependencies than score reconstruction; saved `grammar_model/` results remain
available in each factor unit.

`acp/phase_001/` contains submission commands, actual ACP job IDs, observed platform
states, worker claims, hardware and subprocess exits. These are local/platform
observations, not hardware attestation. A full H100 replaces P4's MIG partition;
sampling seeds also change with stress slot identities. Timings and score changes
are descriptive, with three dependent source groups and one repeat.

The archive's internal `review_contents.json` records per-member SHA-256 hashes.
The external `archive_manifest.json` also binds the compressed archive. No model
weights or credential files are included, and packaging does not publish a release.
