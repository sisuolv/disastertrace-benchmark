# P1 interrupted-capture audit

`result.json` records the independent, offline audit of the original interrupted
capture in `work/p1-deepseek-development-v1`. All 1,548 checks pass. This is an
artifact-integrity and accounting result; it does not mean 90 live requests
completed. No model request or retry was made by this audit.

## Observed execution

The original execution file still says `running` and contains the last completed
method boundary (60 calls). The original budget ledger is newer: 79 admitted
calls and 78 recorded completions. Attempt 79 is `answer_history`, Florence,
delay branch, checkpoint c3; it was admitted at
`2026-09-06T16:07:36.809370+00:00` and has no saved outcome or usage.
No `run_experiment.py` process was present when `/proc` was inspected.
The process exit status and precise interruption time are unknown. A separate
observation describes the interrupted state; no original status, journal or
ledger was rewritten.

| Method | Planned | Admitted | Received | Accepted | Invalid | Outcome unknown | Unattempted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| snapshot | 30 | 30 | 30 | 14 | 16 | 0 | 0 |
| structured_state | 30 | 30 | 30 | 30 | 0 | 0 | 0 |
| answer_history | 30 | 19 | 18 | 14 | 4 | 1 | 11 |

Accepted means schema-valid, not necessarily factually correct. The offline
scoring package determines correctness with the frozen scoring rules.

## Cost interpretation

The 78 received completions have valid recorded usage, the expected returned
model alias, and provider-created timestamps inside the frozen Sunday off-peak
window. Their cache-aware estimated subtotal is USD 0.123358592:

| Method | Observed received-response estimate, USD |
| --- | ---: |
| snapshot | 0.066161104 |
| structured_state | 0.022414064 |
| answer_history | 0.034783424 |

The full experiment's incurred cost is unknown because attempt 79 may have
reached the provider. Its USD 0.46678016 reservation remains retained. Decimal
arithmetic verifies the conservative peak-rate reported subtotal of
USD 0.30435328 plus that reservation equals USD 0.77113344, leaving
USD 0.22886656 in the conditional local allowance. These accounting values
are not a provider invoice or provider-enforced billing limit.

Observed usage is 255,491 prompt tokens and 145,407 completion tokens, totaling
400,898. The 135,081 reasoning tokens are already part of completion tokens.
Prompt cache hits are 135,296 and misses are 120,195.

## Comparison limits

All methods retain 30 planned scoring opportunities. The answer-history
full-denominator result therefore includes 12 checkpoints without a saved
response: one uncertain admitted attempt and eleven unattempted checkpoints.
Those missing responses reflect interruption and must not be described as
demonstrated model mistakes. Observed-prefix-only diagnostics use selected
observations and do not complete the intended three-method comparison.
The two fully captured methods can be compared descriptively under this exact
development protocol, with its fixed order, one repeat and small selected cohort.
No statistical significance, causal memory benefit, broad method superiority,
heldout performance or general extreme-weather competence follows.

The original `final_checks/protocol_audit/audit.py --stage final` is not used:
it requires a completed 90-response run and assumes unique request hashes.
Some base/delay checkpoints legitimately have identical requests. This audit
checks ordered request journals and multisets, preserving duplicate requests
and their separately recorded usage.

## Integrity and reproduction

The audit verifies all 177 protected historical files, frozen experiment,
runner, reporter, provider configuration, price source/rates, build artifacts,
implementation files, and saved request/response/ledger bindings. It hashes
all 83 original live files before and after inspection and confirms no changes.
`commands.json` records command evidence and lint/format checks.

The audit refuses to overwrite its existing `result.json`. For another
observation, preserve this directory and adapt the output location in a new
audit script, recording that new source hash. Do not change the existing
experiment or scorer to fit observed results.
