# Independent audit of the completed P1 continuation

The completed amended continuation passes 1,887 independent artifact and
accounting checks. This audit makes zero model requests and changes no source,
capture, scoring or historical artifacts. Evidence is in `result.json`,
`audit.log`, `process_observation.json`, and `commands.json`.

The separately authorized USD 1.5 allowance permits at most 12 new calls, at
most 91 cumulative calls, and one explicit retry of unresolved original
attempt 79. All 12 new calls completed, yielding 90 benchmark answers from 91
admitted calls. The first new call, number 80, has exactly the unresolved
request's payload hash. The original result and charge remain unknown.

| Quantity | Verified value |
| --- | ---: |
| Original answers retained | 78, including 20 invalid answers |
| New answers received | 12, including 2 invalid answers |
| All benchmark answer opportunities | 90 |
| Cumulative admitted calls | 91 |
| Cumulative requested output reservations | 372,736 tokens |
| Received prompt tokens | 293,816 |
| Received completion tokens | 170,378 |
| Received total tokens | 464,194 |
| Received cache-hit / cache-miss prompt tokens | 141,312 / 152,504 |
| Reasoning tokens, already included in completion tokens | 158,370 |

All 90 received responses have the expected returned model alias and timestamps
inside the captured Sunday price window. Decimal arithmetic independently
reproduces the received-response estimate of USD 0.146989544, including
USD 0.023630952 for the 12 new responses. This excludes any unreported charge
for original attempt 79 and is not a provider invoice.

Conservative peak-rate accounting is USD 0.35417800 settled plus the unchanged
USD 0.46678016 original pending reservation, totaling USD 0.82095816 and leaving
USD 0.67904184 under the conditional local allowance. Receiving the retry does
not release or settle the original reservation.

The audit checks journal positions, checkpoint identities, raw-response hashes
and usage in order. Equal request payloads at distinct checkpoints are allowed.
All 79 original ledger rows are unchanged. The original 18 answer-history
responses, outcomes and requests remain byte-identical in the resumed prefix.
Snapshot and structured-state collections are the preserved original files.
The frozen amendment, actual authorization, launch hashes and original 22-test
offline evidence match their saved identities. An independent `/proc`
observation confirms the worker ran in its own session with no controlling
terminal; its final exit record reports code 0.

All 177 protected historical files and 83 original interrupted-capture files
match their previous hashes. A separate `sha256sum --check` verifies all 247
entries in the preserved partial package, with exit code 0.

These checks establish artifact consistency and conditional accounting. They
do not establish provider billing authentication, an immutable backend model
version, a representative benchmark population, or causal carrier effects.
The restart and fixed method order remain timing and cache confounds. The
frozen scorer stays unchanged and no per-item human review or LLM judge is used.

The final reporter and generated output pass 372 additional independent checks
in `report_review_final.json`. These verify all manifest inputs and outputs,
the reporter's 23-test source identity, original V1 metrics and the two derived
known-only rates, V2 metrics, event macros, paired differences, costs and
independently calculated latency means and quantiles. The report ID is
`38eec952940983180eb670bc40a8bd482bb4a805501ce6d360d35ed415306e4c`.

Code review identified authorization-binding and per-call budget validation
gaps in the new reporter before generation. Both were fixed and tested before
the final report. No violation exists in the independently checked live data.
The initial report audit incorrectly expected the reporter's V1 metric mapping
to equal the raw mapping even though the frozen reporter adds two derived
known-only rates. Its three failed checks, source and log remain preserved.
The corrected audit verifies all original keys plus both derived rates;
`report_review_commands.json` explains this audit-assumption correction and
records both command exit codes. No scorer or reported result was changed.

The audit refuses to overwrite its result files; preserve these observations
when creating another audit. All current source and output files are frozen
after the final review.
