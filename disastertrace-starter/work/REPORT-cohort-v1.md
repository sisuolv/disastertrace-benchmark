# Automated weather evaluation report

Diagnostic programs are not LLM benchmark results. Imported responses retain unverified external provenance; no certified leaderboard is produced.

Build: 204681b7be7600a23ad57a7517e2ce5847d2bb5746d978d7b4a144775752f484

## Source admission

- DisasterBench: 230/233 tasks admitted; 3 quarantined without label repair.
- CyPortQA: 48 template declarations inventoried; no claim of complete QA admission.
- NHC: 32 selected official reports parsed; 10 independent storm groups.
- Dynamic example: 20 controlled schedules, 100 checkpoint attempts; original report content unchanged.
- Gold is inherited for planning and generated from admitted source facts plus the explicit replay specification for dynamic tasks.

## Automatic quarantine

- disasterbench:3: step[2]:dependency_output_not_produced:0; step[2]:generated_input_output_not_produced:image_path
- disasterbench:119: step[2]:step_id_must_equal_array_index
- disasterbench:191: step[2]:dependency_output_not_produced:0; step[2]:generated_input_output_not_produced:image_path

## Frozen event cohort

- Catalogue: nhc-atlantic-pilot-v1; 12 planned storm groups; 36/36 records downloaded.
- Admitted groups by split: {'development': 3, 'heldout': 7}.
- All branches and reports from one storm stay in one split. Ida remains in development because it was used for the first implementation.
- This is a selected Atlantic cyclone pilot, not a representative sample of all extreme weather. Held-out events use the same parser and task template; they are not a hidden contamination-free benchmark.
- Full source/event rejections are in profiles/nhc_admission.json and profiles/cohort.json; split assignments are in splits/event_groups.json.

## Diagnostic results

| Track / backend | Model kind | Metric | Result |
| --- | --- | --- | --- |
| dynamic / rule / development | diagnostic_program | grounded_state | 150/150 |
| dynamic / rule / development | diagnostic_program | action_accuracy | 30/30 |
| dynamic / rule / development | diagnostic_program | known_answer_coverage | 96/96 |
| dynamic / last-arrival / development | diagnostic_program | grounded_state | 126/150 |
| dynamic / last-arrival / development | diagnostic_program | action_accuracy | 28/30 |
| dynamic / last-arrival / development | diagnostic_program | known_answer_coverage | 96/96 |
| dynamic / no-update / development | diagnostic_program | grounded_state | 54/150 |
| dynamic / no-update / development | diagnostic_program | action_accuracy | 6/30 |
| dynamic / no-update / development | diagnostic_program | known_answer_coverage | 0/96 |
| dynamic / rule / heldout | diagnostic_program | grounded_state | 350/350 |
| dynamic / rule / heldout | diagnostic_program | action_accuracy | 70/70 |
| dynamic / rule / heldout | diagnostic_program | known_answer_coverage | 224/224 |
| dynamic / last-arrival / heldout | diagnostic_program | grounded_state | 294/350 |
| dynamic / last-arrival / heldout | diagnostic_program | action_accuracy | 70/70 |
| dynamic / last-arrival / heldout | diagnostic_program | known_answer_coverage | 224/224 |
| dynamic / no-update / heldout | diagnostic_program | grounded_state | 126/350 |
| dynamic / no-update / heldout | diagnostic_program | action_accuracy | 14/70 |
| dynamic / no-update / heldout | diagnostic_program | known_answer_coverage | 0/224 |

## Event-level results

Each storm contributes one event; branches and checkpoints do not increase the independent event count. Event macro rates and denominators are preserved in score JSON. No confidence interval or population generalization is claimed.

- dynamic / rule / development: 3 storm groups, 6 branches, 30 checkpoints.
- dynamic / last-arrival / development: 3 storm groups, 6 branches, 30 checkpoints.
- dynamic / no-update / development: 3 storm groups, 6 branches, 30 checkpoints.
- dynamic / rule / heldout: 7 storm groups, 14 branches, 70 checkpoints.
- dynamic / last-arrival / heldout: 7 storm groups, 14 branches, 70 checkpoints.
- dynamic / no-update / heldout: 7 storm groups, 14 branches, 70 checkpoints.

| Run / split | Storm | Grounded fields | Correct rule actions |
| --- | --- | --- | --- |
| dynamic / rule / development | AL092021 | 50/50 | 10/10 |
| dynamic / rule / development | AL062018 | 50/50 | 10/10 |
| dynamic / rule / development | AL052019 | 50/50 | 10/10 |
| dynamic / last-arrival / development | AL092021 | 42/50 | 8/10 |
| dynamic / last-arrival / development | AL062018 | 42/50 | 10/10 |
| dynamic / last-arrival / development | AL052019 | 42/50 | 10/10 |
| dynamic / no-update / development | AL092021 | 18/50 | 2/10 |
| dynamic / no-update / development | AL062018 | 18/50 | 2/10 |
| dynamic / no-update / development | AL052019 | 18/50 | 2/10 |
| dynamic / rule / heldout | AL112017 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL152017 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL142018 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL132020 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL092022 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL102023 | 50/50 | 10/10 |
| dynamic / rule / heldout | AL022024 | 50/50 | 10/10 |
| dynamic / last-arrival / heldout | AL112017 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL152017 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL142018 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL132020 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL092022 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL102023 | 42/50 | 10/10 |
| dynamic / last-arrival / heldout | AL022024 | 42/50 | 10/10 |
| dynamic / no-update / heldout | AL112017 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL152017 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL142018 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL132020 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL092022 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL102023 | 18/50 | 2/10 |
| dynamic / no-update / heldout | AL022024 | 18/50 | 2/10 |

| Run / split | Event macro grounded rate | Event macro action rate |
| --- | --- | --- |
| dynamic / rule / development | 1.0000 | 1.0000 |
| dynamic / last-arrival / development | 0.8400 | 0.9333 |
| dynamic / no-update / development | 0.3600 | 0.2000 |
| dynamic / rule / heldout | 1.0000 | 1.0000 |
| dynamic / last-arrival / heldout | 0.8400 | 1.0000 |
| dynamic / no-update / heldout | 0.3600 | 0.2000 |

## Interpretation

Reference-copy predictions are scorer fixtures that intentionally read private labels, not model outputs. Rule/last-arrival/no-update are deterministic diagnostic programs, not LLMs. Submitted outputs have unverified external provenance.

DisasterBench scores measure agreement with inherited plans, not tool execution or emergency response quality. The new strict admission/response contract is a derived protocol. These tasks cover broad disasters and are not all extreme-weather events.

The weather sample uses real source text with controlled release and repeated/late arrivals. Selected advisories do not establish a population-wide parser admission rate or historical public availability. The missing reopening field tests evidence insufficiency, not actual port recovery.

Offline run/score use diagnostics or imported responses. Separate model collection requires an explicitly configured endpoint and model. Monetary caps, cross-provider budgets, automated search, and resumable live execution are not implemented.
