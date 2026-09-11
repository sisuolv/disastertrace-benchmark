# P11 completed audits: expanded native protocol

Qwen3-8B returns all 2,412 planned answers and scores 1,000/2,412 strictly correct
(41.4594%). DeepSeek-R1-Distill-Qwen-7B returns 1,604/2,412 and scores 3/2,412
(0.1244%); its two FAILED workers leave 808 unattempted slots in the denominator.
All four H100 allocations are released and both independent audits pass.

Read [the phase findings](artifacts/p11_cohort_live_v1/FINDINGS.md) for method,
storm, reference-status, failure and resource breakdowns, and
[the DeepSeek stopped-prefix findings](artifacts/p11_cohort_live_v1/DEEPSEEK_FINDINGS.md)
for the exact context projections. The completed acceptance is
`artifacts/p11_cohort_live_v1/COMPLETED_ACCEPTANCE.json`.

Qwen checkpoint strict counts are snapshot356/804, structured_state345/804 and
answer_history299/804. Whole-target single-repeat counts are4/144,22/144,15/144,
respectively. Method rankings differ across storms and metrics. Numeric strict
correctness is485/1794;502 of the1000 total correct answers are not_stated cases.
These are descriptive six-storm development results, not population estimates.

Every method receives the same cumulative source documents. Only the extra
own-answer carrier differs. The task concerns understanding and citing published
NHC forecasts, not generating physical weather forecasts. The public deterministic
resolver scores perfectly. No unit normalization, answer repair, model retries,
paid API, training, heldout inference or per-item human/LLM judging occurs.

The original cross-phase review daemon stops on a later P12 observer metadata
error. Its failure is retained. P11 Qwen analysis is independently completed in
`artifacts/autonomy_10h_v1/reviews_continuation_v2/p11_qwen3.json`; the existing
verified DeepSeek analysis stays in `cohort_reviews_01/p11_deepseek_r1.json`.
The two LOCATION records under `reviews_continuation_v2` specify the complete
project-relative paths and hashes. P11's original terminal model audits both pass.

The v2 acceptance builder retains the original scientific implementation and
checks the explicit CPU continuation locations. To verify an existing acceptance:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  artifacts/autonomy_10h_v1/seal_cohort_evidence_v2.py --phase p11 --verify
```

Use a compatible CPU Python in a restored review workspace. Verification creates
no model calls and does not restart any consumed launch. The already registered
P12 default-spacing and P13/P14 role-placement conditions are separate matrices
within the original autonomous window; consult CURRENT_PHASE.md for their status.
