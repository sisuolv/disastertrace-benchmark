# P14 completed model-condition audits

Qwen receives the same contract text in the user message, under default JSON separator spacing.

Qwen/Qwen3-8B: 952/2412 strictly correct (39.4693%), with 1628/2412 returned.

All allocations are released. The fixed denominator includes missing returns;
audit completion does not imply a fully collected matrix or successful GPU jobs.

See [phase findings](artifacts/p14_qwen_prompt_role_v1/FINDINGS.md) for all method, storm,
reference-status, error, unit, output and resource breakdowns. Exact report and
analysis paths are bound by the LOCATION records under
`artifacts/autonomy_10h_v1/reviews_continuation_v2/`.

Every method sees the same cumulative source documents. Own-answer carriers
differ; no hidden-evidence memory or numerical weather-forecasting claim follows.
Interpret prompt conditions with their separate histories and remaining time.

Verify the completed inventory without restarting any model launch:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  artifacts/autonomy_10h_v1/seal_cohort_evidence_v3.py --phase p14 --verify
```

Use a compatible CPU Python in a restored review workspace. No retries, heldout
inference, paid API, training, unit normalization or human/LLM judge occurs.
