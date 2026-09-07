# Offline amended-continuation reporting

This new reporting layer composes the frozen P1 reporter's independent rescore
verification, metrics, usage, transport-latency and price-window calculations.
It does not change the frozen experiment, source data, prompts or scorers. It
makes no API calls and preserves the prior interrupted experiment and report.

The separate accounting validator handles the amended continuation: 79 original
ledger rows remain unchanged; 18 received answer_history prefix records remain
byte-identical; the new request suffix is matched in order and by multiplicity.
The first new call is explicitly bound to original unresolved attempt 79.
Repeated request hashes are not deduplicated. All 90 benchmark opportunities
remain in scoring denominators even if continuation stops before completion.

The original uncertain attempt remains outside the resumed collection and inside
the cumulative ledger. Thus 91 admitted attempts can correspond to 90 received
benchmark responses. The original USD 0.46678016 reservation is not released,
and actual total expense remains unknown. Received-response cache-aware costs
are labeled subtotals. The answer_history cost and latency denominators include
its unresolved original attempt; the other two completed methods reuse original
artifacts through verified aliases.

`checks.json` records the actual independent 23-test execution, source hashes,
lint and format checks. The tests include immutable real captured data as
offline fixtures, rejected history/usage/cap/authorization mutations, repeated
request hashes, partial-count accounting, raw-output failure classification,
and a complete source-bound report with HTTP access rejected. These tests are
separate from prior core and continuation-runner test executions.

`execution.json` and `execution.log` record the actual report command and result.
The report's `manifest.json` binds inputs, reporting source and report outputs.
The reporting code was written after collection as a deterministic reporting
layer; it is not presented as a pre-frozen new scoring policy.

Regenerate into a fresh output directory, with no model calls:

```bash
.venv/bin/python artifacts/p1_deepseek_development/continuation_report/report_continuation.py \
  --amendment artifacts/p1_deepseek_development/background_resume/prepared/amendment.json \
  --continuation work/p1-deepseek-background-continuation-v1 \
  --output work/p1-continuation-report-recheck-001
```

Focused tests (requires the preserved completed continuation as offline input):

```bash
.venv/bin/python -m pytest -o addopts= -q \
  artifacts/p1_deepseek_development/continuation_report/test_report_continuation.py
```

The worker must have closed collection, independent audit and scores before
reporting. A stopped, finalized collection is reported as partial. An unclosed
capture or failed finalization is rejected; it requires a separate explicit
offline finalization rather than invented responses or implicit API resubmission.
