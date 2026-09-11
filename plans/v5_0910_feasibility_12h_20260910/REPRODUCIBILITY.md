# Reproducing the feasibility evidence

All commands below are run from this feasibility directory. They read frozen
captures and model outputs and write a fresh report directory. They do not call
an API, create a GPU job, download weights, or open a historical execution scope.

```bash
python3 code/verify_feasibility.py --output verification/reviewer_01
```

Choose a new output directory for each verification. Existing receipts are
exclusive and are never silently overwritten. The verifier recomputes seven
audits from raw outputs, compares them with the accepted reports, checks source
body hashes, selected source provenance, frozen input/runtime bindings, GPU
terminal states and preserved baseline files. Some bindings are absolute paths
to this AFS environment; copying the folder alone is not a portable release.

The semantic core can be checked independently without model execution:

```bash
python3 -m unittest discover -s code -p test_evidence_core.py -v
```

Production runners use
`/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python` with pinned
Transformers 4.57.3, PyTorch 2.8, Accelerate 1.11 and native model classes.
Per-wave `PLAN.json` binds the exact versions, library files, model revisions,
weights, processor settings, public inputs and worker source. Remote model code
was not executed. CPU geospatial parsers use separately installed source-probe
and feasibility libraries, explicitly named in their scripts.

## Evidence organization

- `SCOPE.json` is the original 12-hour scope. `SCOPE_AMENDMENT_01.json` preserves
  the original and raises the agent-set model-call cap to 3,600. The user limit
  remains at most four concurrent H100 GPUs. The window is not reopened by
  replaying outputs.
- `attempts/` stores response bodies, intent and response records, including
  HTTP errors and partial captures. `batches/` points to each final probe result.
- `data/` stores source-derived records, array manifests, public state targets
  and evaluator-private references. Public projections are in each GPU batch;
  GPU workers read those projections and do not load the private reference data.
- `gpu/wave*/source/` is the executed worker snapshot. `code/` contains build,
  analysis and verification tools, which may have evolved between waves.
- `runs/*/trajectories/*/turn-*` holds the ordinary trajectory records.
  Wave5 uses `runs/*/tasks/*/step-*`. Raw text is persisted before parsing.
- `analysis/FINAL_RESULTS.json` is the pre-assistance consolidation.
  `analysis/FINAL_RESULTS_02.json` includes Wave7 and is the canonical final
  consolidation. Earlier audits are retained.
- `verification/final_01/` contains the final offline replay receipts.
  `RESOURCE_ACCOUNTING.json` reports actual terminal jobs and interval proxies.

## Re-running inference is a new experiment

The old freezer and launcher paths must not be replayed as though they were
renewable launch recipes: output directories are exclusive and the absolute
deadline is fixed. A future experiment requires a new batch, scope, frozen
inputs and preflight. This is a reproducibility boundary, not a request for
additional permission for the already completed work.

Four one-GPU H100 shards were submitted on `computing-cluster-01g-02` using
worker spec `N6lS.Iu.I10.1.8c128g`. Actual job IDs and terminal records are
stored per batch; the setup guide is
`/mnt/afs/260010168/ACP-GPU-QUICKSTART.md`.

## Release limitations

This is an auditable development bundle, not yet a portable full benchmark
release. Source snapshots include upstream data under their own terms, and
some dependencies refer to inherited captures outside this directory. A public
release should provide source-specific attribution, stable fetch manifests,
relative artifact locations and a locked CPU environment. Do not apply the
software license to every upstream asset.

Weight file bytes and file attempts are recorded, including a failed shard and
its bounded resume. The weight downloader did not record every automatic HTTP
redirect hop. Resource reports preserve this limitation rather than inventing
an exact underlying HTTP transaction count.
