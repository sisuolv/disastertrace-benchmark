# Calibration execution report

Mode: `urllib_http`. Completed 270/270.

Program transports are diagnostics, never LLM results. Projection construction makes zero provider calls; actual calls are counted in the separately audited journal. Missing opportunities remain in fixed denominators and are not claims of model knowledge errors.

Live budget recommendation: `8192`.

| Cell | Attempted / 30 | Received | Schema valid | Length | Known grounded |
| --- | ---: | ---: | ---: | ---: | ---: |
| legacy_4096__snapshot | 30 | 30 | 17 | 12 | 44/96 |
| legacy_4096__structured_state | 30 | 30 | 28 | 1 | 90/96 |
| legacy_4096__answer_history | 30 | 30 | 27 | 3 | 81/96 |
| explicit_4096__snapshot | 30 | 30 | 27 | 3 | 84/96 |
| explicit_4096__structured_state | 30 | 30 | 30 | 0 | 96/96 |
| explicit_4096__answer_history | 30 | 30 | 28 | 2 | 85/96 |
| explicit_8192__snapshot | 30 | 30 | 30 | 0 | 91/96 |
| explicit_8192__structured_state | 30 | 30 | 30 | 0 | 90/96 |
| explicit_8192__answer_history | 30 | 30 | 30 | 0 | 96/96 |

report.json includes per-storm numerators/denominators, equal-weight event macros, paired arm differences, overlapping failure counts, captured usage and transport latency. UTC intent/capture times bracket collection; they are not authenticated provider billing timestamps. Snapshot-rate/cache-aware estimates require complete, consistent cache counts and a single pricing window. Missing or crossed windows retain unknown cost; conservative reservations remain separate. Diagnostic estimates are simulations, never incurred spend.
