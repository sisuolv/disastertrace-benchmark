# DisasterTrace P7: native forecast-claim task, offline verified

P7 implements Section 1 of the accepted P6 next research plan. It turns the
twelve already admitted NHC forecast advisories into a separately versioned task
for reading, updating and citing published forecasts. It contains no new LLM
answers, GPU jobs, acquisitions, human Gold annotations or LLM-judge calls.

Start with [findings](artifacts/p7_forecast_task_v1/FINDINGS.md), the
[task contract](artifacts/p7_forecast_task_v1/PROTOCOL.md), and the
[next executable plan](artifacts/p7_forecast_task_v1/NEXT_EXECUTION_PLAN.md).
The [review guide](artifacts/p7_forecast_task_v1/REVIEW_GUIDE.md) explains the main
scientific and software checks for an independent reviewer.

| Item | Completed result |
| --- | --- |
| Natural sources | 12 products, 95 forecast rows, two development storms |
| Target catalogue | 46 unique storm/absolute-valid-time targets |
| Candidate / included / excluded checkpoints | 276 / 257 / 19 (not future) |
| Included statuses | 176 numeric, 26 explicit terminal, 55 not_stated |
| Method/repeat schedule | three methods, two repeats, 1542 answer slots |
| Legal public resolver | 1542/1542 correct program answers |
| Diagnostic coverage | nine policies, 13878 planned program answer opportunities |
| Tests | 64 new plus 26 relevant historical tests pass |
| Actual-tokenizer checks | 2831 different requests; max prompt 16059 plus 8192 reserved output |
| CPU reconstruction | exact copied source, source bytes, requests, scores and token counts reproduced |
| Four-H100 preview | 390 / 390 / 384 / 378 answers, whole target episodes kept together |

The compiler rebuilds both admitted source parsers from original saved bytes.
The public resolver has its own text parser and reads only the exact messages
shown to a model. The scorer separates values, units, absolute time, source
version, literal support and locators, retaining invalid/missing opportunities.
Current source claims and historical P1-P6 results remain frozen.

The first CPU wrapper exits 1 after successful reconstruction because it treats
urllib3's denied local IPv6 capability probe as unexpected network activity. The
versioned v2 wrapper still denies that bind, records it separately and exits 0;
all original-path, connection and subprocess restrictions remain active. Both
attempts and the dependency source evidence are retained.

## Verify from the frozen source

Run from `disastertrace-starter` using the existing CPU review environment:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=artifacts/p7_forecast_task_v1/execution_v1/source/src \
USE_TORCH=0 CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false \
/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python \
  -m disastertrace.forecast_task verify \
  --execution artifacts/p7_forecast_task_v1/execution_v1
```

The exact relocated CLI invocation and observed exit are in
`artifacts/p7_forecast_task_v1/validation/cpu_relocation_002/result.json`.
It installs the isolation guard before importing the copied package and requires
no Torch, vLLM, network, original source path or model weights.

The final milestone record is
`artifacts/p7_forecast_task_v1/OFFLINE_ACCEPTANCE.json`. Verify its inventory with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  artifacts/p7_forecast_task_v1/accept_offline.py --verify
```

The scientific execution and acceptance are immutable; use `CURRENT_PHASE.md`
for later navigation. Do not edit an accepted P6/P7 file to update progress.
New local code is under `src/disastertrace/forecast_task/`, with core tests in
`tests/p7_forecast_task/`. A fresh native collector, multi-worker audit/aggregation
and actual-H100 preflight are the next engineering tasks before a model launch.
The preview has no dispatch path or reusable live attempt claim.
