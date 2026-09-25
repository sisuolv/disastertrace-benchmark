# Reproduction guide: v21 execution 20260925_04

Run commands from the repository root unless a command changes directory.
The checked-in JSON files are frozen receipts. Re-running a command should use
a new output directory so that this receipt is not overwritten.

## Offline regression

```bash
cd disastertrace-starter
.venv/bin/python -m pytest \
  tests/test_v17*.py tests/test_v18*.py tests/test_v19*.py tests/test_v21*.py -q
.venv/bin/python -m compileall -q src scripts tests
.venv/bin/ruff check src scripts tests --select E9,F63,F7,F82
```

The recorded execution passed 226 v17-v21 tests, compileall, Ruff critical
checks, and `git diff --check`.

## Bounded real-development diagnostic

The source and outcome commands below require the local research archive. Set
`DATA_ROOT` to that archive without committing it:

```bash
ROOT="$PWD"
DATA_ROOT=/path/to/data_real_v16
OUT="$ROOT/disastertrace-starter/artifacts/v21_rerun"
mkdir -p "$OUT"

cd "$ROOT/disastertrace-starter"
.venv/bin/python scripts/build_v18_dev_episodes.py \
  --data-root "$DATA_ROOT" \
  --out "$OUT/G1_DEV_EPISODES_V3.json" \
  --limit 24
.venv/bin/python scripts/run_v21_real_dev_source_bridge.py \
  --source-artifact "$OUT/G1_DEV_EPISODES_V3.json" \
  --out "$OUT/REAL_DEV_SOURCE_BRIDGE.json"
.venv/bin/python scripts/bind_v21_dev_asos_outcomes.py \
  --source-artifact "$OUT/G1_DEV_EPISODES_V3.json" \
  --data-root "$DATA_ROOT" \
  --out "$OUT/REAL_DEV_ASOS_OUTCOMES.json"
.venv/bin/python scripts/run_v21_real_dev_deterministic_score.py \
  --source-artifact "$OUT/REAL_DEV_SOURCE_BRIDGE.json" \
  --outcome-artifact "$OUT/REAL_DEV_ASOS_OUTCOMES.json" \
  --out "$OUT/REAL_DEV_DETERMINISTIC_SCORE.json"
```

The bridge stops before outcomes and provider calls. The ASOS binder is
evaluator-only and enforces the declared four-station, two-month read set.
Do not point these commands at quarantine, holdout, or the protected February
window.

## Synthetic CPU/GPU diagnostics

The synthetic scripts do not read weather data or call a provider. A CPU smoke
run is:

```bash
cd disastertrace-starter
.venv/bin/python scripts/run_v21_cost_matched_adaptive_surface.py \
  --out /tmp/v21-cost-matched.json --n 10000 --seed 350925 --device cpu
```

For a GPU replication, use the same script with `--device cuda`, a fresh output
path, and a new seed/job receipt. The checked-in `cost_matched_gpu/` and
`shared_delay_gpu/` directories contain the original commands, request
metadata, script hashes, submissions, and per-cell results for the six
successful tide jobs.

## Interpretation

`HANDOFF_REPORT_V4.md`, `CLAIM_EVIDENCE_TABLE_V4.md`, and `PROTOCOL_GATE_V4.json`
are the authoritative interpretation of this execution. The synthetic GPU
surface supports a conditional mechanism hypothesis only; it does not support
a weather, provider, or novelty claim. A future provider-backed pilot needs a
new run ID, complete denominator, equal retrieval/model-call cost, and a
predeclared harm guard.
