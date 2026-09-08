# Expanded native forecast development cohort

Offline-complete: six additional Atlantic storms,36 original NHC forecast
advisories,144 target valid times and804 future checkpoints. Three methods and
one repeat give2412 candidate answers per model,4824 for the separately planned
two-model comparison. This offline package produces no model answers.

Entry protocol and findings: artifacts/p10_forecast_cohort_v1/PROTOCOL.md and
artifacts/p10_forecast_cohort_v1/FINDINGS.md. The execution is execution_01 in
that bundle; source acquisition and dual-parser review remain in the distinct
artifacts/p10_source_catalog_v1. Original parser failures are retained.

All110 related tests,21,708 full-denominator program-control opportunities and
17,252 actual tokenizer checks pass. The legal public resolver answers every
question correctly. Copy-based CPU reconstruction passes with original project,
weights,network and child processes blocked. This is software and real-source
validation, not evidence of model competence.

New task loader/package: src/disastertrace/forecast_cohort. It reuses the frozen
P7 contract,renderer,compiler and scorer without editing them. Later model
collection belongs to the separate cohort_live/P11 execution. The six storms
are curated development sources; all declared heldout IDs remain protected.
