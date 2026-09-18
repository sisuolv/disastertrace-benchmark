# P12 DeepSeek worker 0: numeric growth despite default JSON spacing

Worker 0 saves 928/1,206 answers, then stops at the context guard before the next
batch is dispatched. It leaves 278 unattempted slots. ACP job `pt-f7z0k9zq` is
FAILED and releases at 2026-09-08T23:01:49Z. No worker or answer is retried.

The frozen stop-analysis tool reconstructs the next batch from saved history;
both analysis and verification exit zero. Output:
`../autonomy_10h_v1/cohort_stops_01/p12_deepseek_r1_worker0.json`, analysis ID
`e8641af7a55b17dde8d7a4386ed352513faf8c2f9acbf074658d96e3fc942ea6`.

| Next scheduled method | Prompt tokens | Reserved output | Full context limit | Exceeds limit |
| --- | ---: | ---: | ---: | --- |
| snapshot | 9163 | 8192 | 32768 | No |
| answer_history | 9404 | 8192 | 32768 | No |
| structured_state | 8847 | 8192 | 32768 | No |
| answer_history | 27603 | 8192 | 32768 | Yes |

These requests were not dispatched. The last would require 35,795 tokens after
reserving output. The unchanged collector stops the whole worker, also preventing
later work on unrelated trajectories that would fit.

## All four answers in the blocked history

`characterize_blocked_history.py` binds raw-batch fingerprints, selected capture
bytes, the schedule and the prior stop analysis. It checks the prior-answer count
and total characters against that independently audited projection. These four
answers total 16,138 final-text characters:

| Saved batch | Final characters | ASCII digits | Whitespace | Trailing digit run |
| --- | ---: | ---: | ---: | ---: |
| 28 | 331 | 38 | 29 | 0 |
| 82 | 329 | 37 | 29 | 0 |
| 133 | 7581 | 7508 | 6 | 7498 |
| 183 | 7897 | 7824 | 6 | 7811 |

Both long answers end in an unfinished integer in `citation.wind_line`. Batch
183 begins with `forecast_line: 2022`; its `wind_line` starts `20202020202015`,
followed by a long zero sequence. These are observed model strings, not accepted
citation values. Explicitly labeled excerpts appear in the diagnostic JSON;
complete, unchanged output remains in the original batch captures.

Output: `blocked_history_worker0.json`, analysis ID
`25fa42c51dc49969031f3abeedcdf3f7232e9996d6f8f4fc19f1e49b5d2402d8`.
Its build and reconstruction checks both exit zero. Selection is posthoc: all
four preceding answers of this one blocked trajectory. It is not a representative
performance sample or a new set of Gold labels.

The first descriptive-helper command compared a file-byte digest with a field
that stores a canonical JSON fingerprint. It failed before writing output.
Its original source, failed command and correction receipt remain under
`../autonomy_10h_v1/validation/p12_blocked_history_*`. The corrected helper follows
the unchanged collector/auditor convention. Original captures, the scientific
collector and scoring code remain unchanged.

## What this establishes

Default separator spacing removes arbitrary JSON formatting whitespace. It does
not bound integer digits, guarantee a complete final JSON within the output cap,
or guarantee that later answer history fits the context. This worker demonstrates
remaining numeric-output growth rather than a large formatting-whitespace flood.

Future engineering should first isolate over-budget trajectories. Any public,
predeclared bounds on integer/string representation need a new protocol version
and counterexamples showing that wrong but legal answers remain possible. This
proposal does not justify changing old captures, fixing citations, truncating
history or replacing failed slots.
