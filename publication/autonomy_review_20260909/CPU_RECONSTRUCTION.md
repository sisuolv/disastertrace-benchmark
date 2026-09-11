# Independent CPU reconstruction

Use a completed phase's accepted evidence volumes. The selected reading ZIP is
not sufficient: it omits complete raw runs, tokenizers, and execution closures.
Restore the appropriate volumes with `evidence_archive.py` before these steps.
Read the archive manifests and the phase's actual terminal status first.

## What each check establishes

1. Archive restoration and verification check accepted file bytes and original
   paths. They do not run the scientific evaluator.
2. A phase acceptance verifier checks the saved acceptance identity and every
   bound file. It does not create new answers or override the recorded job state.
3. The saved `portable_review.py` imports the copied source, verifies the copied
   execution, and reconstructs the saved report from raw records on CPU. It blocks
   the original/restored projects outside isolation, model weights, networking,
   subprocesses, and model backend imports.
4. XGrammar token-mask replay is an additional check. Its saved commands and logs
   are included in the phase finalization. Re-executing it requires the recorded
   XGrammar/torch/backend dependencies; ordinary CPU semantic reconstruction does
   not require installing the full GPU environment or loading model weights.

These checks do not validate every external meteorological assumption, establish
historical public availability, or prove freedom from training-data contamination.
They preserve the exact distinction between a complete collection and an auditable
stopped prefix.

## Observed CPU review environment

The actual isolated CPU reviews use Python 3.10.12. Relevant installed versions
include pydantic 2.13.5, transformers 4.55.2, tokenizers 0.21.4, Jinja2 3.1.6,
numpy 2.2.6, safetensors 0.8.0, huggingface_hub 0.34.4, and packaging 26.3.
These are observed versions, not a claim that this short list exhausts all
transitive dependencies or that every other environment has been tested.

Use an already compatible CPU environment or prepare a separate review
environment. Do not upgrade the environment that produced the accepted evidence.
The saved wrapper intentionally rejects imports of torch, vLLM, TensorFlow, and
Flax during semantic report reconstruction. Its recorded urllib3 IPv6 capability
probe remains denied and is accounted for separately from unexpected access.

## Example: completed P11 Qwen report

Run this only when the restored P11 Qwen finalization is present and its status
is `passed`. All arguments passed to the wrapper must be absolute, because the
wrapper changes its working directory. Choose a new receipt filename each time.

```bash
DT_REVIEW_ROOT='/absolute/path/to/restored-review'
DT_CPU_PYTHON='/absolute/path/to/compatible-cpu-python'
DT_REVIEW_PROJECT="$DT_REVIEW_ROOT/disastertrace-starter"
DT_AUDIT_DIR="$DT_REVIEW_PROJECT/artifacts/p11_cohort_live_v1/finalization_qwen3_01/cpu_relocated"

PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  "$DT_CPU_PYTHON" "$DT_AUDIT_DIR/portable_review.py" \
  --execution "$DT_AUDIT_DIR/execution" \
  --isolation-root "$DT_AUDIT_DIR" \
  --blocked-root "$DT_REVIEW_PROJECT" \
  --blocked-root '/mnt/afs/260010168/extreme_weather_benchmark/development/disastertrace-next/disastertrace-starter' \
  --blocked-root '/mnt/afs/260010168/models' \
  --review-spec "$DT_AUDIT_DIR/review_spec.json" \
  --output "$DT_AUDIT_DIR/INDEPENDENT_RECEIPT_01.json"
```

The two `/mnt/afs/...` paths identify the original execution environment being
denied; they are not paths to create or sources to download. The restored project
outside the isolated copy is also denied. The wrapper's own isolation directory
must stay accessible. Do not edit original absolute path strings inside manifests,
requests, journals, or reports to make them resemble your new workspace.

For another completed cohort model, use the exact directory named in its
`artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_<phase>_<profile>.json`.
P12's initial observers fail on ACP QUEUEING/INIT metadata; their failures stay
in `finalization_<profile>_01`, while fresh CPU observers use `_02`. The LOCATION
record distinguishes these directories and binds hashes. Use the successful
directory's own wrapper and execution closure. For P9 use
`finalization_02`, preserving the failed `finalization_01` evidence. Earlier phases
can use different review-spec layouts; follow their saved command intent files
with relocated absolute paths, rather than guessing arguments.

## Verify a completed phase inventory

From the restored `disastertrace-starter` directory, using the same CPU Python:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  "$DT_CPU_PYTHON" artifacts/autonomy_10h_v1/seal_cohort_evidence_v2.py \
  --phase p11 --verify
```

Use `p12`, `p13`, or `p14` only when that phase has a completed acceptance file.
Those later phases use `seal_cohort_evidence_v3.py`, which fixes a per-case
analysis-file omission in the preserved v2 P11 inventory. Restore the final
supplemental evidence as well as the P11 phase archive, then verify the independent
P11 addendum with `seal_p11_review_addendum.py --verify`. It explicitly binds the
two omitted analyses and twelve command-chain files without replacing P11's
original acceptance or raw evidence. The v2 inventory check alone cannot prove
coverage of those omitted files. See the autonomous bundle's
`ACCEPTANCE_COVERAGE_ADDENDUM.md` for the actual failure and regression evidence.
The `--verify` option is required for review; creating another acceptance is not
part of reconstruction. Do not launch `run_after_*.py`, `run_preflight*.py`, or
model collection commands. Historical phase and worker claims are consumed, and
new inference would be a different experiment.

## Persistent recovery and cutoff evidence

The initial publication CPU processes and local temporary restore roots were
absent when work continued. The interruption record preserves the original
command intents and logs without inventing their missing exit codes. The new
`recover_cpu_publication_v2.py` chain restores all five phase archive groups and
verifies the P11-P14 inventories. Its first CPU command fails before task import
because it chooses a receipt path outside the unchanged wrapper's isolation root.
`complete_cpu_reconstruction_v3.py` reuses those successful restoration steps,
reconstructs the six model conditions with local output paths and immediately
copies each successful receipt to persistent AFS with matching hashes. The failed
command and recovery status remain preserved. Their final
copies and exact command chains are in
`artifacts/autonomy_10h_v1/publication_reconstruction_02/` inside the supplement.
The copy receipt binds their execution/report identities and the recovery source.
The older helper and incomplete controllers are historical evidence, not commands
to rerun. Reconstruction never requires a model API or another GPU launch.

The final auxiliary cutoff analysis is `dispatch_deadlines_v3.json`. V1 failed
on an unpublished zero-byte intent; V2 then rejected normal parsed-cache
directories. V3 and its 23-test suite preserve both failures, bind the temporary
bytes and parsed-cache files, and count only published dispatch/raw records.
All six cases verify with no dispatch outside their cutoff. P14 has four unknown
worker-0 outcomes; worker 1's zero-byte unpublished intent does not establish a
new attempt. The supplementary diagnostic verifies host-clock records and is
not an independent device-clock attestation. These fixes do not alter the
scientific raw records, original scoring or completed phase acceptances.
