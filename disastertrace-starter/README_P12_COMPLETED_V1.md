# P12 completed model-condition audits

The system contract is retained; XGrammar uses default JSON separator spacing.

deepseek-ai/DeepSeek-R1-Distill-Qwen-7B: 9/2412 strictly correct (0.3731%), with 1994/2412 returned.
Qwen/Qwen3-8B: 1060/2412 strictly correct (43.9469%), with 2412/2412 returned.

All allocations are released. The fixed denominator includes missing returns;
audit completion does not imply a fully collected matrix or successful GPU jobs.

See [phase findings](artifacts/p12_compact_grammar_v1/FINDINGS.md) for all method, storm,
reference-status, error, unit, output and resource breakdowns. Exact report and
analysis paths are bound by the LOCATION records under
`artifacts/autonomy_10h_v1/reviews_continuation_v2/`.

Every method sees the same cumulative source documents. Own-answer carriers
differ; no hidden-evidence memory or numerical weather-forecasting claim follows.
Interpret prompt conditions with their separate histories and remaining time.

Verify the completed inventory without restarting any model launch:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  artifacts/autonomy_10h_v1/seal_cohort_evidence_v3.py --phase p12 --verify
```

Use a compatible CPU Python in a restored review workspace. No retries, heldout
inference, paid API, training, unit normalization or human/LLM judge occurs.
