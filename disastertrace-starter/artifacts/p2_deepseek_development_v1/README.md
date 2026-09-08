# First P2 DeepSeek development comparison

Chinese entry: [README_P2_DEEPSEEK_V1.md](../../README_P2_DEEPSEEK_V1.md).

The user authorizes one development matrix of at most 270 requests and a separate
USD 3 conditional allowance. The model is deepseek-v4-flash with high reasoning,
thinking enabled, no temperature, and a common 8192 output cap. No retries or
automatic restarts are enabled. The original frozen production registry is kept.

The detached worker completes all 270 responses and independent audit at
2026-09-07 13:15:39 UTC. The common format screen fails: U2 snapshot and
answer_history each have 28/30 valid answers. Six answers are schema-invalid
(four structural errors, two length/empty); three additional fields have correct
values but invalid citations. All final offline reconstructions pass.

Read [FINDINGS.md](FINDINGS.md), [NEXT_PHASE_PLAN.md](NEXT_PHASE_PLAN.md), and
[REVIEW_GUIDE.md](REVIEW_GUIDE.md). Machine outcome: [FINAL_STATUS.json](FINAL_STATUS.json).
The initial 270-call scope is consumed. No further paid matrix is authorized.

## Files

- `execution/`: unchanged frozen P2 execution and bound implementation source.
- `launch_manifest.json`: preparation inventory, identity, run path and registry.
- `authorization.json` and `authorization_context.json`: actual current approval.
- `docs/` and `price_attestation.json`: fresh matching official documentation.
- `runner.py` and `test_runner.py`: tested one-use detached launcher.
- `diagnostic/`: complete 270-slot offline run; never eligible as LLM results.
- `runtime/`: real worker progress, completion and independently verified report.
- `analyze.py`: offline error inventory and paired descriptive comparisons.
- `schema_inventory.py` and `render_tables.py`: reproducible failure details and tables.
- `validation/`: commands, observed exit codes, logs and preservation checks.
- `archive_manifest.json`: file hashes for the final review archive.

## Read-only status

From the project directory:

```bash
.venv/bin/python artifacts/p2_deepseek_development_v1/runner.py status
```

Do not run the one-use launch command again. The 270-request allowance, output
cap and budget belong to one execution; copies or alternative output directories
do not provide new authorization. A stopped unknown dispatch must not be resent.

The worker audits and reports after collection or a safe stop. The frozen direct
report preserves every denominator and requires model capture origin. It also
recomputes its own report through the independent auditor before completion.

The prior 999-test core remains unchanged; this launcher has eight passing tests.
No new per-item human annotation, LLM judging, heldout or second-model inference
is included. P1's unresolved original attempt 79 is outside this P2 accounting.
