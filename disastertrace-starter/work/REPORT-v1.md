# Automated first-work-package report

This report contains data checks and offline diagnostics, not LLM benchmark results.

Build: 3669bbb9717a54c21de4c9d8d64b969f4d165fd3cafb7c728bfb3fb267fca979

## Source admission

- DisasterBench: 230/233 tasks admitted; 3 quarantined without label repair.
- CyPortQA: 48 template declarations inventoried; no claim of complete QA admission.
- NHC: 3 selected official Ida reports parsed; 1 independent storm.
- Dynamic example: 2 controlled schedules, 10 checkpoint attempts; original report content unchanged.
- Gold is inherited for planning and generated from admitted source facts plus the explicit replay specification for dynamic tasks.

## Automatic quarantine

- disasterbench:3: step[2]:dependency_output_not_produced:0; step[2]:generated_input_output_not_produced:image_path
- disasterbench:119: step[2]:step_id_must_equal_array_index
- disasterbench:191: step[2]:dependency_output_not_produced:0; step[2]:generated_input_output_not_produced:image_path

## Diagnostic results

| Track / backend | Model kind | Metric | Result |
| --- | --- | --- | --- |
| dynamic / rule | diagnostic_program | grounded_state | 50/50 |
| dynamic / rule | diagnostic_program | action_accuracy | 10/10 |
| dynamic / rule | diagnostic_program | known_answer_coverage | 32/32 |
| dynamic / last-arrival | diagnostic_program | grounded_state | 42/50 |
| dynamic / last-arrival | diagnostic_program | action_accuracy | 8/10 |
| dynamic / last-arrival | diagnostic_program | known_answer_coverage | 32/32 |
| dynamic / no-update | diagnostic_program | grounded_state | 18/50 |
| dynamic / no-update | diagnostic_program | action_accuracy | 2/10 |
| dynamic / no-update | diagnostic_program | known_answer_coverage | 0/32 |
| disasterbench / reference-fixture | scorer_fixture | Inherited exact agreement | 230/230 |
| disasterbench / empty-control | scorer_fixture | Inherited exact agreement | 0/230 |

## Interpretation

Reference-copy predictions are scorer fixtures that intentionally read private labels, not model outputs. Rule/last-arrival/no-update are deterministic diagnostic programs, not LLMs. Submitted outputs have unverified external provenance.

DisasterBench scores measure agreement with inherited plans, not tool execution or emergency response quality. The new strict admission/response contract is a derived protocol. These tasks cover broad disasters and are not all extreme-weather events.

The weather sample uses real source text with controlled release and repeated/late arrivals. Three selected advisories do not establish a general parser admission rate, historical public availability, or a statistically adequate benchmark. The missing reopening field tests evidence insufficiency, not actual port recovery.

The current runner preserves completed episode traces but does not implement provider calls, cross-provider budgets, automated search, or resumable live execution. Next: expand admitted independent events and connect an explicitly configured model backend.
